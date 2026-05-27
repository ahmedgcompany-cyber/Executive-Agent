"""
Skill Engine — Registry.

Central in-memory store for all parsed skills with fast lookup APIs.

Public API:
    registry.search_by_keyword(query)     → list[Skill]
    registry.search_by_category(cat)      → list[Skill]
    registry.get_best_match(task)         → Optional[Skill]
    registry.get_by_id(skill_id)          → Optional[Skill]
    registry.all_skills()                 → list[Skill]
    registry.summary()                    → dict
"""

from __future__ import annotations

import re
from typing import Optional

from .parser import SkillParser
from .schemas import Skill, SkillStatus
from .utils import find_skills_root


class SkillRegistry:
    """Stores and indexes all parsed skills for fast retrieval."""

    # Common words that produce false-positive matches — penalized in scoring
    _STOPWORDS = frozenset({
        "create", "build", "make", "app", "application", "new", "get",
        "run", "use", "help", "want", "need", "like", "try", "open",
        "write", "show", "tell", "find", "give", "set", "start",
    })

    def __init__(self, parser: Optional[SkillParser] = None, auto_load: bool = True):
        """
        Args:
            parser:    Optional custom SkillParser (default: auto-locate skills dir).
            auto_load: If True, parse + index skills immediately on construction.
        """
        self._parser = parser or SkillParser()
        self._skills: list[Skill] = []
        self._by_id: dict[str, Skill] = {}
        self._by_category: dict[str, list[Skill]] = {}
        self._keyword_index: dict[str, list[str]] = {}  # token → [skill_id, ...]

        if auto_load:
            self.load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> int:
        """(Re)parse the skills directory and rebuild all indexes.

        Returns:
            Number of skills successfully loaded.
        """
        raw = self._parser.parse_all()
        self._skills = [s for s in raw if s.status == SkillStatus.ACTIVE]
        self._rebuild_indexes()
        return len(self._skills)

    def _rebuild_indexes(self):
        self._by_id = {s.id: s for s in self._skills}

        self._by_category = {}
        for s in self._skills:
            self._by_category.setdefault(s.category, []).append(s)

        self._keyword_index = {}
        for s in self._skills:
            for kw in s.trigger_keywords:
                for token in self._tokenise(kw):
                    self._keyword_index.setdefault(token, [])
                    if s.id not in self._keyword_index[token]:
                        self._keyword_index[token].append(s.id)

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        return [w for w in re.split(r"[\s\-_/,;]+", text.lower()) if len(w) > 2]

    # ------------------------------------------------------------------
    # Search API
    # ------------------------------------------------------------------

    def search_by_keyword(self, query: str) -> list[Skill]:
        """Return all skills that match at least one token in query.

        Results are sorted by descending match-count (most relevant first).
        """
        tokens = self._tokenise(query)
        hit_count: dict[str, int] = {}

        for token in tokens:
            for skill_id in self._keyword_index.get(token, []):
                hit_count[skill_id] = hit_count.get(skill_id, 0) + 1

        sorted_ids = sorted(hit_count, key=lambda i: hit_count[i], reverse=True)
        return [self._by_id[sid] for sid in sorted_ids if sid in self._by_id]

    def search_by_category(self, category: str) -> list[Skill]:
        """Return all active skills in the given category."""
        return list(self._by_category.get(category.lower(), []))

    def get_best_match(self, task: str) -> Optional[Skill]:
        """Return the single best-matching active skill for a task description.

        Uses keyword scoring with phrase-level bonuses.
        """
        results = self._score_all(task)
        if not results:
            return None
        top_skill, top_score = results[0]
        if top_score < 1.0:
            return None
        return top_skill

    def get_top_matches(self, task: str, n: int = 5, min_score: float = 1.0) -> list[Skill]:
        """Return the top-N best-matching skills above min_score."""
        results = self._score_all(task)
        return [s for s, sc in results[:n] if sc >= min_score]

    def get_by_id(self, skill_id: str) -> Optional[Skill]:
        return self._by_id.get(skill_id)

    def all_skills(self) -> list[Skill]:
        return list(self._skills)

    def categories(self) -> list[str]:
        return sorted(self._by_category.keys())

    # ------------------------------------------------------------------
    # Scoring engine
    # ------------------------------------------------------------------

    def _score_all(self, query: str) -> list[tuple[Skill, float]]:
        """Score every active skill against a query and return sorted list."""
        q = query.lower()
        tokens = self._tokenise(q)

        candidate_ids: set[str] = set()
        for token in tokens:
            candidate_ids.update(self._keyword_index.get(token, []))
        if not candidate_ids:
            return []

        scores: list[tuple[Skill, float]] = []
        for sid in candidate_ids:
            skill = self._by_id.get(sid)
            if not skill:
                continue
            score = self._score_skill(skill, q, tokens)
            scores.append((skill, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _score_skill(self, skill: Skill, q_lower: str, q_tokens: list[str]) -> float:
        """Compute relevance score for one skill."""
        score = 0.0

        for kw in skill.trigger_keywords:
            kw_lower = kw.lower()
            kw_tokens = self._tokenise(kw_lower)

            if len(kw_tokens) > 1:
                if kw_lower in q_lower:
                    score += 5.0        # exact multi-word phrase
                else:
                    hits = sum(1 for t in kw_tokens if t in q_lower)
                    if hits == len(kw_tokens):
                        score += 3.5    # all tokens present
                    elif hits > 0:
                        # Penalize partial matches dominated by stopwords
                        non_stop_hits = sum(1 for t in kw_tokens if t in q_lower and t not in self._STOPWORDS)
                        if non_stop_hits == 0:
                            score += hits * 0.15  # stopword-only partial match: heavily reduced
                        else:
                            score += hits * 0.6
            else:
                if kw_lower in q_lower:
                    # Single-stopword matches are nearly meaningless
                    if kw_lower in self._STOPWORDS:
                        score += 0.2
                    else:
                        score += 1.5    # single word exact
                elif any(kw_lower in tok for tok in q_tokens):
                    score += 0.5        # substring

        # Bonus: description overlap (but stopword overlap counts less)
        desc_words = set(self._tokenise(skill.description))
        q_word_set = set(q_tokens)
        overlap = len(desc_words & q_word_set)
        stop_overlap = len(desc_words & q_word_set & self._STOPWORDS)
        score += (overlap - stop_overlap) * 0.3 + stop_overlap * 0.05

        return round(score, 3)

    # ------------------------------------------------------------------
    # Runtime management
    # ------------------------------------------------------------------

    def set_active(self, skill_id: str, active: bool):
        """Enable or disable a skill at runtime."""
        skill = self._by_id.get(skill_id)
        if skill:
            skill.status = SkillStatus.ACTIVE if active else SkillStatus.INACTIVE
            if not active and skill_id in self._by_id:
                self._skills = [s for s in self._skills if s.id != skill_id]
                self._rebuild_indexes()

    # ------------------------------------------------------------------
    # Summary for UI
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        total = len(self._skills)
        cats  = self.categories()
        return {
            "total":          total,
            "active":         total,
            "categories":     cats,
            "category_count": len(cats),
            "keyword_tokens": len(self._keyword_index),
            "skills_root":    str(self._parser._root),
        }
