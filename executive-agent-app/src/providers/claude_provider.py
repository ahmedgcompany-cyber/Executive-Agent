"""Claude (Anthropic) provider — uses requests (no anthropic package needed)."""

import os
import json
import requests
from typing import Any, Callable


class ClaudeProvider:
    DEFAULT_MODEL = "claude-opus-4-7"
    CODE_MODEL = "claude-sonnet-4-6"
    FAST_MODEL = "claude-haiku-4-5-20251001"
    REASONING_MODEL = "claude-opus-4-7"

    MAX_TOKENS_CODE = 16384
    MAX_TOKENS_CHAT = 8192
    MAX_TOKENS_FAST = 4096
    MAX_TOKENS_REASONING = 16384

    BASE_URL = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }

    def available(self) -> bool:
        return bool(self.api_key)

    def _build_payload(self, messages: list, model: str, max_tokens: int) -> dict:
        """Separate system message from conversation messages (Anthropic API requirement)."""
        system = ""
        chat_msgs = []
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content", "")
            else:
                chat_msgs.append(m)
        payload: dict = {"model": model, "max_tokens": max_tokens, "messages": chat_msgs}
        if system:
            payload["system"] = system
        return payload

    def _post(self, messages: list, model: str, max_tokens: int) -> dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "No Anthropic API key set"}
        try:
            resp = requests.post(
                f"{self.BASE_URL}/messages",
                headers=self._headers(),
                json=self._build_payload(messages, model, max_tokens),
                timeout=60,
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            data = resp.json()
            text = "".join(b.get("text", "") for b in data.get("content", []))
            return {"success": True, "response": text,
                    "message": {"role": "assistant", "content": text}}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out (60s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate(self, prompt: str, model: str = "", max_tokens: int = 0) -> dict[str, Any]:
        return self._post(
            [{"role": "user", "content": prompt}],
            model or self.CODE_MODEL,
            max_tokens or self.MAX_TOKENS_CODE,
        )

    def chat(self, messages: list, model: str = "", max_tokens: int = 0) -> dict[str, Any]:
        return self._post(messages, model or self.DEFAULT_MODEL, max_tokens or self.MAX_TOKENS_CHAT)

    def generate_with_thinking(self, prompt: str, model: str = "", max_tokens: int = 0,
                                thinking_budget: int = 10000) -> dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "No Anthropic API key set"}
        try:
            resp = requests.post(
                f"{self.BASE_URL}/messages",
                headers=self._headers(),
                json={
                    "model": model or self.REASONING_MODEL,
                    "max_tokens": max_tokens or self.MAX_TOKENS_REASONING,
                    "thinking": {"type": "enabled", "budget_tokens": thinking_budget},
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120,
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            data = resp.json()
            text = ""
            thinking_text = ""
            for block in data.get("content", []):
                if block.get("type") == "thinking":
                    thinking_text += block.get("thinking", "")
                elif block.get("type") == "text":
                    text += block.get("text", "")
            result = {"success": True, "response": text}
            if thinking_text:
                result["reasoning"] = thinking_text
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stream_chat(self, messages: list, model: str = "", max_tokens: int = 0,
                    callback: Callable[[str], None] | None = None) -> dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "No Anthropic API key set"}
        try:
            full = ""
            with requests.post(
                f"{self.BASE_URL}/messages",
                headers={**self._headers(), "anthropic-beta": ""},
                json={**self._build_payload(messages, model or self.DEFAULT_MODEL,
                                            max_tokens or self.MAX_TOKENS_CHAT),
                      "stream": True},
                timeout=120, stream=True,
            ) as resp:
                if resp.status_code != 200:
                    return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
                for line in resp.iter_lines():
                    if not line:
                        continue
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        payload = decoded[6:]
                        chunk = json.loads(payload)
                        if chunk.get("type") == "content_block_delta":
                            text = chunk.get("delta", {}).get("text", "")
                            if text:
                                full += text
                                if callback:
                                    callback(text)
            return {"success": True, "message": {"role": "assistant", "content": full}}
        except Exception as e:
            return {"success": False, "error": str(e)}
