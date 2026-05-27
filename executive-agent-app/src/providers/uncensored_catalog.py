"""Curated catalog of the best uncensored/abliterated/heretic models for Ollama.

This replaces the hardcoded OLLAMA_MODELS dict and setup wizard MODELS list
with a curated, uncensored-first model catalog organized by task type and
VRAM tier.  Models are sorted so uncensored variants always appear before
censored fallbacks.

Abliterated = refusal direction surgically removed via linear algebra
Heretic    = automated abliteration tool that co-minimizes refusals + KL divergence
Uncensored = fine-tuned on compliant datasets (Dolphin, Wizard, etc.)
"""


class UncensoredModelCatalog:
    """Defines the best uncensored models available via Ollama, organized by
    task type and hardware requirements."""

    # VRAM tiers: 1 = 12GB+, 2 = 8-12GB, 3 = 4-8GB
    MODELS = [
        # ── Tier 1: Maximum capability (12GB+ VRAM) ──────────────────────
        {
            "id": "richardyoung/qwen3-14b-abliterated:Q4_K_M",
            "name": "Qwen3 14B Abliterated",
            "size_gb": 9.0,
            "vram_tier": 1,
            "task_types": ["general", "coder", "reasoning"],
            "tag": "recommended",
            "family": "qwen3",
            "uncensored": True,
        },
        {
            "id": "richardyoung/deepseek-r1-32b-uncensored",
            "name": "DeepSeek R1 32B Uncensored",
            "size_gb": 19.0,
            "vram_tier": 1,
            "task_types": ["reasoning", "general"],
            "tag": "reasoning",
            "family": "deepseek",
            "uncensored": True,
        },
        # ── Tier 2: Good capability (8-12GB VRAM) ─────────────────────────
        {
            "id": "huihui_ai/dolphin3-abliterated",
            "name": "Dolphin 3 Abliterated (8B)",
            "size_gb": 4.9,
            "vram_tier": 2,
            "task_types": ["general", "coder", "fast"],
            "tag": "popular",
            "family": "dolphin",
            "uncensored": True,
        },
        {
            "id": "hf.co/brillio-ai/Mistral-Nemo-12B-Uncensored-Heretic:Q4_K_M",
            "name": "Mistral Nemo 12B Heretic",
            "size_gb": 8.0,
            "vram_tier": 2,
            "task_types": ["general", "coder"],
            "tag": "heretic",
            "family": "mistral",
            "uncensored": True,
        },
        {
            "id": "hf.co/bartowski/Llama-3.3-8B-Instruct-Thinking-Heretic:Q4_K_M",
            "name": "Llama 3.3 8B Thinking Heretic",
            "size_gb": 6.0,
            "vram_tier": 2,
            "task_types": ["general", "reasoning"],
            "tag": "heretic",
            "family": "llama",
            "uncensored": True,
        },
        # ── Tier 3: Lightweight (4-8GB VRAM) ──────────────────────────────
        {
            "id": "dolphin-mistral",
            "name": "Dolphin Mistral 7B",
            "size_gb": 4.1,
            "vram_tier": 3,
            "task_types": ["general", "fast"],
            "tag": "uncensored",
            "family": "dolphin",
            "uncensored": True,
        },
        {
            "id": "R4C3R/qwen2.5-3b-heretic",
            "name": "Qwen 2.5 3B Heretic",
            "size_gb": 2.0,
            "vram_tier": 3,
            "task_types": ["fast", "general"],
            "tag": "lightweight",
            "family": "qwen",
            "uncensored": True,
        },
        # ── Censored fallbacks (clearly labeled) ──────────────────────────
        {
            "id": "deepseek-coder-v2",
            "name": "DeepSeek Coder V2 (standard)",
            "size_gb": 5.0,
            "vram_tier": 2,
            "task_types": ["coder"],
            "tag": "censored",
            "family": "deepseek",
            "uncensored": False,
        },
        {
            "id": "llama3.2",
            "name": "Llama 3.2 (standard)",
            "size_gb": 2.0,
            "vram_tier": 3,
            "task_types": ["general", "fast"],
            "tag": "censored",
            "family": "llama",
            "uncensored": False,
        },
        {
            "id": "mistral",
            "name": "Mistral 7B (standard)",
            "size_gb": 4.1,
            "vram_tier": 3,
            "task_types": ["general", "fast"],
            "tag": "censored",
            "family": "mistral",
            "uncensored": False,
        },
        # ── Vision models ─────────────────────────────────────────────────
        {
            "id": "llava",
            "name": "LLaVA (vision)",
            "size_gb": 4.5,
            "vram_tier": 2,
            "task_types": ["vision"],
            "tag": "vision",
            "family": "llava",
            "uncensored": False,
        },
    ]

    # Auto-pull priority: these get pulled in background when Ollama is running
    AUTO_PULL_IDS = [
        "huihui_ai/dolphin3-abliterated",                     # best general uncensored (compact)
        "richardyoung/qwen3-14b-abliterated:Q4_K_M",         # best quality-to-size
    ]

    # Fallback model when nothing else is available
    FALLBACK_ID = "dolphin-mistral"

    # ── Query methods ────────────────────────────────────────────────────

    def get_models_for_task(self, task_type: str, prefer_uncensored: bool = True) -> list[dict]:
        """Return models suitable for a task type, uncensored first if preferred."""
        matching = [m for m in self.MODELS if task_type in m["task_types"]]
        if prefer_uncensored:
            matching.sort(key=lambda m: (0 if m["uncensored"] else 1, m["vram_tier"], m["size_gb"]))
        else:
            matching.sort(key=lambda m: (m["vram_tier"], m["size_gb"]))
        return matching

    def get_models_by_tier(self, vram_tier: int) -> list[dict]:
        """Return all models for a given VRAM tier."""
        return [m for m in self.MODELS if m["vram_tier"] == vram_tier]

    def get_wizard_models(self) -> list[dict]:
        """Return models for the setup wizard — uncensored first, manageable count."""
        # Pick top uncensored per tier + 1-2 censored fallbacks
        picks = []
        seen_families = set()
        for m in sorted(self.MODELS, key=lambda m: (0 if m["uncensored"] else 1, m["vram_tier"], m["size_gb"])):
            # Limit to 8 models, at most 1 per family for uncensored
            if m["uncensored"] and m["family"] in seen_families:
                continue
            picks.append(m)
            seen_families.add(m["family"])
            if len(picks) >= 8:
                break
        return picks

    def find_best_match(self, installed_name: str, task_type: str = "general") -> dict | None:
        """Given an installed model name from /api/tags, find the best catalog match."""
        installed_lower = installed_name.lower()
        # Exact match first
        for m in self.MODELS:
            if m["id"].lower() == installed_lower:
                return m
        # Prefix match (handles tags like :Q4_K_M)
        for m in self.MODELS:
            if installed_lower.startswith(m["id"].lower().split(":")[0]):
                return m
            if m["id"].lower().split(":")[0].startswith(installed_lower):
                return m
        # Family match
        for m in self.get_models_for_task(task_type):
            if m["family"].lower() in installed_lower:
                return m
        return None

    def get_auto_pull_list(self, vram_tier: int = 1) -> list[str]:
        """Return model IDs to auto-pull, filtered by what fits in the user's VRAM."""
        pulls = []
        for mid in self.AUTO_PULL_IDS:
            model = self._get_by_id(mid)
            if model and model["vram_tier"] <= vram_tier:
                pulls.append(mid)
        return pulls

    def is_uncensored(self, model_name: str) -> bool:
        """Check if a model name corresponds to an uncensored model in the catalog."""
        match = self.find_best_match(model_name)
        return match["uncensored"] if match else False

    def get_all_uncensored(self) -> list[dict]:
        """Return all uncensored models."""
        return [m for m in self.MODELS if m["uncensored"]]

    def _get_by_id(self, model_id: str) -> dict | None:
        for m in self.MODELS:
            if m["id"] == model_id:
                return m
        return None