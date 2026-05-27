"""
MCP (Model Context Protocol) Client Adapter.

Provides a simple stdio-based MCP client that can:
  - Start MCP server processes (Playwright, Context7, Tavily)
  - Send JSON-RPC requests to list and call tools
  - Gracefully degrade when servers are unavailable

Usage from agents::

    from tools_ext.mcp_tools import MCPClient

    client = MCPClient()
    result = client.call_tool("context7", "resolve-library-id", {
        "libraryName": "react",
        "query": "how to use hooks"
    })
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional

import yaml


# ---------------------------------------------------------------------------
# MCP Server Configuration
# ---------------------------------------------------------------------------

def load_mcp_config() -> dict[str, dict]:
    """Load MCP server configs from settings.yaml."""
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        servers = cfg.get("mcp_servers", {})
        return {k: v for k, v in servers.items() if v.get("enabled", True)}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# MCP stdio Client
# ---------------------------------------------------------------------------

class MCPServerProcess:
    """Manages a single MCP server subprocess communicating via stdio JSON-RPC."""

    def __init__(self, name: str, command: str, env: dict | None = None,
                 description: str = ""):
        self.name = name
        self.command = command
        self.env = env or {}
        self.description = description
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._request_id = 0

    def start(self) -> bool:
        """Start the MCP server process."""
        if self._proc and self._proc.poll() is None:
            return True
        try:
            full_env = {**os.environ, **self.env}
            # Filter out empty values
            full_env = {k: v for k, v in full_env.items() if v}
            self._proc = subprocess.Popen(
                self.command.split(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=full_env,
                bufsize=0,
            )
            # Send initialize request
            init_resp = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "MegaV", "version": "2.2.0"},
            })
            if init_resp is None:
                return False
            # Send initialized notification
            self._send_notification("notifications/initialized", {})
            return True
        except Exception as exc:
            print(f"[MCP] Failed to start {self.name}: {exc}", file=sys.stderr)
            return False

    def stop(self):
        """Stop the MCP server process."""
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def list_tools(self) -> list[dict]:
        """List available tools from the MCP server."""
        resp = self._send_request("tools/list", {})
        if resp and "result" in resp:
            return resp["result"].get("tools", [])
        return []

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server."""
        return self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

    def _send_request(self, method: str, params: dict) -> Optional[dict]:
        """Send a JSON-RPC request and return the response."""
        if not self._proc or self._proc.poll() is not None:
            return None
        with self._lock:
            self._request_id += 1
            msg_id = self._request_id
        request = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params,
        }
        return self._write_and_read(request)

    def _send_notification(self, method: str, params: dict):
        """Send a JSON-RPC notification (no response expected)."""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        try:
            payload = json.dumps(notification) + "\n"
            if self._proc and self._proc.stdin:
                self._proc.stdin.write(payload.encode("utf-8"))
                self._proc.stdin.flush()
        except Exception:
            pass

    def _write_and_read(self, request: dict) -> Optional[dict]:
        """Write a JSON-RPC message and read the response."""
        try:
            payload = json.dumps(request) + "\n"
            if not self._proc or not self._proc.stdin:
                return None
            self._proc.stdin.write(payload.encode("utf-8"))
            self._proc.stdin.flush()

            # Read response line
            if not self._proc.stdout:
                return None
            response_line = self._proc.stdout.readline()
            if not response_line:
                return None
            return json.loads(response_line.decode("utf-8"))
        except Exception as exc:
            print(f"[MCP] Error communicating with {self.name}: {exc}",
                   file=sys.stderr)
            return None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None


# ---------------------------------------------------------------------------
# MCP Client (high-level API)
# ---------------------------------------------------------------------------

class MCPClient:
    """High-level MCP client that manages multiple server connections."""

    def __init__(self):
        self._servers: dict[str, MCPServerProcess] = {}
        self._tools_cache: dict[str, list[dict]] = {}
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy init: load configs on first use."""
        if self._initialized:
            return
        configs = load_mcp_config()
        for name, cfg in configs.items():
            self._servers[name] = MCPServerProcess(
                name=name,
                command=cfg.get("command", ""),
                env=cfg.get("env", {}),
                description=cfg.get("description", ""),
            )
        self._initialized = True

    def start_server(self, name: str) -> bool:
        """Start a specific MCP server."""
        self._ensure_initialized()
        server = self._servers.get(name)
        if not server:
            return False
        return server.start()

    def stop_server(self, name: str):
        """Stop a specific MCP server."""
        self._ensure_initialized()
        server = self._servers.get(name)
        if server:
            server.stop()

    def stop_all(self):
        """Stop all running MCP servers."""
        for server in self._servers.values():
            server.stop()

    def list_tools(self, server_name: str) -> list[dict]:
        """List available tools from a specific MCP server."""
        self._ensure_initialized()
        server = self._servers.get(server_name)
        if not server:
            return []
        if not server.is_running and not server.start():
            return []
        tools = server.list_tools()
        self._tools_cache[server_name] = tools
        return tools

    def call_tool(self, server_name: str, tool_name: str,
                  arguments: dict | None = None) -> dict:
        """Call a tool on a specific MCP server.

        Args:
            server_name: Name of the MCP server (e.g., "context7", "tavily", "playwright")
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            dict with 'success' bool and 'result' or 'error'
        """
        self._ensure_initialized()
        server = self._servers.get(server_name)
        if not server:
            return {"success": False, "error": f"Unknown MCP server: {server_name}"}
        if not server.is_running and not server.start():
            return {"success": False, "error": f"Failed to start MCP server: {server_name}"}

        response = server.call_tool(tool_name, arguments or {})
        if response is None:
            return {"success": False, "error": f"No response from {server_name}"}
        if "error" in response:
            return {"success": False, "error": response["error"].get("message", str(response["error"]))}
        return {"success": True, "result": response.get("result", {})}

    def get_available_servers(self) -> list[str]:
        """Return list of configured MCP server names."""
        self._ensure_initialized()
        return list(self._servers.keys())

    def is_server_available(self, name: str) -> bool:
        """Check if a server is configured and can be started."""
        self._ensure_initialized()
        return name in self._servers


# ---------------------------------------------------------------------------
# Convenience functions for agents
# ---------------------------------------------------------------------------

_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get or create the global MCP client instance."""
    global _client
    if _client is None:
        _client = MCPClient()
    return _client


def mcp_call(server: str, tool: str, args: dict | None = None) -> dict:
    """Quick-call an MCP tool. Convenience wrapper for agents."""
    client = get_mcp_client()
    return client.call_tool(server, tool, args)


def mcp_list_tools(server: str) -> list[dict]:
    """List tools available on an MCP server."""
    client = get_mcp_client()
    return client.list_tools(server)