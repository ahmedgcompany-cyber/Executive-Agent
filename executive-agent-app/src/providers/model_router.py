"""Route LLM requests to the best available provider.

UNCENSORED-FIRST routing:
  - Ollama uncensored models first (free, local, no restrictions)
  - DeepSeek API second (cheap cloud, capable, uncensored)
  - Claude last (premium cloud, best for complex code/reasoning)

Auto-pulls the best uncensored Ollama models when they're not installed.
"""

import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Optional

from .local_provider import LocalOllamaProvider
from .claude_provider import ClaudeProvider
from .deepseek_provider import DeepSeekProvider
from .openrouter_provider import OpenRouterProvider
from .uncensored_catalog import UncensoredModelCatalog


class NoModelAvailableError(Exception):
    """Raised when no LLM provider is available."""
    def __init__(self, message: str = "", ollama_status: dict | None = None):
        super().__init__(message)
        self.ollama_status = ollama_status or {}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional["ModelRouter"] = None


def get_model_router() -> "ModelRouter":
    """Return the global ModelRouter singleton."""
    global _instance
    if _instance is None:
        _instance = ModelRouter()
    return _instance


class ModelRouter:
    """Task-type-aware model router — uncensored-first.

    Routing priority per task type:
      coder:    Ollama (uncensored) -> DeepSeek -> Claude -> Ollama (any)
      general:  Ollama (uncensored) -> DeepSeek -> Claude -> Ollama (any)
      reasoning: Ollama (uncensored) -> DeepSeek reasoner -> Claude -> Ollama (any)
      fast:     Ollama (fast uncensored) -> DeepSeek -> Ollama (any)
      vision:   Ollama (vision) -> Claude

    When prefer_uncensored=False, Claude is tried first for coder tasks.
    """

    # Backward-compatible class attributes (now sourced from catalog)
    OLLAMA_MODELS = {}  # populated lazily from catalog
    OLLAMA_AUTO_PULL = []  # populated lazily from catalog
    OLLAMA_FALLBACK = UncensoredModelCatalog.FALLBACK_ID

    # Config file for persisting settings
    _CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".megav")
    _CONFIG_FILE = os.path.join(_CONFIG_DIR, "settings.json")

    # Cache for installed models (refreshed every 10s)
    _installed_cache: list[str] = []
    _installed_cache_time: float = 0.0
    _CACHE_TTL = 10.0

    def __new__(cls, *args, **kwargs):
        """Singleton: always return the same instance."""
        global _instance
        if _instance is None:
            _instance = super().__new__(cls)
        return _instance

    def __init__(self):
        # Skip re-init if already initialized (singleton)
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.ollama = LocalOllamaProvider()
        self.catalog = UncensoredModelCatalog()
        self._claude: ClaudeProvider | None = None
        self._deepseek: DeepSeekProvider | None = None
        self._openrouter: OpenRouterProvider | None = None
        self._auto_pull_attempted = False

        # Populate backward-compatible class attrs from catalog
        self._populate_compat_attrs()

    def _populate_compat_attrs(self):
        """Fill OLLAMA_MODELS and OLLAMA_AUTO_PULL from catalog for backward compat."""
        for task_type in ("coder", "general", "vision", "fast", "reasoning"):
            models = self.catalog.get_models_for_task(task_type)
            self.OLLAMA_MODELS[task_type] = [m["id"] for m in models]
        self.OLLAMA_AUTO_PULL = self.catalog.AUTO_PULL_IDS

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    @classmethod
    def _get_fernet(cls):
        """Return Fernet cipher, creating key file on first use."""
        from cryptography.fernet import Fernet
        key_path = Path.home() / ".megav" / "secret.key"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if not key_path.exists():
            key_path.write_bytes(Fernet.generate_key())
            key_path.chmod(0o600)
        return Fernet(key_path.read_bytes())

    @classmethod
    def _encrypt(cls, value: str) -> str:
        return cls._get_fernet().encrypt(value.encode()).decode()

    @classmethod
    def _decrypt(cls, value: str) -> str:
        try:
            return cls._get_fernet().decrypt(value.encode()).decode()
        except Exception:
            return value  # already plaintext (legacy)

    _API_KEY_FIELDS = ("anthropic_api_key", "deepseek_api_key", "openrouter_api_key")

    @classmethod
    def _load_settings(cls) -> dict:
        try:
            if os.path.exists(cls._CONFIG_FILE):
                with open(cls._CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for field in cls._API_KEY_FIELDS:
                    if field in data and data[field]:
                        data[field] = cls._decrypt(data[field])
                return data
        except Exception:
            pass
        return {}

    @classmethod
    def _save_settings(cls, settings: dict):
        try:
            os.makedirs(cls._CONFIG_DIR, exist_ok=True)
            to_write = dict(settings)
            for field in cls._API_KEY_FIELDS:
                if field in to_write and to_write[field]:
                    to_write[field] = cls._encrypt(to_write[field])
            with open(cls._CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(to_write, f, indent=2)
        except Exception:
            pass

    # -- Anthropic API key ------------------------------------------------

    @classmethod
    def set_api_key(cls, key: str):
        settings = cls._load_settings()
        settings["anthropic_api_key"] = key
        cls._save_settings(settings)
        os.environ["ANTHROPIC_API_KEY"] = key
        if _instance:
            _instance._claude = None

    @classmethod
    def get_api_key(cls) -> str:
        settings = cls._load_settings()
        return settings.get("anthropic_api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")

    @classmethod
    def clear_api_key(cls):
        settings = cls._load_settings()
        settings.pop("anthropic_api_key", None)
        cls._save_settings(settings)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        if _instance:
            _instance._claude = None

    # -- DeepSeek API key -------------------------------------------------

    @classmethod
    def set_deepseek_api_key(cls, key: str):
        settings = cls._load_settings()
        settings["deepseek_api_key"] = key
        cls._save_settings(settings)
        os.environ["DEEPSEEK_API_KEY"] = key
        if _instance:
            _instance._deepseek = None

    @classmethod
    def get_deepseek_api_key(cls) -> str:
        settings = cls._load_settings()
        return settings.get("deepseek_api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")

    @classmethod
    def clear_deepseek_api_key(cls):
        settings = cls._load_settings()
        settings.pop("deepseek_api_key", None)
        cls._save_settings(settings)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        if _instance:
            _instance._deepseek = None

    # -- OpenRouter API key -----------------------------------------------

    @classmethod
    def set_openrouter_api_key(cls, key: str):
        settings = cls._load_settings()
        settings["openrouter_api_key"] = key
        cls._save_settings(settings)
        os.environ["OPENROUTER_API_KEY"] = key
        if _instance:
            _instance._openrouter = None

    @classmethod
    def get_openrouter_api_key(cls) -> str:
        settings = cls._load_settings()
        return settings.get("openrouter_api_key", "") or os.environ.get("OPENROUTER_API_KEY", "")

    @classmethod
    def clear_openrouter_api_key(cls):
        settings = cls._load_settings()
        settings.pop("openrouter_api_key", None)
        cls._save_settings(settings)
        os.environ.pop("OPENROUTER_API_KEY", None)
        if _instance:
            _instance._openrouter = None

    # -- Ollama Cloud API key ---------------------------------------------

    @classmethod
    def set_ollama_api_key(cls, key: str):
        settings = cls._load_settings()
        settings["ollama_api_key"] = key
        cls._save_settings(settings)
        if key:
            os.environ["OLLAMA_API_KEY"] = key
        else:
            os.environ.pop("OLLAMA_API_KEY", None)

    @classmethod
    def get_ollama_api_key(cls) -> str:
        settings = cls._load_settings()
        return settings.get("ollama_api_key", "") or os.environ.get("OLLAMA_API_KEY", "")

    @classmethod
    def clear_ollama_api_key(cls):
        settings = cls._load_settings()
        settings.pop("ollama_api_key", None)
        cls._save_settings(settings)
        os.environ.pop("OLLAMA_API_KEY", None)

    # -- General settings -------------------------------------------------

    @classmethod
    def get_prefer_uncensored(cls) -> bool:
        settings = cls._load_settings()
        return settings.get("prefer_uncensored", False)

    @classmethod
    def get_auto_pull_enabled(cls) -> bool:
        settings = cls._load_settings()
        return bool(settings.get("auto_pull_models", False))

    @classmethod
    def set_auto_pull_enabled(cls, value: bool):
        settings = cls._load_settings()
        settings["auto_pull_models"] = bool(value)
        cls._save_settings(settings)

    def invalidate_model_cache(self) -> None:
        """Force next _get_installed_models() call to refresh."""
        self._installed_cache_time = 0.0

    @classmethod
    def set_prefer_uncensored(cls, value: bool):
        settings = cls._load_settings()
        settings["prefer_uncensored"] = value
        cls._save_settings(settings)

    @classmethod
    def get_vram_tier(cls) -> int:
        """Return user's VRAM tier (1=12GB+, 2=8-12GB, 3=4-8GB). Default 1."""
        settings = cls._load_settings()
        return settings.get("vram_tier", 1)

    @classmethod
    def set_vram_tier(cls, tier: int):
        settings = cls._load_settings()
        settings["vram_tier"] = tier
        cls._save_settings(settings)

    @classmethod
    def get_preferred_local_model(cls) -> str:
        settings = cls._load_settings()
        return settings.get("preferred_local_model", "")

    @classmethod
    def set_preferred_local_model(cls, model: str):
        settings = cls._load_settings()
        settings["preferred_local_model"] = model
        cls._save_settings(settings)

    # ------------------------------------------------------------------
    # Provider getters
    # ------------------------------------------------------------------

    def _get_claude(self) -> ClaudeProvider | None:
        if self._claude is None:
            key = self.get_api_key()
            if key:
                self._claude = ClaudeProvider(api_key=key)
        return self._claude if (self._claude and self._claude.available()) else None

    def _get_deepseek(self) -> DeepSeekProvider | None:
        if self._deepseek is None:
            key = self.get_deepseek_api_key()
            if key:
                self._deepseek = DeepSeekProvider(api_key=key)
        return self._deepseek if (self._deepseek and self._deepseek.available()) else None

    def _get_openrouter(self) -> OpenRouterProvider | None:
        if self._openrouter is None:
            key = self.get_openrouter_api_key()
            if key:
                self._openrouter = OpenRouterProvider(api_key=key)
        return self._openrouter if (self._openrouter and self._openrouter.available()) else None

    # ------------------------------------------------------------------
    # Auto-pull better Ollama models
    # ------------------------------------------------------------------

    def _auto_pull_models(self):
        """Auto-pull uncensored models — gated by user setting (default off).

        User must explicitly opt in via setup wizard or settings toggle
        (auto_pull_models: true in settings.yaml). Never runs by default.
        """
        if self._auto_pull_attempted:
            return
        self._auto_pull_attempted = True

        if not self.get_auto_pull_enabled():
            return

        status = self.ollama_status()
        if not status.get("running"):
            return

        installed = set(status.get("models", []))
        vram_tier = self.get_vram_tier()
        pull_list = self.catalog.get_auto_pull_list(vram_tier)

        for model in pull_list:
            already_installed = any(model in m or m in model for m in installed)
            if not already_installed:
                try:
                    creationflags = 0
                    if os.name == "nt":
                        creationflags = subprocess.CREATE_NO_WINDOW
                    subprocess.Popen(
                        ["ollama", "pull", model],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=creationflags,
                    )
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Status and availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        if self.is_ollama_running():
            return True
        if self._get_deepseek() is not None:
            return True
        if self._get_claude() is not None:
            return True
        return False

    def get_status(self) -> dict:
        """Return status info about available providers and models."""
        ollama_info = self.ollama_status()
        claude_available = self._get_claude() is not None
        deepseek_available = self._get_deepseek() is not None
        openrouter_available = self._get_openrouter() is not None
        prefer_uncensored = self.get_prefer_uncensored()

        # Determine active provider
        if ollama_info["running"] and ollama_info["has_model"]:
            active_provider = "ollama"
            models = ollama_info.get("models", [])
            active_model = self._pick_ollama_model("general") if models else None
            uncensored_count = sum(1 for m in models if self.catalog.is_uncensored(m))
            ollama_info["uncensored_count"] = uncensored_count
        elif deepseek_available:
            active_provider = "deepseek"
            active_model = DeepSeekProvider.DEFAULT_MODEL
        elif openrouter_available:
            active_provider = "openrouter"
            active_model = OpenRouterProvider.DEFAULT_MODEL
        elif claude_available:
            active_provider = "claude"
            active_model = ClaudeProvider.CODE_MODEL
        else:
            active_provider = None
            active_model = None

        return {
            "ollama": ollama_info,
            "claude": claude_available,
            "deepseek": deepseek_available,
            "openrouter": openrouter_available,
            "active_provider": active_provider,
            "active_model": active_model,
            "prefer_uncensored": prefer_uncensored,
        }

    def ollama_status(self) -> dict:
        """Return {'running': bool, 'has_model': bool, 'models': list}."""
        try:
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=0.5) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                return {"running": True, "has_model": bool(models), "models": models}
        except Exception:
            return {"running": False, "has_model": False, "models": []}

    def is_ollama_running(self) -> bool:
        return self.ollama_status()["running"]

    # ------------------------------------------------------------------
    # Model selection — uncensored-first
    # ------------------------------------------------------------------

    def _get_installed_models(self) -> list[str]:
        """Get installed models list (cached for 60s)."""
        now = time.time()
        if now - self._installed_cache_time > self._CACHE_TTL:
            status = self.ollama_status()
            self._installed_cache = status.get("models", [])
            self._installed_cache_time = now
        return self._installed_cache

    def _pick_ollama_model(self, task_type: str = "general") -> str:
        """Pick the best installed Ollama model for a task type — uncensored first."""
        preferred_model = self.get_preferred_local_model()
        # Cloud tags bypass /api/tags — Ollama daemon (or our cloud fallback)
        # streams them on demand without a local pull.
        if preferred_model and preferred_model.endswith(":cloud"):
            return preferred_model

        installed = self._get_installed_models()
        if not installed:
            return self.OLLAMA_FALLBACK

        # If user has a preferred model and it's installed, use it
        if preferred_model:
            for inst in installed:
                if inst == preferred_model or inst.startswith(preferred_model + ":"):
                    return inst

        # Use catalog to pick the best uncensored model for this task type
        prefer_uncensored = self.get_prefer_uncensored()
        catalog_models = self.catalog.get_models_for_task(task_type, prefer_uncensored=prefer_uncensored)

        for cat_model in catalog_models:
            cat_id = cat_model["id"]
            for inst in installed:
                # Exact match
                if inst == cat_id:
                    return inst
                # Prefix match (handles tags like :Q4_K_M, :latest)
                cat_base = cat_id.split(":")[0]
                inst_base = inst.split(":")[0]
                if inst_base == cat_base or inst.startswith(cat_base + ":"):
                    return inst
                if cat_base.startswith(inst_base) or inst_base.startswith(cat_base):
                    return inst

        # Try family matching
        for cat_model in catalog_models:
            for inst in installed:
                inst_lower = inst.lower()
                if cat_model["family"].lower() in inst_lower:
                    return inst

        # No catalog match — use first available installed model
        return installed[0]

    # ------------------------------------------------------------------
    # Core routing — uncensored-first, task-type-aware
    # ------------------------------------------------------------------

    def route_generate(self, prompt: str, task_type: str = "general",
                       system_prompt: str = "") -> dict:
        """Generate text. Routes uncensored-first based on task type."""
        result: dict = {}
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            result = self.route_chat(messages, task_type=task_type)
            if result.get("success"):
                result["provider"] = result.get("provider", "unknown")
                return result
            return result

        prefer_uncensored = self.get_prefer_uncensored()

        if prefer_uncensored:
            # Uncensored-first: Ollama -> DeepSeek -> Claude -> Ollama any
            result = self._ollama_generate_best(prompt, task_type)
            if result.get("success"):
                result["provider"] = "ollama"
                result["model"] = result.get("model", self._pick_ollama_model(task_type))
                return result

            ds = self._get_deepseek()
            if ds:
                model = DeepSeekProvider.REASONER_MODEL if task_type == "reasoning" else DeepSeekProvider.DEFAULT_MODEL
                result = ds.generate(prompt, model=model)
                if result.get("success"):
                    result["provider"] = "deepseek"
                    result["model"] = model
                    return result

            or_provider = self._get_openrouter()
            if or_provider:
                model = OpenRouterProvider.DEFAULT_MODEL
                result = or_provider.generate(prompt, model=model)
                if result.get("success"):
                    result["provider"] = "openrouter"
                    result["model"] = model
                    return result

            claude = self._get_claude()
            if claude:
                if task_type == "reasoning":
                    result = claude.generate_with_thinking(prompt)
                else:
                    model = ClaudeProvider.CODE_MODEL if task_type == "coder" else ClaudeProvider.DEFAULT_MODEL
                    result = claude.generate(prompt, model=model)
                if result.get("success"):
                    result["provider"] = "claude"
                    result["model"] = result.get("model", model)
                    return result

        else:
            # Censored-preferred (Claude first for coder, Ollama first for general)
            if task_type == "coder":
                claude = self._get_claude()
                if claude:
                    result = claude.generate(prompt, model=ClaudeProvider.CODE_MODEL)
                    if result.get("success"):
                        result["provider"] = "claude"
                        result["model"] = ClaudeProvider.CODE_MODEL
                        return result

            result = self._ollama_generate_best(prompt, task_type)
            if result.get("success"):
                result["provider"] = "ollama"
                result["model"] = result.get("model", self._pick_ollama_model(task_type))
                return result

            ds = self._get_deepseek()
            if ds:
                result = ds.generate(prompt, model=DeepSeekProvider.DEFAULT_MODEL)
                if result.get("success"):
                    result["provider"] = "deepseek"
                    result["model"] = DeepSeekProvider.DEFAULT_MODEL
                    return result

            or_provider = self._get_openrouter()
            if or_provider:
                result = or_provider.generate(prompt, model=OpenRouterProvider.DEFAULT_MODEL)
                if result.get("success"):
                    result["provider"] = "openrouter"
                    result["model"] = OpenRouterProvider.DEFAULT_MODEL
                    return result

            claude = self._get_claude()
            if claude:
                result = claude.generate(prompt, model=ClaudeProvider.DEFAULT_MODEL)
                if result.get("success"):
                    result["provider"] = "claude"
                    result["model"] = ClaudeProvider.DEFAULT_MODEL
                    return result

        # No LLM available
        status = self.ollama_status()
        return {
            "success": False,
            "response": "",
            "error": (locals().get("result") or {}).get("error", "No LLM available"),
            "provider": "none",
            "ollama_status": status,
            "fix_hint": self._build_fix_hint(status),
        }

    def route_chat(self, messages: list, task_type: str = "general") -> dict:
        """Chat completion — uncensored-first, task-type-aware routing."""
        result: dict = {}
        prefer_uncensored = self.get_prefer_uncensored()

        if prefer_uncensored:
            # Uncensored-first: Ollama -> DeepSeek -> Claude
            result = self._ollama_chat_best(messages, task_type)
            if result.get("success"):
                result["provider"] = "ollama"
                result["model"] = result.get("model", self._pick_ollama_model(task_type))
                return result

            ds = self._get_deepseek()
            if ds:
                model = DeepSeekProvider.REASONER_MODEL if task_type == "reasoning" else DeepSeekProvider.DEFAULT_MODEL
                result = ds.chat(messages, model=model, max_tokens=8192)
                if result.get("success"):
                    result["provider"] = "deepseek"
                    result["model"] = model
                    return result

            or_provider = self._get_openrouter()
            if or_provider:
                result = or_provider.chat(messages, model=OpenRouterProvider.DEFAULT_MODEL, max_tokens=8192)
                if result.get("success"):
                    result["provider"] = "openrouter"
                    result["model"] = OpenRouterProvider.DEFAULT_MODEL
                    return result

            claude = self._get_claude()
            if claude:
                if task_type == "reasoning":
                    model = ClaudeProvider.REASONING_MODEL
                    result = claude.chat(messages, model=model, max_tokens=ClaudeProvider.MAX_TOKENS_REASONING)
                else:
                    model = ClaudeProvider.CODE_MODEL if task_type == "coder" else ClaudeProvider.DEFAULT_MODEL
                    result = claude.chat(messages, model=model, max_tokens=8192)
                if result.get("success"):
                    result["provider"] = "claude"
                    result["model"] = model
                    return result

        else:
            # Censored-preferred
            if task_type == "coder":
                claude = self._get_claude()
                if claude:
                    result = claude.chat(messages, model=ClaudeProvider.CODE_MODEL, max_tokens=8192)
                    if result.get("success"):
                        result["provider"] = "claude"
                        result["model"] = ClaudeProvider.CODE_MODEL
                        return result

            result = self._ollama_chat_best(messages, task_type)
            if result.get("success"):
                result["provider"] = "ollama"
                result["model"] = result.get("model", self._pick_ollama_model(task_type))
                return result

            ds = self._get_deepseek()
            if ds:
                result = ds.chat(messages, model=DeepSeekProvider.DEFAULT_MODEL, max_tokens=8192)
                if result.get("success"):
                    result["provider"] = "deepseek"
                    result["model"] = DeepSeekProvider.DEFAULT_MODEL
                    return result

            or_provider = self._get_openrouter()
            if or_provider:
                result = or_provider.chat(messages, model=OpenRouterProvider.DEFAULT_MODEL, max_tokens=8192)
                if result.get("success"):
                    result["provider"] = "openrouter"
                    result["model"] = OpenRouterProvider.DEFAULT_MODEL
                    return result

            claude = self._get_claude()
            if claude:
                result = claude.chat(messages, model=ClaudeProvider.DEFAULT_MODEL, max_tokens=8192)
                if result.get("success"):
                    result["provider"] = "claude"
                    result["model"] = ClaudeProvider.DEFAULT_MODEL
                    return result

        status = self.ollama_status()
        return {
            "success": False,
            "message": {},
            "error": (locals().get("result") or {}).get("error", "No LLM available"),
            "provider": "none",
            "ollama_status": status,
            "fix_hint": self._build_fix_hint(status),
        }

    def ask(self, system: str, user: str, task_type: str = "general",
            raise_on_unavailable: bool = True) -> str:
        """Convenience: ask a question, return text answer.

        By default raises NoModelAvailableError if no provider is available
        so callers can distinguish failure from an empty response.
        """
        self._auto_pull_models()

        if system:
            messages = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ]
        else:
            messages = [{"role": "user", "content": user}]
        result = self.route_chat(messages, task_type=task_type)
        if result.get("success"):
            msg = result.get("message", {})
            return msg.get("content", "")

        if raise_on_unavailable:
            raise NoModelAvailableError(
                result.get("fix_hint", "No LLM available — start Ollama or set an API key"),
                ollama_status=result.get("ollama_status"),
            )
        return ""

    # ------------------------------------------------------------------
    # Ollama helpers
    # ------------------------------------------------------------------

    def _ollama_generate_best(self, prompt: str, task_type: str = "general") -> dict:
        preferred = self._pick_ollama_model(task_type)
        result = self.ollama.generate(prompt, model=preferred)
        result["model"] = preferred
        if result.get("success"):
            return result
        # Model not found — try whatever is installed
        status = self.ollama_status()
        for model in status.get("models", []):
            r = self.ollama.generate(prompt, model=model)
            r["model"] = model
            if r.get("success"):
                return r
        return result

    def _ollama_chat_best(self, messages: list, task_type: str = "general") -> dict:
        preferred = self._pick_ollama_model(task_type)
        result = self.ollama.chat(messages, model=preferred)
        result["model"] = preferred
        if result.get("success"):
            return result
        status = self.ollama_status()
        for model in status.get("models", []):
            r = self.ollama.chat(messages, model=model)
            r["model"] = model
            if r.get("success"):
                return r
        return result

    def _build_fix_hint(self, ollama_status: dict) -> str:
        """Build a user-friendly fix hint when no LLM is available."""
        lines = ["No AI model available. To fix this:"]
        if not ollama_status.get("running"):
            lines.append("1. Install Ollama from https://ollama.com/download")
            lines.append("2. Run 'ollama serve' in a terminal")
            lines.append("3. Pull an uncensored model: 'ollama pull dolphin-mistral'")
        elif not ollama_status.get("has_model"):
            lines.append("1. Pull an uncensored model: 'ollama pull dolphin-mistral'")
        lines.append("OR set a DeepSeek API key (cheap: $0.27/1M tokens) at https://platform.deepseek.com/")
        lines.append("OR set your Anthropic API key in MegaV Settings (Tools > Settings).")
        return "\n".join(lines)