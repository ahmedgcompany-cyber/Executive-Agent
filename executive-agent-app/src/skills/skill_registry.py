"""
Skill Registry — central index of all 31 skills.

Loads skill definitions, reads SKILL.md context files, and provides
fast lookup APIs by id, keyword, category, and agent affinity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .skill_definitions import ALL_SKILLS, SKILL_BY_ID, SKILLS_BY_CATEGORY, SKILLS_BY_AGENT, SKILLS_ROOT


class SkillRegistry:
    """Central registry for all available skills."""

    def __init__(self, skills_root: Optional[Path] = None):
        """Initialise registry and build keyword index.

        Args:
            skills_root: Override root path for the skills collection.
                         Defaults to the path defined in skill_definitions.py.
        """
        self._root = Path(skills_root) if skills_root else SKILLS_ROOT
        self._skills: list[dict] = [dict(s) for s in ALL_SKILLS]  # shallow copy
        self._by_id: dict[str, dict] = {s["id"]: s for s in self._skills}

        # Inject SKILL.md context text into each skill definition
        self._load_skill_contexts()

        # Build inverted keyword index: keyword_token -> list[skill_id]
        self._keyword_index: dict[str, list[str]] = {}
        self._build_keyword_index()

    # ------------------------------------------------------------------
    # Context loading
    # ------------------------------------------------------------------

    def _load_skill_contexts(self):
        """Read SKILL.md (or README.md) from each skill folder and attach
        the text as skill["context_text"] for use as LLM system context."""
        for skill in self._skills:
            folder = self._root / skill["folder"]
            context_text = ""
            for candidate in ("SKILL.md", "skill.md", "README.md", "readme.md"):
                md_path = folder / candidate
                if md_path.exists():
                    try:
                        context_text = md_path.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        pass
                    break
            skill["context_text"] = context_text
            skill["skill_folder_exists"] = folder.exists()

    # ------------------------------------------------------------------
    # Keyword index
    # ------------------------------------------------------------------

    def _build_keyword_index(self):
        """Build inverted index mapping every trigger keyword token to skill ids."""
        for skill in self._skills:
            if not skill.get("active", True):
                continue
            for kw in skill.get("trigger_keywords", []):
                tokens = self._tokenise(kw)
                for token in tokens:
                    self._keyword_index.setdefault(token, [])
                    if skill["id"] not in self._keyword_index[token]:
                        self._keyword_index[token].append(skill["id"])

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        """Split phrase into individual lowercase word tokens."""
        return [w for w in re.split(r"[\s\-_/]+", text.lower()) if len(w) > 2]

    # ------------------------------------------------------------------
    # Lookup APIs
    # ------------------------------------------------------------------

    def get_by_id(self, skill_id: str) -> Optional[dict]:
        """Return skill definition by id, or None."""
        return self._by_id.get(skill_id)

    def get_all(self, active_only: bool = True) -> list[dict]:
        """Return all skill definitions, optionally filtered to active only."""
        if active_only:
            return [s for s in self._skills if s.get("active", True)]
        return list(self._skills)

    def get_by_category(self, category: str) -> list[dict]:
        """Return skills in a given category."""
        return [s for s in self._skills if s.get("category") == category and s.get("active", True)]

    def get_by_agent(self, agent_name: str) -> list[dict]:
        """Return skills that list agent_name in their agent_affinity."""
        return [
            s for s in self._skills
            if agent_name in s.get("agent_affinity", []) and s.get("active", True)
        ]

    def get_categories(self) -> list[str]:
        """Return sorted unique category names."""
        return sorted({s["category"] for s in self._skills})

    def candidates_for_query(self, query: str) -> list[str]:
        """Return skill ids that share at least one keyword token with query.

        Args:
            query: Raw user input text.

        Returns:
            List of candidate skill ids (may contain duplicates — caller scores them).
        """
        tokens = self._tokenise(query)
        candidates: list[str] = []
        for token in tokens:
            candidates.extend(self._keyword_index.get(token, []))
        return candidates

    def set_active(self, skill_id: str, active: bool):
        """Enable or disable a skill at runtime."""
        skill = self._by_id.get(skill_id)
        if skill:
            skill["active"] = active
            # Rebuild index to reflect change
            self._keyword_index = {}
            self._build_keyword_index()

    # ------------------------------------------------------------------
    # Script helpers
    # ------------------------------------------------------------------

    def script_path(self, skill_id: str, script_relative: str) -> Path:
        """Resolve absolute path to a skill script.

        Args:
            skill_id: Skill identifier.
            script_relative: Relative script path from the skill's folder.

        Returns:
            Absolute Path object.
        """
        skill = self._by_id.get(skill_id)
        if not skill:
            raise KeyError(f"Unknown skill id: {skill_id!r}")
        return self._root / skill["folder"] / script_relative

    def context_text(self, skill_id: str) -> str:
        """Return SKILL.md content for the given skill, or empty string."""
        skill = self._by_id.get(skill_id)
        if not skill:
            return ""
        return skill.get("context_text", "")

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return a summary dict for display in the Skills tab."""
        total = len(self._skills)
        active = sum(1 for s in self._skills if s.get("active", True))
        with_context = sum(1 for s in self._skills if s.get("context_text"))
        folders_found = sum(1 for s in self._skills if s.get("skill_folder_exists"))
        categories = self.get_categories()

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "with_context": with_context,
            "folders_found": folders_found,
            "categories": categories,
            "keyword_tokens": len(self._keyword_index),
        }
