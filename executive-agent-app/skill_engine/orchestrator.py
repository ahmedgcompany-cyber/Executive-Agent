"""
Skill Engine — Orchestrator.

THE BRAIN. Exposes the primary public API for the rest of the system:

    from skill_engine.orchestrator import run_task

    result = run_task(user_prompt)          # auto-select + execute
    result = run_task(prompt, skill_id="canvas-design")   # forced
    result = run_task(prompt, chain=["canvas-design","theme-factory"])

Flow:
    User Prompt
        → Analyze (should_intercept?)
        → Select Skill(s)       (selector.py)
        → Execute Each           (executor.py)
        → Combine Output
        → Return OrchestrationResult

Key properties:
  - ZERO manual skill selection required
  - Automatic multi-skill chaining
  - Error recovery per step
  - Thread-safe (called from QThread in GUI)
  - Lazy singleton  (_ENGINE) for quick imports
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from .executor import SkillExecutor
from .registry import SkillRegistry
from .schemas import ExecutionResult, OrchestrationResult, SkillMatch
from .selector import SkillSelector


# ---------------------------------------------------------------------------
# Auto-chain rules
# Output of skill A is piped as extra context into skill B
# ---------------------------------------------------------------------------

_AUTO_CHAIN: dict[str, list[str]] = {
    "canvas-design":         ["frontend-design", "brand-guidelines"],
    "content-research-writer": ["theme-factory"],
    "tailored-resume-generator": ["brand-guidelines"],
    "artifacts-builder":     ["webapp-testing"],
    "mcp-builder":           ["webapp-testing"],
    "lead-research-assistant": ["twitter-algorithm-optimizer"],
    "competitive-ads-extractor": ["lead-research-assistant"],
    # Superpowers workflow chains
    "brainstorming":                    ["writing-plans"],
    "writing-plans":                    ["executing-plans"],
    "executing-plans":                  ["verification-before-completion"],
    "systematic-debugging":             ["verification-before-completion"],
    # Design chains
    "frontend-design":                  ["brand-guidelines"],
    # GStack chains
    "gstack-qa":                        ["gstack-review"],
    "gstack-investigate":              ["gstack-qa"],
    "gstack-ship":                     ["gstack-canary"],
    "gstack-design-consultation":      ["gstack-design-review"],
    # Research chains
    "lead-research-assistant":          ["tavily-search"],
    "content-research-writer":          ["tavily-search"],
    "competitive-ads-extractor":        ["tavily-search"],
}


class SkillOrchestrator:
    """Manages skill selection, execution, and chaining."""

    # Minimum selector score to auto-intercept
    CONFIDENCE_THRESHOLD = 3.5

    def __init__(
        self,
        registry: SkillRegistry,
        model_router: Optional[Any] = None,
        progress_cb: Optional[Callable[[str], None]] = None,
    ):
        self._registry = registry
        self._selector = SkillSelector(registry)
        self._executor = SkillExecutor(model_router, progress_cb)
        self._emit: Callable[[str], None] = progress_cb or (lambda _: None)
        self._model_router = model_router

    # ------------------------------------------------------------------
    # Primary public method
    # ------------------------------------------------------------------

    def run(
        self,
        user_prompt: str,
        skill_id: Optional[str] = None,
        chain: Optional[list[str]] = None,
        agent_hint: Optional[str] = None,
        extra_context: Optional[dict] = None,
        allow_auto_chain: bool = True,
    ) -> OrchestrationResult:
        """Execute the best skill(s) for a user prompt.

        Args:
            user_prompt:      What the user wants.
            skill_id:         Force a specific skill (bypasses selection).
            chain:            Force an ordered list of skill ids to run.
            agent_hint:       Which agent is calling (for affinity boosting).
            extra_context:    Additional data (profile, chat history, etc.).
            allow_auto_chain: Apply _AUTO_CHAIN rules after primary skill.

        Returns:
            OrchestrationResult with combined output.
        """
        t0 = time.time()
        ctx = dict(extra_context or {})

        # ── Mode 1: forced pipeline ────────────────────────────────────
        if chain:
            return self._run_pipeline(user_prompt, chain, ctx, t0)

        # ── Mode 2: forced single skill ────────────────────────────────
        if skill_id:
            return self._run_single_by_id(user_prompt, skill_id, ctx, t0)

        # ── Mode 3: auto-select ────────────────────────────────────────
        matches = self._selector.select_multi(user_prompt, agent_hint=agent_hint)
        if not matches:
            return OrchestrationResult(
                success=False,
                summary="No skill matched this request.",
            )

        # Check confidence
        if matches[0].score < self.CONFIDENCE_THRESHOLD:
            return OrchestrationResult(
                success=False,
                summary=f"Confidence too low ({matches[0].score:.1f}) — no skill triggered.",
            )

        skill_ids = [m.skill.id for m in matches]
        self._emit(f"Selected skill(s): {', '.join(skill_ids)}")

        step_results: list[ExecutionResult] = []
        current_input = user_prompt

        for match in matches:
            res = self._executor.execute(match.skill, current_input, ctx)
            step_results.append(res)
            if not res.success:
                self._emit(f"  Skill '{match.skill.name}' failed: {res.error}")
                break
            # Pipe output forward
            if res.result:
                current_input = (
                    f"{user_prompt}\n\n"
                    f"[Previous step — {match.skill.name}:]\n{res.result[:2000]}"
                )

        # ── Auto-chain rules (applied only on first primary skill) ─────
        if allow_auto_chain and step_results and step_results[-1].success:
            primary_id = matches[0].skill.id
            chain_ids  = _AUTO_CHAIN.get(primary_id, [])
            for cid in chain_ids:
                if cid in skill_ids:
                    continue   # already ran
                chain_skill = self._registry.get_by_id(cid)
                if not chain_skill:
                    continue
                self._emit(f"  Auto-chaining: {chain_skill.name}")
                chain_input = (
                    f"{user_prompt}\n\n"
                    f"[Output from {matches[0].skill.name}:]\n"
                    f"{step_results[-1].result[:2000]}"
                )
                cr = self._executor.execute(chain_skill, chain_input, ctx)
                step_results.append(cr)
                skill_ids.append(cid)

        total_elapsed = round(time.time() - t0, 2)
        success = any(r.success for r in step_results)
        summary = self._build_summary(step_results)
        full    = "\n\n---\n\n".join(r.result for r in step_results if r.result)

        return OrchestrationResult(
            success=success,
            summary=summary,
            full_result=full,
            skills_used=skill_ids,
            step_results=step_results,
            total_elapsed_s=total_elapsed,
            chained=len(step_results) > 1,
        )

    # ------------------------------------------------------------------
    # Secondary modes
    # ------------------------------------------------------------------

    def _run_single_by_id(
        self,
        user_prompt: str,
        skill_id: str,
        ctx: dict,
        t0: float,
    ) -> OrchestrationResult:
        skill = self._registry.get_by_id(skill_id)
        if not skill:
            return OrchestrationResult(
                success=False,
                summary=f"Unknown skill id: '{skill_id}'",
            )
        res = self._executor.execute(skill, user_prompt, ctx)
        return OrchestrationResult(
            success=res.success,
            summary=res.summary,
            full_result=res.result,
            skills_used=[skill_id],
            step_results=[res],
            total_elapsed_s=round(time.time() - t0, 2),
        )

    def _run_pipeline(
        self,
        user_prompt: str,
        skill_ids: list[str],
        ctx: dict,
        t0: float,
    ) -> OrchestrationResult:
        """Execute a fixed ordered list of skills, piping output forward."""
        step_results: list[ExecutionResult] = []
        current_input = user_prompt
        run_ids: list[str] = []

        for sid in skill_ids:
            skill = self._registry.get_by_id(sid)
            if not skill:
                self._emit(f"  Pipeline: unknown skill '{sid}', skipping")
                continue
            self._emit(f"  Pipeline step: {skill.name}")
            res = self._executor.execute(skill, current_input, ctx)
            step_results.append(res)
            run_ids.append(sid)
            if not res.success:
                break
            if res.result:
                current_input = (
                    f"{user_prompt}\n\n"
                    f"[{skill.name} output:]\n{res.result[:2000]}"
                )

        success = bool(step_results) and step_results[-1].success
        return OrchestrationResult(
            success=success,
            summary=self._build_summary(step_results),
            full_result="\n\n---\n\n".join(r.result for r in step_results if r.result),
            skills_used=run_ids,
            step_results=step_results,
            total_elapsed_s=round(time.time() - t0, 2),
            chained=len(run_ids) > 1,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def should_intercept(self, prompt: str, agent_hint: Optional[str] = None) -> bool:
        """Return True if a skill should handle this prompt."""
        return self._selector.should_intercept(prompt, agent_hint)

    def _build_summary(self, results: list[ExecutionResult]) -> str:
        parts = []
        for res in results:
            if res.success:
                snippet = (res.result or res.summary or "")[:300]
                parts.append(f"[{res.skill_name}] {snippet}")
            else:
                parts.append(f"[{res.skill_name}] FAILED: {res.error}")
        return "\n\n".join(parts) if parts else "No output."


# ---------------------------------------------------------------------------
# Lazy singleton — module-level convenience so agents can just import
# ---------------------------------------------------------------------------

_ENGINE: Optional[SkillOrchestrator] = None


def init_engine(
    model_router: Optional[Any] = None,
    progress_cb: Optional[Callable[[str], None]] = None,
    skills_root: Optional[str] = None,
) -> SkillOrchestrator:
    """Initialise (or reinitialise) the global SkillOrchestrator.

    Called once from main.py's build_runtime().
    """
    global _ENGINE
    from .parser import SkillParser
    from pathlib import Path as _Path

    parser = SkillParser(_Path(skills_root) if skills_root else None)
    registry = SkillRegistry(parser=parser, auto_load=True)
    _ENGINE = SkillOrchestrator(registry, model_router, progress_cb)
    return _ENGINE


def get_engine() -> Optional[SkillOrchestrator]:
    """Return the global engine (None if not initialised yet)."""
    return _ENGINE


def run_task(
    user_prompt: str,
    skill_id: Optional[str] = None,
    chain: Optional[list[str]] = None,
    agent_hint: Optional[str] = None,
    extra_context: Optional[dict] = None,
) -> OrchestrationResult:
    """Primary public API — run a skill task from anywhere in the app.

    Usage in agents::

        from skill_engine.orchestrator import run_task

        result = run_task(user_prompt, agent_hint="coder")
        if result.success:
            return {"success": True, "summary": result.summary}

    Args:
        user_prompt:   What the user typed.
        skill_id:      Optional — force a specific skill.
        chain:         Optional — force an ordered list of skill ids.
        agent_hint:    Calling agent name for affinity boosting.
        extra_context: Dict of extra data (profile, chat_history, etc.).

    Returns:
        OrchestrationResult (always returns, never raises).
    """
    engine = get_engine()
    if engine is None:
        return OrchestrationResult(
            success=False,
            summary="Skill Engine not initialised. Call init_engine() first.",
        )
    try:
        return engine.run(
            user_prompt,
            skill_id=skill_id,
            chain=chain,
            agent_hint=agent_hint,
            extra_context=extra_context,
        )
    except Exception as exc:
        return OrchestrationResult(
            success=False,
            summary=f"Skill Engine error: {exc}",
        )
