"""DeepSeek API provider — uses requests (no openai package needed)."""

import os
import json
import requests
from typing import Any, Callable


class DeepSeekProvider:
    DEFAULT_MODEL = "deepseek-chat"
    REASONER_MODEL = "deepseek-reasoner"
    MAX_TOKENS_CODE = 16384
    MAX_TOKENS_CHAT = 8192
    MAX_TOKENS_REASONING = 16384
    BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def available(self) -> bool:
        return bool(self.api_key)

    def _post(self, messages: list, model: str, max_tokens: int) -> dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "No DeepSeek API key set"}
        try:
            resp = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self._headers(),
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
                timeout=60,
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            data = resp.json()
            text = data["choices"][0]["message"]["content"] or ""
            reasoning = data["choices"][0]["message"].get("reasoning_content")
            result = {"success": True, "response": text,
                      "message": {"role": "assistant", "content": text}}
            if reasoning:
                result["reasoning"] = reasoning
            return result
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out (60s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate(self, prompt: str, model: str = "", max_tokens: int = 0) -> dict[str, Any]:
        return self._post(
            [{"role": "user", "content": prompt}],
            model or self.DEFAULT_MODEL,
            max_tokens or self.MAX_TOKENS_CODE,
        )

    def chat(self, messages: list, model: str = "", max_tokens: int = 0) -> dict[str, Any]:
        return self._post(messages, model or self.DEFAULT_MODEL, max_tokens or self.MAX_TOKENS_CHAT)

    def stream_chat(self, messages: list, model: str = "", max_tokens: int = 0,
                    callback: Callable[[str], None] | None = None) -> dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "No DeepSeek API key set"}
        try:
            full = ""
            with requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self._headers(),
                json={"model": model or self.DEFAULT_MODEL, "messages": messages,
                      "max_tokens": max_tokens or self.MAX_TOKENS_CHAT, "stream": True},
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
                        if payload.strip() == "[DONE]":
                            break
                        chunk = json.loads(payload)
                        text = chunk["choices"][0].get("delta", {}).get("content") or ""
                        if text:
                            full += text
                            if callback:
                                callback(text)
            return {"success": True, "message": {"role": "assistant", "content": full}}
        except Exception as e:
            return {"success": False, "error": str(e)}
