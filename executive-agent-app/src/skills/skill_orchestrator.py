"""
Skill Orchestrator — chains multiple skills together and manages
the full skill lifecycle: detect → select → execute → chain.

Entry point for the agent loop:  SkillOrchestrator.run(user_input)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .skill_registry import SkillRegistry
from .skill_selector import SkillSelector, SkillMatch
from .skill_engine import SkillEngine


@dataclass
class OrchestrationResult:
    """Result of one or more skill executions."""
    success: bool
    summary: str
    skill_results: list[dict] = field(default_factory=list)
    skills_used: list[str] = field(default_factory=list)
    total_elapsed_s: float = 0.0
    chained: bool = False

    def to_dict(self) -> dict:
        return {
            "success":        self.success,
            "summary":        self.summary,
            "skill_results":  self.skill_results,
            "skills_used":    self.skills_used,
            "total_elapsed_s": self.total_elapsed_s,
            "chained":        self.chained,
        }


class SkillOrchestrator:
    """High-level orchestrator that ties selector + engine together.

    Typical usage in agent loop::

        orchestrator = SkillOrchestrator(registry, model_router, progress_cb)
        result = orchestrator.run(user_input, agent_hint="content")
        if result.success:
            # skill handled the request
            ...
    """

    # Confidence threshold: only intercept with a skill if top score is above this
    CONFIDENCE_THRESHOLD = 3.5

    def __init__(
        self,
        registry: SkillRegistry,
        model_router: Optional[Any] = None,
        progress_cb: Optional[Callable[[str], None]] = None,
    ):
        self._registry = registry
        self._selector = SkillSelector(registry)
        self._engine = SkillEngine(registry, model_router, progress_cb)
        self._emit: Callable[[str], None] = progress_cb or (lambda _: None)

        # Chain rules: if skill A is selected, also run these skills after it
        self._chain_rules: dict[str, list[str]] = {
            "tailored-resume-generator": ["brand-guidelines"],
            "content-research-writer":   ["theme-factory"],
            "canvas-design":             ["brand-guidelines"],
            "competitive-ads-extractor": ["lead-research-assistant"],
            "mcp-builder":               ["webapp-testing"],
        }

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def should_intercept(self, user_input: str, agent_hint: Optional[str] = None) -> bool:
        """Return True if a skill should handle this input (not a regular agent task).

        Args:
            user_input:  Raw user query.
            agent_hint:  Current agent name (for affinity boosting).

        Returns:
            True if a skill match exceeds the confidence threshold.
        """
        match = self._selector.best_match(user_input, agent_hint=agent_hint)
        return match is not None and match.score >= self.CONFIDENCE_THRESHOLD

    def run(
        self,
        user_input: str,
        agent_hint: Optional[str] = None,
        extra_context: Optional[dict] = None,
        allow_chain: bool = True,
    ) -> OrchestrationResult:
        """Select and execute the best skill(s) for the given input.

        Args:
            user_input:    User's request text.
            agent_hint:    Agent name for affinity boosting.
            extra_context: Extra dict passed through to the engine.
            allow_chain:   Whether to execute auto-chained skills.

        Returns:
            OrchestrationResult with success status and combined summary.
        """
        t0 = time.time()

        # --- Step 1: Select best skill ---
        match = self._selector.best_match(user_input, agent_hint=agent_hint)
        if not match or match.score < self.CONFIDENCE_THRESHOLD:
            return OrchestrationResult(
                success=False,
                summary="No skill matched this request.",
            )

        self._emit(f"Skill matched: '{match.skill_name}' (score={match.score})")

        # --- Step 2: Execute primary skill ---
        primary_result = self._engine.execute(match, user_input, extra_context)
        all_results = [primary_result]
        skills_used = [match.skill_id]

        # --- Step 3: Auto-chain follow-up skills ---
        if allow_chain and primary_result.get("success"):
            chain_ids = self._chain_rules.get(match.skill_id, [])
            for chain_id in chain_ids:
                chain_skill = self._registry.get_by_id(chain_id)
                if not chain_skill or not chain_skill.get("active", True):
                    continue
                self._emit(f"  Auto-chaining: {chain_skill['name']}")
                # Pass primary result text as additional context
                chain_input = (
                    f"{user_input}\n\n"
                    f"[Previous skill '{match.skill_name}' produced:]\n"
                    f"{primary_result.get('result', '')[:1500]}"
                )
                chain_match = SkillMatch(
                    skill_id=chain_id,
                    skill_name=chain_skill["name"],
                    score=1.0,
                    category=chain_skill.get("category", ""),
                    execution_type=chain_skill.get("execution_type", "prompt"),
                    agent_affinity=chain_skill.get("agent_affinity", []),
                )
                chain_result = self._engine.execute(chain_match, chain_input, extra_context)
                all_results.append(chain_result)
                skills_used.append(chain_id)

        # --- Step 4: Build summary ---
        total_elapsed = round(time.time() - t0, 2)
        success = primary_result.get("success", False)
        summary = self._build_summary(all_results, skills_used)

        return OrchestrationResult(
            success=success,
            summary=summary,
            skill_results=all_results,
            skills_used=skills_used,
            total_elapsed_s=total_elapsed,
            chained=len(all_results) > 1,
        )

    def run_skill(
        self,
        skill_id: str,
        user_input: str,
        extra_context: Optional[dict] = None,
    ) -> OrchestrationResult:
        """Run a specific skill by id (bypasses selection/threshold).

        Args:
            skill_id:      Exact skill id from skill_definitions.py.
            user_input:    User's request text.
            extra_context: Extra context dict.

        Returns:
            OrchestrationResult.
        """
        t0 = time.time()
        result = self._engine.execute_by_id(skill_id, user_input, extra_context)
        elapsed = round(time.time() - t0, 2)
        skill = self._registry.get_by_id(skill_id)
        skill_name = skill["name"] if skill else skill_id

        return OrchestrationResult(
            success=result.get("success", False),
            summary=result.get("summary", ""),
            skill_results=[result],
            skills_used=[skill_id],
            total_elapsed_s=elapsed,
        )

    def run_pipeline(
        self,
        skill_ids: list[str],
        user_input: str,
        extra_context: Optional[dict] = None,
    ) -> OrchestrationResult:
        """Execute a fixed ordered list of skills, piping output forward.

        Args:
            skill_ids:     Ordered list of skill ids to execute.
            user_input:    Initial user input.
            extra_context: Optional extra context.

        Returns:
            OrchestrationResult with all step results.
        """
        t0 = time.time()
        all_results: list[dict] = []
        current_input = user_input

        for skill_id in skill_ids:
            self._emit(f"[Pipeline] Running: {skill_id}")
            result = self._engine.execute_by_id(skill_id, current_input, extra_context)
            all_results.append(result)

            if not result.get("success"):
                self._emit(f"  Pipeline stopped at '{skill_id}': {result.get('error')}")
                break

            # Pipe this skill's result as input to the next
            output = result.get("result") or result.get("summary") or ""
            current_input = f"{user_input}\n\n[Previous step output:]\n{output[:2000]}"

        elapsed = round(time.time() - t0, 2)
        success = all_results[-1].get("success") if all_results else False
        summary = self._build_summary(all_results, skill_ids)

        return OrchestrationResult(
            success=success,
            summary=summary,
            skill_results=all_results,
            skills_used=skill_ids,
            total_elapsed_s=elapsed,
            chained=len(skill_ids) > 1,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_summary(self, results: list[dict], skill_ids: list[str]) -> str:
        names = []
        for sid in skill_ids:
            skill = self._registry.get_by_id(sid)
            names.append(skill["name"] if skill else sid)

        lines = []
        for res, name in zip(results, names):
            if res.get("success"):
                snippet = (res.get("result") or res.get("summary") or "")[:300]
                lines.append(f"**{name}**\n{snippet}")
            else:
                lines.append(f"**{name}** — failed: {res.get('error', 'unknown error')}")

        return "\n\n---\n\n".join(lines) if lines else "No results."

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def available_skills_text(self) -> str:
        """Return a compact text listing all active skills (for UI or debug)."""
        skills = self._registry.get_all(active_only=True)
        lines = [f"  {s['id']:35s} [{s['category']:12s}] {s['description'][:80]}" for s in skills]
        return f"Available skills ({len(skills)}):\n" + "\n".join(lines)

    def get_skill_info(self, skill_id: str) -> Optional[dict]:
        """Return full skill definition dict including context_text."""
        return self._registry.get_by_id(skill_id)
