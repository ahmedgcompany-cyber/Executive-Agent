"""
Agency Library — indexes, loads, and searches the 190+ agent personalities
copied from agency-agents-main into src/agents/agency/.

Usage:
    lib = get_agency_library()
    agent = lib.find_best_agent("design a landing page")
    prompt = lib.get_prompt(agent["id"])
    agents = lib.list_by_category("marketing")
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_AGENCY_DIR = Path(__file__).parent / "agency"

# ---------------------------------------------------------------------------
# Category → label + typical tasks (used for smart routing)
# ---------------------------------------------------------------------------

CATEGORY_META: dict[str, dict] = {
    "engineering": {
        "label": "Engineering",
        "emoji": "💻",
        "keywords": ["code", "build", "develop", "architect", "backend", "frontend", "api",
                     "database", "devops", "security", "mobile", "ai", "ml", "engineer",
                     "debug", "refactor", "deploy", "ci", "cd", "docker", "kubernetes"],
    },
    "design": {
        "label": "Design",
        "emoji": "🎨",
        "keywords": ["design", "ui", "ux", "brand", "visual", "logo", "prototype", "wireframe",
                     "figma", "style", "interface", "typography", "color", "mockup"],
    },
    "marketing": {
        "label": "Marketing",
        "emoji": "📢",
        "keywords": ["marketing", "campaign", "seo", "content", "social", "growth", "viral",
                     "tiktok", "instagram", "twitter", "linkedin", "youtube", "email marketing",
                     "ads", "audience", "engagement", "funnel", "conversion"],
    },
    "sales": {
        "label": "Sales",
        "emoji": "💼",
        "keywords": ["sales", "deal", "pipeline", "prospect", "proposal", "account",
                     "outbound", "discovery", "close", "crm", "revenue", "client"],
    },
    "specialized": {
        "label": "Specialized",
        "emoji": "⭐",
        "keywords": ["orchestrate", "workflow", "automate", "compliance", "legal", "hr",
                     "onboarding", "customer service", "document", "report", "data", "blockchain"],
    },
    "testing": {
        "label": "Testing & QA",
        "emoji": "🧪",
        "keywords": ["test", "qa", "quality", "bug", "validation", "performance", "api test",
                     "accessibility", "audit", "evidence", "verify", "benchmark"],
    },
    "project-management": {
        "label": "Project Management",
        "emoji": "📋",
        "keywords": ["project", "sprint", "agile", "plan", "milestone", "timeline", "jira",
                     "schedule", "coordinate", "task", "prioritize", "roadmap", "scope"],
    },
    "product": {
        "label": "Product",
        "emoji": "🚀",
        "keywords": ["product", "feature", "user story", "backlog", "mvp", "trend", "feedback",
                     "research", "market fit", "product manager", "roadmap"],
    },
    "support": {
        "label": "Support & Ops",
        "emoji": "🛠️",
        "keywords": ["support", "operations", "infrastructure", "analytics", "report",
                     "finance", "budget", "compliance", "monitor", "incident"],
    },
    "finance": {
        "label": "Finance",
        "emoji": "💰",
        "keywords": ["finance", "financial", "accounting", "tax", "investment", "budget",
                     "revenue", "profit", "forecast", "bookkeeping", "balance sheet"],
    },
    "academic": {
        "label": "Academic",
        "emoji": "🎓",
        "keywords": ["research", "academic", "history", "psychology", "geography",
                     "anthropology", "narrative", "analysis", "study", "thesis"],
    },
    "game-development": {
        "label": "Game Development",
        "emoji": "🎮",
        "keywords": ["game", "unity", "unreal", "godot", "roblox", "blender", "shader",
                     "multiplayer", "level", "narrative", "audio", "3d", "vr", "ar"],
    },
    "paid-media": {
        "label": "Paid Media",
        "emoji": "📊",
        "keywords": ["paid", "ppc", "ads", "programmatic", "search", "display", "creative",
                     "tracking", "attribution", "bid", "cpm", "cpc", "roas", "media buy"],
    },
    "spatial-computing": {
        "label": "Spatial Computing",
        "emoji": "🥽",
        "keywords": ["xr", "ar", "vr", "spatial", "visionos", "macos", "metal", "immersive",
                     "3d interface", "apple vision", "mixed reality"],
    },
}


# ---------------------------------------------------------------------------
# YAML-like frontmatter parser (no external deps)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Extract YAML frontmatter and body from a markdown agent file."""
    meta: dict[str, str] = {}
    body = text

    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if m:
        fm_text, body = m.group(1), m.group(2)
        for line in fm_text.splitlines():
            kv = re.match(r"^(\w[\w-]*):\s*(.+)$", line)
            if kv:
                meta[kv.group(1)] = kv.group(2).strip().strip('"\'')
    return meta, body


# ---------------------------------------------------------------------------
# AgentRecord
# ---------------------------------------------------------------------------

class AgentRecord:
    """Holds metadata and prompt for a single agent."""

    __slots__ = (
        "id", "name", "description", "category", "emoji", "color",
        "vibe", "file_path", "_prompt",
    )

    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        category: str,
        emoji: str,
        color: str,
        vibe: str,
        file_path: Path,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.category = category
        self.emoji = emoji
        self.color = color
        self.vibe = vibe
        self.file_path = file_path
        self._prompt: Optional[str] = None

    @property
    def prompt(self) -> str:
        """Lazy-load the full agent prompt."""
        if self._prompt is None:
            self._prompt = self.file_path.read_text(encoding="utf-8", errors="replace")
        return self._prompt

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "emoji": self.emoji,
            "color": self.color,
            "vibe": self.vibe,
        }


# ---------------------------------------------------------------------------
# AgencyLibrary
# ---------------------------------------------------------------------------

class AgencyLibrary:
    """
    Loads and indexes all agent personalities from src/agents/agency/.
    Provides search, category browsing, and prompt retrieval.
    """

    def __init__(self, agency_dir: Path = _AGENCY_DIR):
        self._dir = agency_dir
        self._agents: dict[str, AgentRecord] = {}   # id → AgentRecord
        self._by_category: dict[str, list[str]] = {}  # category → [ids]
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._load_all()
        self._loaded = True

    def _load_all(self):
        """Walk agency dir and build index."""
        if not self._dir.exists():
            return

        for md_file in sorted(self._dir.rglob("*.md")):
            # Skip strategy/examples sub-dirs
            parts = md_file.relative_to(self._dir).parts
            if parts[0] in ("strategy", "examples", "integrations", "scripts"):
                continue

            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                meta, _body = _parse_frontmatter(text)

                category = parts[0]  # e.g. "engineering"
                file_stem = md_file.stem  # e.g. "engineering-backend-architect"
                agent_id = file_stem  # use filename as ID

                # Prefer frontmatter name, else derive from filename
                name = meta.get("name") or " ".join(
                    w.title() for w in agent_id.replace("-", " ").split()
                )
                description = meta.get("description", "")
                emoji = meta.get("emoji", CATEGORY_META.get(category, {}).get("emoji", "🤖"))
                color = meta.get("color", "blue")
                vibe = meta.get("vibe", "")

                rec = AgentRecord(
                    id=agent_id,
                    name=name,
                    description=description,
                    category=category,
                    emoji=emoji,
                    color=color,
                    vibe=vibe,
                    file_path=md_file,
                )
                self._agents[agent_id] = rec

                if category not in self._by_category:
                    self._by_category[category] = []
                self._by_category[category].append(agent_id)

            except Exception:
                continue

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        """Return an AgentRecord by ID (filename stem)."""
        self._ensure_loaded()
        return self._agents.get(agent_id)

    def get_prompt(self, agent_id: str) -> Optional[str]:
        """Return the full markdown prompt for an agent."""
        rec = self.get(agent_id)
        return rec.prompt if rec else None

    def list_by_category(self, category: str) -> list[dict[str, Any]]:
        """Return agent dicts for a category."""
        self._ensure_loaded()
        ids = self._by_category.get(category, [])
        return [self._agents[i].to_dict() for i in ids if i in self._agents]

    def all_agents(self) -> list[dict[str, Any]]:
        """Return all agents as dicts."""
        self._ensure_loaded()
        return [r.to_dict() for r in self._agents.values()]

    def categories(self) -> list[str]:
        """Return known categories (those with agents loaded)."""
        self._ensure_loaded()
        return sorted(self._by_category.keys())

    def agent_count(self) -> int:
        self._ensure_loaded()
        return len(self._agents)

    # ------------------------------------------------------------------
    # Search & routing
    # ------------------------------------------------------------------

    def find_best_agent(
        self,
        query: str,
        category: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Find the best matching agent for a query.

        Args:
            query: User's natural-language request
            category: Optional category to restrict search

        Returns:
            Agent dict, or None if no match found
        """
        self._ensure_loaded()
        q = query.lower()

        candidates = list(self._by_category.get(category, [])) if category else list(self._agents.keys())

        best_id: Optional[str] = None
        best_score = -1

        for agent_id in candidates:
            rec = self._agents.get(agent_id)
            if not rec:
                continue
            score = self._score_agent(rec, q)
            if score > best_score:
                best_score = score
                best_id = agent_id

        if best_id and best_score > 0:
            return self._agents[best_id].to_dict()
        return None

    def search(self, query: str, top_n: int = 5) -> list[dict[str, Any]]:
        """Return top-N matching agents across all categories."""
        self._ensure_loaded()
        q = query.lower()

        scored: list[tuple[float, str]] = []
        for agent_id, rec in self._agents.items():
            score = self._score_agent(rec, q)
            if score > 0:
                scored.append((score, agent_id))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._agents[aid].to_dict() for _, aid in scored[:top_n]]

    def best_category_for_query(self, query: str) -> Optional[str]:
        """Return the category that best matches a query."""
        q = query.lower()
        best_cat: Optional[str] = None
        best_score = 0

        for cat, meta in CATEGORY_META.items():
            score = sum(1 for kw in meta["keywords"] if kw in q)
            if score > best_score:
                best_score = score
                best_cat = cat

        return best_cat if best_score > 0 else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_agent(self, rec: AgentRecord, query: str) -> float:
        """Score relevance of an agent to a query."""
        score = 0.0

        # Match in agent ID (filename)
        for token in query.split():
            if token and len(token) > 2 and token in rec.id:
                score += 2.0

        # Match in description
        if rec.description:
            desc_l = rec.description.lower()
            for token in query.split():
                if token and len(token) > 2 and token in desc_l:
                    score += 1.5

        # Match in name
        if rec.name:
            name_l = rec.name.lower()
            for token in query.split():
                if token and len(token) > 2 and token in name_l:
                    score += 1.0

        # Category keyword bonus
        cat_meta = CATEGORY_META.get(rec.category, {})
        for kw in cat_meta.get("keywords", []):
            if kw in query:
                score += 0.5

        return score


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_library_instance: Optional[AgencyLibrary] = None


def get_agency_library() -> AgencyLibrary:
    """Return the global AgencyLibrary singleton."""
    global _library_instance
    if _library_instance is None:
        _library_instance = AgencyLibrary()
    return _library_instance
