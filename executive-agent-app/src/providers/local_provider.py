import json
import logging
import os
import urllib.request
import urllib.error
from typing import Callable, Optional


_log = logging.getLogger("megav.cloud")


class LocalOllamaProvider:
    """Ollama integration for local + cloud models — uncensored-first.

    Cloud routing: any model whose tag ends with ":cloud" tries the local
    daemon first (so `ollama signin` keeps working), and falls back to
    https://ollama.com when the local daemon is down or rejects the request.
    """

    CLOUD_BASE_URL = "https://ollama.com"

    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url

    # ── Auth helpers ──────────────────────────────────────────────────
    @staticmethod
    def _read_api_key() -> str:
        """Resolve OLLAMA_API_KEY from settings.json or env."""
        try:
            from .model_router import ModelRouter
            key = ModelRouter.get_ollama_api_key()
            if key:
                return key
        except Exception:
            pass
        return os.environ.get("OLLAMA_API_KEY", "").strip()

    @staticmethod
    def _is_cloud_model(model: str) -> bool:
        return isinstance(model, str) and model.endswith(":cloud")

    # ── Core request: try local, optionally fall back to cloud ────────
    def _send(self, path: str, payload: dict, *, stream: bool, timeout: int):
        """POST to /api/<path>. For :cloud models, fall back to ollama.com.

        Returns the urllib response object on success. Caller must close it.
        Raises the underlying exception if both attempts fail.
        """
        model = payload.get("model", "")
        is_cloud = self._is_cloud_model(model)
        attempts = [(self.base_url, None)]
        if is_cloud:
            key = self._read_api_key()
            attempts.append((self.CLOUD_BASE_URL, key or None))

        last_err: Optional[Exception] = None
        for base, api_key in attempts:
            url = f"{base}/api/{path}"
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                )
                resp = urllib.request.urlopen(req, timeout=timeout)
                if base != self.base_url:
                    _log.info("cloud fallback succeeded via %s for %s", base, model)
                return resp
            except urllib.error.HTTPError as e:
                last_err = e
                if is_cloud and base == self.base_url and e.code in (401, 403, 404, 502, 503):
                    _log.info("local daemon rejected %s (HTTP %s) — trying cloud", model, e.code)
                    continue
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
                last_err = e
                if is_cloud and base == self.base_url:
                    _log.info("local daemon unreachable for %s (%s) — trying cloud", model, e)
                    continue
                break
            except Exception as e:
                last_err = e
                break

        assert last_err is not None
        raise last_err

    # ── Public API (unchanged signatures) ─────────────────────────────
    def generate(self, prompt, model="dolphin-mistral"):
        """Generate a response using Ollama."""
        payload = {"model": model, "prompt": prompt, "stream": False}
        try:
            with self._send("generate", payload, stream=False, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
                return {"success": True, "response": result.get("response", "")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def chat(self, messages, model="dolphin-mistral", timeout=300):
        """Chat completion using Ollama."""
        payload = {"model": model, "messages": messages, "stream": False}
        try:
            with self._send("chat", payload, stream=False, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                return {"success": True, "message": result.get("message", {})}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stream_chat(self, messages, model="dolphin-mistral", callback=None, timeout=300):
        """Stream chat completion, calling callback(chunk_text) for each token."""
        payload = {"model": model, "messages": messages, "stream": True}
        try:
            full_response = ""
            with self._send("chat", payload, stream=True, timeout=timeout) as response:
                for line in response:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        full_response += content
                        if callback:
                            callback(content)
                    if chunk.get("done"):
                        break
            return {"success": True, "message": {"role": "assistant", "content": full_response}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_model_info(self, model_name: str) -> dict:
        """Get detailed info about a model via POST /api/show."""
        url = f"{self.base_url}/api/show"
        payload = {"name": model_name}
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception:
            return {}

    def list_models_detailed(self) -> list[dict]:
        """List installed models with full metadata (name, size, family, etc.)."""
        url = f"{self.base_url}/api/tags"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get("models", [])
        except Exception:
            return []

    def get_running_models(self) -> list[str]:
        """List models currently loaded in VRAM via GET /api/ps."""
        url = f"{self.base_url}/api/ps"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            return []
