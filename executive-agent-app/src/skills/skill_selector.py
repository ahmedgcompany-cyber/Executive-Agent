"""
Skill Selector — keyword-scoring engine that picks the best skill(s) for a
user query WITHOUT requiring an LLM call.

Scoring algorithm
-----------------
For each candidate skill (those sharing at least one keyword token with the
query), compute a weighted score:

  score = exact_phrase_hits * 4
        + multi_word_phrase_hits * 3
        + single_word_token_hits * 1

A minimum score threshold filters out weak matches.  The top-N results
are returned ranked by score descending.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .skill_registry import SkillRegistry


@dataclass
class SkillMatch:
    """A single skill match with its score and metadata."""
    skill_id: str
    skill_name: str
    score: float
    matched_keywords: list[str] = field(default_factory=list)
    category: str = ""
    execution_type: str = ""
    agent_affinity: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "skill_id":        self.skill_id,
            "skill_name":      self.skill_name,
            "score":           self.score,
            "matched_keywords": self.matched_keywords,
            "category":        self.category,
            "execution_type":  self.execution_type,
            "agent_affinity":  self.agent_affinity,
        }


class SkillSelector:
    """Selects the most relevant skill(s) for a user input query."""

    # Minimum score to be considered a valid match
    MIN_SCORE = 2.0
    # Maximum number of skills to return
    MAX_RESULTS = 5

    # Common words that produce false positives — penalized
    _STOPWORDS = frozenset({
        "create", "build", "make", "app", "application", "new", "get",
        "run", "use", "help", "want", "need", "like", "try", "open",
        "write", "show", "tell", "find", "give", "set", "start",
    })

    # Coding task patterns — skip skill interception entirely
    _SKIP_PATTERNS = (
        re.compile(r"\b(write|create|build|make|develop|code|implement)\b.{0,30}\b(script|program|function|class|method|app|application|tool|bot|game|calculator|converter|parser|scraper|server|api|database|algorithm|widget|snippet|module|package|library)\b", re.I),
        re.compile(r"\b(fix|debug|solve|troubleshoot|repair|patch)\b.{0,20}\b(bug|error|issue|problem|code|script|program)\b", re.I),
        re.compile(r"\b(explain|understand|analyze|review|refactor)\b.{0,20}\b(code|function|class|method|script|program|algorithm)\b", re.I),
    )

    def __init__(self, registry: SkillRegistry):
        self._registry = registry

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def select(
        self,
        query: str,
        agent_hint: Optional[str] = None,
        top_n: int = 1,
    ) -> list[SkillMatch]:
        """Select the best matching skill(s) for a query.

        Args:
            query:      Raw user input text.
            agent_hint: Optional agent name (e.g. "coder") to boost skills
                        that have affinity with that agent.
            top_n:      Maximum number of skills to return.

        Returns:
            Ranked list of SkillMatch objects (highest score first).
            Empty list if no skill meets the minimum threshold.
        """
        query_lower = query.lower()

        # Skip coding/development tasks — these go to agents, not skills
        for pat in self._SKIP_PATTERNS:
            if pat.search(query_lower):
                return []

        candidates = self._registry.candidates_for_query(query_lower)
        if not candidates:
            return []

        # Score each unique candidate
        scored: dict[str, float] = {}
        matched_kws: dict[str, list[str]] = {}

        unique_candidates = list(dict.fromkeys(candidates))  # preserve order, dedupe
        for skill_id in unique_candidates:
            skill = self._registry.get_by_id(skill_id)
            if not skill or not skill.get("active", True):
                continue
            score, kws = self._score_skill(skill, query_lower, agent_hint)
            if score > 0:
                scored[skill_id] = score
                matched_kws[skill_id] = kws

        # Filter by minimum threshold
        passing = [(sid, sc) for sid, sc in scored.items() if sc >= self.MIN_SCORE]
        if not passing:
            return []

        # Sort descending
        passing.sort(key=lambda x: x[1], reverse=True)

        results = []
        for skill_id, score in passing[: min(top_n, self.MAX_RESULTS)]:
            skill = self._registry.get_by_id(skill_id)
            results.append(SkillMatch(
                skill_id=skill_id,
                skill_name=skill.get("name", skill_id),
                score=round(score, 2),
                matched_keywords=matched_kws.get(skill_id, []),
                category=skill.get("category", ""),
                execution_type=skill.get("execution_type", "prompt"),
                agent_affinity=skill.get("agent_affinity", []),
            ))

        return results

    def best_match(
        self,
        query: str,
        agent_hint: Optional[str] = None,
    ) -> Optional[SkillMatch]:
        """Return the single best-matching skill, or None."""
        results = self.select(query, agent_hint=agent_hint, top_n=1)
        return results[0] if results else None

    def select_for_agent(self, query: str, agent_name: str, top_n: int = 3) -> list[SkillMatch]:
        """Return best skills for a specific agent context."""
        return self.select(query, agent_hint=agent_name, top_n=top_n)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_skill(
        self,
        skill: dict,
        query_lower: str,
        agent_hint: Optional[str],
    ) -> tuple[float, list[str]]:
        """Compute relevance score for one skill against the query.

        Returns:
            (score, list_of_matched_keyword_strings)
        """
        score = 0.0
        matched: list[str] = []

        keywords: list[str] = skill.get("trigger_keywords", [])

        for kw in keywords:
            kw_lower = kw.lower()
            tokens = re.split(r"[\s\-_/]+", kw_lower)

            if len(tokens) > 1:
                # Multi-word phrase
                if kw_lower in query_lower:
                    score += 4.0       # exact phrase match
                    matched.append(kw)
                else:
                    # Count how many tokens appear
                    hits = sum(1 for t in tokens if t and t in query_lower)
                    if hits == len(tokens):
                        score += 3.0   # all tokens present (not necessarily adjacent)
                        matched.append(kw)
                    elif hits > 0:
                        # Penalize stopword-only partial matches
                        non_stop_hits = sum(1 for t in tokens if t and t in query_lower and t not in self._STOPWORDS)
                        if non_stop_hits == 0:
                            score += hits * 0.1  # stopword-only: heavily reduced
                        else:
                            score += hits * 0.5
            else:
                # Single word
                if kw_lower in query_lower:
                    if kw_lower in self._STOPWORDS:
                        score += 0.2  # stopword single-word match: nearly meaningless
                    else:
                        score += 1.0
                        matched.append(kw)

        # Agent affinity boost
        if agent_hint and agent_hint in skill.get("agent_affinity", []):
            score *= 1.3

        return score, matched

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    def rank_all(self, query: str) -> list[SkillMatch]:
        """Score and rank ALL active skills. Used for debugging / UI display."""
        return self.select(query, top_n=self.MAX_RESULTS)

    def skills_for_category(self, category: str) -> list[dict]:
        """Return all active skills in a category (no scoring)."""
        return self._registry.get_by_category(category)
