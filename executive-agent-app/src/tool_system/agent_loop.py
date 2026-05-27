"""Core agent execution loop with async support, retry logic, and live progress.

SYSTEM MODE: REAL-WORLD AUTONOMOUS OPERATOR
Every goal is executed with real tools. Failures trigger automatic diagnosis
and repair via SelfRepairEngine before any retry.
"""

import asyncio
import inspect
import logging
import re
import time
import traceback
from typing import Callable, Optional

from .system_directive import SelfRepairEngine, SYSTEM_DIRECTIVE


_fastpath_log = logging.getLogger("megav.router.fastpath")


class AgentLoop:
    """Orchestrates goal execution across specialist agents."""

    # Map agent names to human-readable descriptions
    AGENT_LABELS = {
        "coder":   "Coder (code & files)",
        "browser": "Browser (web automation)",
        "desktop": "Desktop (app control)",
        "job":     "Job Hunt (applications)",
        "sales":   "Sales (research & leads)",
        "content": "Content Writer",
        "skill":   "Skill Manager",
        "memory":  "Memory (profile & data)",
        "social":  "Social Media Manager",
        "finance": "Finance (invoicing & payments)",
    }

    # System-mode directive exposed for agents that need it in their prompts
    SYSTEM_DIRECTIVE = SYSTEM_DIRECTIVE

    def __init__(self, runtime: dict, progress_cb: Optional[Callable[[str], None]] = None):
        self.runtime = runtime
        self.commander = runtime.get("commander")
        self.workflow_tools = runtime.get("workflow_tools")
        self.context = runtime.get("context")
        # Called at each progress event — safe to call from any thread
        self._progress_cb: Callable[[str], None] = progress_cb or (lambda _: None)
        # Self-repair engine — diagnoses failures and applies automated fixes
        self._repair = SelfRepairEngine(emit_cb=self._emit)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    MAX_GOAL_LEN = 4000
    _INJECTION_MARKERS = (
        "ignore previous instructions",
        "ignore all prior",
        "disregard the system",
        "you are now",
        "system prompt:",
    )

    def _sanitize_goal(self, goal: str) -> str:
        """Normalize and length-cap user goal text. Logs prompt-injection markers."""
        if not isinstance(goal, str):
            goal = str(goal or "")
        goal = goal.replace("\x00", "").strip()
        if len(goal) > self.MAX_GOAL_LEN:
            self._emit(f"  -> Goal truncated to {self.MAX_GOAL_LEN} chars")
            goal = goal[: self.MAX_GOAL_LEN]
        lowered = goal.lower()
        for marker in self._INJECTION_MARKERS:
            if marker in lowered:
                self._emit(f"  -> Warning: prompt-injection marker detected ('{marker}')")
                break
        return goal

    async def run(self, goal: str) -> dict:
        """Execute a user goal end-to-end.

        Supports both single-phase and compound (multi-phase) goals.
        For compound goals, each phase feeds context into the next,
        and real verification checks that output files/data exist.

        Args:
            goal: Natural-language goal from the user.

        Returns:
            dict with keys: success, summary, steps_log
        """
        if not self.context:
            from .context import ToolContext
            self.context = ToolContext()
            self.runtime["context"] = self.context

        goal = self._sanitize_goal(goal)
        self.context.goal = goal
        self.context.current_goal = goal
        self._steps_log: list[dict] = []
        # Accumulated context from previous phases (for compound goals)
        self._phase_context: list[str] = []
        self._phase_outputs: list[str] = []   # file paths saved by previous phases

        try:
            # 0. Short-circuit conversational / help queries
            help_resp = self._try_handle_as_question(goal)
            if help_resp:
                return help_resp

            # 0.5. Skill interception — check if a skill should handle this
            skill_result = await self._try_skill_intercept(goal)
            if skill_result:
                return skill_result

            # 1. Analyse
            self._emit(f"Analysing your request…")
            goal_preview = goal[:100].replace("\n", " ")
            self._emit(f"  -> Goal: {goal_preview}{'…' if len(goal) > 100 else ''}")
            analysis = self.commander.analyze_goal(goal)
            agent_name = analysis.get("suggested_agent", "coder")
            label = self.AGENT_LABELS.get(agent_name, agent_name)
            self._emit(f"Routing to: {label}")

            # 2. Build execution plan (pass already-determined agent to avoid re-analysis)
            self._emit("Building execution plan…")
            plan = self.commander.plan_steps(goal, agent_hint=agent_name)
            steps = plan.get("steps", [])
            total = len(steps)
            is_compound = plan.get("compound", False)

            if is_compound and total > 1:
                self._emit(f"Multi-phase plan ready — {total} phases to execute.")
                return await self._execute_compound_goal(goal, steps, agent_name)
            else:
                self._emit(f"Plan ready — {total} step(s) to execute.")

            # 3. Execute each step (single-phase path)
            results = []
            succeeded = 0
            for i, step in enumerate(steps, 1):
                action = step.get("action", "")
                desc = step.get("description", action)

                # Real verification: check that prior output exists
                if action == "verify_compound":
                    self._emit(f"[{i}/{total}] Verifying output…")
                    verify_result = self._verify_compound_output(results, goal)
                    self._log_step(action, desc, verify_result)
                    results.append(verify_result)
                    if verify_result.get("success"):
                        succeeded += 1
                        self._emit(f"  -> Verification passed")
                    else:
                        self._emit(f"  -> Verification note: {verify_result.get('summary', 'partial')}")
                    continue

                # Legacy "verify" steps: real check instead of blind "OK"
                if action == "verify":
                    self._emit(f"[{i}/{total}] Verifying output…")
                    verify_result = self._verify_step_output(results, goal)
                    self._log_step(action, desc, verify_result)
                    if verify_result.get("success"):
                        succeeded += 1
                        self._emit(f"  -> Verification passed")
                    continue

                self._emit(f"[{i}/{total}] {desc}…")

                # Inject phase context into the step for the agent
                enriched_step = dict(step)
                if self._phase_context:
                    enriched_step["prior_context"] = "\n".join(self._phase_context[-3:])
                if self._phase_outputs:
                    enriched_step["prior_files"] = list(self._phase_outputs)

                result = await self._dispatch_step_with_retry(enriched_step)
                self._log_step(action, desc, result)
                results.append(result)

                if result.get("success"):
                    succeeded += 1
                    note = result.get("summary") or result.get("message", "Done.")
                    first_line = note.split("\n")[0][:140]
                    self._emit(f"  -> {first_line}")
                    # If a file was saved, track it for downstream phases
                    if result.get("path"):
                        self._emit(f"  SAVED: {result['path']}")
                        self._phase_outputs.append(result["path"])
                    # Accumulate summary for context chaining
                    self._phase_context.append(note[:500])
                else:
                    err = result.get("error", "Failed")
                    if "Unknown action" in err:
                        self._emit(f"  -> Step skipped (no handler).")
                        succeeded += 1   # don't penalise skipped steps
                        continue
                    self._emit(f"  -> ERROR: {err[:120]}")
                    if any(x in err.lower() for x in ("no handler", "not available", "not found", "skipped")):
                        continue
                    break

            # 4. Build final summary — prefer the last successful result's full summary
            self._emit("Finalising…")
            last_summary = ""
            for r in reversed(results):
                if r.get("success") and r.get("summary"):
                    last_summary = r["summary"]
                    break

            if last_summary:
                summary = last_summary
            else:
                summary = self._build_summary(goal, agent_name, results, succeeded, total)

            final_result: dict = {
                "success": succeeded > 0 and succeeded == total,
                "summary": summary,
                "steps_log": self._steps_log,
                "details": results,
            }

            # ── Auto-export via OutputEngine ──────────────────────────
            if final_result["success"] and not any(r.get("path") for r in results):
                try:
                    from .output_engine import get_output_engine
                    export_path = get_output_engine().auto_export(goal, final_result)
                    if export_path:
                        final_result["path"] = export_path
                        self._emit(f"  SAVED: {export_path}")
                except Exception as _oe:
                    self._emit(f"  [OutputEngine] export skipped: {_oe}")

            return final_result

        except Exception as e:
            tb = traceback.format_exc()
            self._emit(f"Unexpected error: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": f"Error during execution: {e}",
                "traceback": tb,
                "steps_log": getattr(self, "_steps_log", []),
            }

    # ------------------------------------------------------------------
    # Compound (multi-phase) goal execution
    # ------------------------------------------------------------------

    async def _execute_compound_goal(
        self, goal: str, steps: list[dict], primary_agent: str,
    ) -> dict:
        """Execute a compound multi-phase goal with context chaining.

        Each phase feeds its output into the next phase as context.
        Real verification checks that files/data exist between phases.
        """
        total = len(steps)
        results = []
        succeeded = 0
        saved_files: list[str] = []

        for i, step in enumerate(steps, 1):
            action = step.get("action", "")
            desc = step.get("description", action)
            sub_goal = step.get("sub_goal", "")
            phase_name = step.get("phase_name", f"Phase {i}")

            # ── Verification step ──────────────────────────────────────
            if action == "verify_compound":
                self._emit(f"[{i}/{total}] Verifying all phases produced real output…")
                verify = self._verify_compound_output(results, goal)
                self._log_step(action, desc, verify)
                results.append(verify)
                if verify.get("success"):
                    succeeded += 1
                    self._emit(f"  -> All phases verified — {len(saved_files)} file(s) saved")
                else:
                    self._emit(f"  -> Verification note: {verify.get('summary', 'partial output')}")
                continue

            # ── Execute a phase ────────────────────────────────────────
            self._emit(f"[{i}/{total}] {phase_name}…")

            # Build a focused sub-goal with context from previous phases
            enriched_step = dict(step)
            if sub_goal:
                # Give the agent a clear, focused instruction
                enriched_step["description"] = (
                    f"{sub_goal}\n\n"
                    f"Context from previous phases:\n"
                    + "\n".join(f"  - {ctx}" for ctx in self._phase_context[-3:])
                    if self._phase_context
                    else sub_goal
                )
            if self._phase_outputs:
                enriched_step["prior_files"] = list(self._phase_outputs)

            result = await self._dispatch_step_with_retry(enriched_step)
            self._log_step(action, desc, result)
            results.append(result)

            if result.get("success"):
                succeeded += 1
                note = result.get("summary") or result.get("message", "Done.")
                first_line = note.split("\n")[0][:140]
                self._emit(f"  -> {first_line}")

                # Track saved files for downstream phases
                if result.get("path"):
                    self._emit(f"  SAVED: {result['path']}")
                    saved_files.append(result["path"])
                    self._phase_outputs.append(result["path"])
                elif action not in ("verify_compound", "verify"):
                    # Auto-save this phase's output as its own file
                    try:
                        from .output_engine import get_output_engine
                        phase_path = get_output_engine().export_phase(
                            goal=goal,
                            phase_idx=i,
                            phase_name=phase_name,
                            action=action,
                            result=result,
                        )
                        if phase_path:
                            self._emit(f"  SAVED: {phase_path}")
                            saved_files.append(phase_path)
                            self._phase_outputs.append(phase_path)
                            result["path"] = phase_path
                    except Exception:
                        pass

                # Chain context: previous phase summaries feed into next phase
                self._phase_context.append(note[:500])
            else:
                err = result.get("error", "Failed")
                self._emit(f"  -> ERROR: {err[:120]}")
                # For compound goals, try to continue even on failure
                if any(x in err.lower() for x in ("no handler", "not available", "not found")):
                    self._phase_context.append(f"[Phase {i} attempted but handler not available]")
                    continue
                # Critical failure — but still try remaining phases
                self._phase_context.append(f"[Phase {i} failed: {err[:100]}]")

        # ── Build final summary for compound goal ─────────────────────
        self._emit("Finalising compound task…")

        phase_summaries = []
        for idx, r in enumerate(results):
            if r.get("success"):
                s = r.get("summary", "Completed")
                p = r.get("path", "")
                if p:
                    phase_summaries.append(f"  - {s[:80]} (saved: {p})")
                else:
                    phase_summaries.append(f"  - {s[:80]}")

        summary = (
            f"Completed {succeeded}/{total} phases.\n"
            + "\n".join(phase_summaries[:8])
        )

        if saved_files:
            summary += f"\n\nFiles saved ({len(saved_files)}):\n" + "\n".join(f"  {f}" for f in saved_files)

        final_result: dict = {
            "success": succeeded > 0 and succeeded == total,
            "summary": summary,
            "steps_log": self._steps_log,
            "details": results,
            "saved_files": saved_files,
            "compound": True,
        }

        # ── Always export a master summary file ───────────────────────
        try:
            from .output_engine import get_output_engine
            export_path = get_output_engine().auto_export(goal, final_result)
            if export_path:
                final_result["path"] = export_path
                self._emit(f"  SAVED: {export_path}")
        except Exception as _oe:
            self._emit(f"  [OutputEngine] export skipped: {_oe}")

        return final_result

    # ------------------------------------------------------------------
    # Real verification (replaces blind "OK" skips)
    # ------------------------------------------------------------------

    def _verify_compound_output(self, results: list[dict], goal: str) -> dict:
        """Verify that compound goal phases produced real output.

        Checks for: saved files, non-empty summaries, and real data
        (not just "acknowledged" or "task noted" placeholders).
        """
        import os
        verified_files = []
        verified_summaries = []
        placeholder_count = 0
        PLACEHOLDER_PHRASES = [
            "task acknowledged", "task noted", "will be handled",
            "i understand", "i'll help", "here's a plan",
            "i can assist", "let me help", "great idea",
            "generated by megav", "implement the requested code",
            "example: read files", "this is a template",
            "auto-generated", "placeholder", "replace with your",
        ]

        for r in results:
            if not r or not r.get("success"):
                continue
            # Check for real file output
            path = r.get("path")
            if path and os.path.isfile(path):
                size = os.path.getsize(path)
                if size > 50:  # More than 50 bytes = real content
                    verified_files.append(path)
                continue
            # Check summary for placeholder language
            summary = (r.get("summary") or r.get("message") or "").lower()
            if summary:
                is_placeholder = any(p in summary for p in PLACEHOLDER_PHRASES)
                if is_placeholder:
                    placeholder_count += 1
                else:
                    verified_summaries.append(summary[:200])

        if verified_files:
            return {
                "success": True,
                "summary": f"Verified {len(verified_files)} real output file(s): "
                           + "; ".join(os.path.basename(f) for f in verified_files),
                "verified_files": verified_files,
            }
        if verified_summaries:
            return {
                "success": True,
                "summary": f"Verified {len(verified_summaries)} phase(s) with output. "
                           f"({placeholder_count} placeholder response(s) detected)",
                "verified_files": [],
            }
        if placeholder_count > 0:
            return {
                "success": False,
                "summary": f"No real output produced — {placeholder_count} placeholder response(s) detected. "
                           "The AI acknowledged tasks but did not produce deliverables.",
                "verified_files": [],
            }
        return {
            "success": False,
            "summary": "No verifiable output produced by any phase.",
            "verified_files": [],
        }

    def _verify_step_output(self, prior_results: list[dict], goal: str) -> dict:
        """Verify the most recent step produced real output."""
        if not prior_results:
            return {"success": True, "summary": "No prior steps to verify."}

        last = prior_results[-1]
        if not last.get("success"):
            return {"success": False, "summary": "Previous step failed — skipping verification."}

        # Re-use compound verification for the single step
        return self._verify_compound_output([last], goal)

    # ------------------------------------------------------------------
    # Step dispatcher (handles both sync and async agent handlers)
    # ------------------------------------------------------------------

    async def _dispatch_step(self, step: dict) -> dict:
        from .approval_gate import ApprovalGate
        _gate = ApprovalGate()
        step_action = step.get("action", "")
        if _gate.is_financial(step_action) and step.get("agent") != "finance":
            # Secondary safety net — finance agent has its own gate,
            # but catch anything that slips through from other agents
            approved = _gate.request_approval(
                action=step_action,
                details=step.get("context", {}),
                risk_level="high",
            )
            if not approved:
                return {
                    "success": False,
                    "reason":  "Financial action rejected by user",
                    "agent":   step.get("agent", "unknown"),
                }

        agent_name = step.get("agent", "coder")
        action     = step.get("action", "")

        agent = self.commander.agents.get(agent_name)
        if not agent:
            return {"success": False, "error": f"Agent not available: {agent_name}"}

        handler_map = {
            "coder":   "handle_code_task",
            "browser": "handle_browser_task",
            "desktop": "handle_desktop_task",
            "job":     "handle_job_task",
            "sales":   "handle_sales_task",
            "content": "handle_content_task",
            "skill":   "handle_skill_task",
            "memory":  "handle_memory_task",
            "social":  "handle_social_task",
            "finance": "handle_finance_task",
        }

        method_name = handler_map.get(agent_name)
        if not method_name or not hasattr(agent, method_name):
            return {"success": False, "error": f"No handler for agent: {agent_name}"}

        self._before_step_hook(step)
        try:
            # Pass step description and prior context to agents for compound goals
            step_desc = step.get("description", "")
            if step_desc:
                self.context.step_description = step_desc
            if step.get("prior_files"):
                self.context.prior_files = step["prior_files"]

            result = getattr(agent, method_name)(action, self.context)
            if inspect.isawaitable(result):
                result = await result
        except Exception as e:
            result = {"success": False, "error": f"{agent_name} handler raised: {e}"}

        self._after_step_hook(step, result)
        return result

    async def _dispatch_step_with_retry(self, step: dict, max_retries: int = 3) -> dict:
        """
        Execute a step with automatic self-repair on failure.

        Flow: attempt → failure → diagnose → fix → retry (up to max_retries).
        """
        last_result: dict = {"success": False, "error": "Not started"}

        for attempt in range(1, max_retries + 1):
            result = await self._dispatch_step(step)
            if result.get("success"):
                return result

            error = result.get("error", "Unknown error")
            last_result = result

            if attempt >= max_retries:
                break

            # ── Self-repair chain ──────────────────────────────────────
            diagnosis = self._repair.diagnose(error)
            self._emit(f"  [SELF-REPAIR] {diagnosis.category}: {diagnosis.fix_description}")
            fixed = self._repair.apply_fix(diagnosis, context={"step": step, "error": error})

            if not self._is_retryable(error) and not fixed and not getattr(diagnosis, 'retry_recommended', False):
                # Non-retryable, fix didn't apply, and retry not recommended — stop
                self._emit(f"  [SELF-REPAIR] Non-retryable error, no fix available. Stopping.")
                return result

            wait = 2 ** (attempt - 1)
            self._emit(f"  -> Retrying in {wait}s… (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(wait)

        self._emit(f"  [SELF-REPAIR] All {max_retries} attempts exhausted.")
        return last_result

    # ------------------------------------------------------------------
    # Summary builder
    # ------------------------------------------------------------------

    def _build_summary(self, _goal, agent_name, results, succeeded, total) -> str:
        label = self.AGENT_LABELS.get(agent_name, agent_name)

        if not results:
            return f"Task processed by {label}. No execution steps were needed."

        real = [r for r in results if not r.get("skipped")]
        if not real:
            return f"Task reviewed by {label}. All steps were verification-only."

        # Collect the most useful snippet from results
        snippets = []
        for r in real:
            for key in ("summary", "message", "content", "code", "path", "url"):
                val = r.get(key)
                if val and isinstance(val, str):
                    snippets.append(val[:200])
                    break

        intro = f"Completed {succeeded}/{total} step(s) via {label}.\n"
        body  = "\n".join(f"  - {s}" for s in snippets[:5]) if snippets else "  (no output details)"
        return intro + body

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, msg: str):
        """Emit a progress message."""
        self._progress_cb(msg)

    def _log_step(self, action: str, desc: str, result: dict):
        self._steps_log.append({
            "action": action,
            "description": desc,
            "success": result.get("success", False),
            "summary": result.get("summary") or result.get("message") or result.get("error", ""),
            "ts": time.time(),
        })

    def _is_retryable(self, error: str) -> bool:
        patterns = ["timeout", "connection", "element not found", "stale element", "page crash"]
        e = error.lower()
        return any(p in e for p in patterns)

    def _before_step_hook(self, step: dict):
        if getattr(self.context, "workflow_recording", False):
            self._pending_step = {
                "action": step.get("action"),
                "params": step.get("params", {}),
                "start_time": time.time(),
            }

    def _after_step_hook(self, _step: dict, result: dict):
        if getattr(self.context, "workflow_recording", False) and hasattr(self, "_pending_step"):
            if hasattr(self.context, "record_step"):
                self.context.record_step(
                    self._pending_step["action"],
                    self._pending_step["params"],
                    result,
                )
            del self._pending_step

    # ------------------------------------------------------------------
    # Skill interception fast-path
    # ------------------------------------------------------------------

    # Tasks that must bypass the skill system — they need real agent execution
    _AGENT_ONLY_PATTERNS = (
        "lead generation", "lead gen", "outreach system", "outreach campaign",
        "find leads", "find companies", "find businesses", "find prospects",
        "discover leads", "prospect list", "research companies",
        "autonomous", "job search", "apply for job", "find job", "job application",
        "fully automat", "end-to-end", "end to end",
        "web research", "market research", "competitor research",
        "send email", "send emails", "email campaign", "bulk email",
        "browser automat", "form fill", "scrape website",
        "post on linkedin", "post on facebook", "post on instagram",
        "desktop automat", "click button", "open notepad",
        # Coding / development tasks — always go to coder agent, never to skills
        "write code", "write a script", "write a program", "write a function",
        "create a script", "create a program", "create a function", "create a calculator",
        "create a tool", "create a bot", "create a game", "create an app",
        "create a python", "create a javascript", "create a web app",
        "build a script", "build a program", "build a tool", "build a bot",
        "build a game", "build an app", "build a python", "build a web app",
        "make a script", "make a program", "make a calculator", "make an app",
        "develop a", "implement a", "code a", "code a script",
        "fix a bug", "debug a", "refactor code", "optimize code",
        "write a python", "write a javascript", "write a web",
        "parse a file", "convert data", "process a csv", "generate a report",
    )

    async def _try_skill_intercept(self, goal: str) -> Optional[dict]:
        """If a skill confidently matches this goal, execute it and return
        a result dict in the same shape as run().  Returns None otherwise.

        The orchestrator is stored in runtime["skill_orchestrator"] by main.py.
        """
        orchestrator = self.runtime.get("skill_orchestrator")
        if not orchestrator:
            return None

        # Complex operational tasks must go to the real agents, not the skill LLM
        goal_lower = goal.lower()
        if any(pat in goal_lower for pat in self._AGENT_ONLY_PATTERNS):
            return None

        # Long multi-step goals (>250 chars) go to agents directly
        if len(goal) > 250 and any(
            kw in goal_lower for kw in
            ("step", "phase", "discover", "research", "outreach", "generate", "build a", "create a")
        ):
            return None

        try:
            # Determine agent hint from commander's quick analysis
            agent_hint = None
            if self.commander:
                try:
                    analysis = self.commander.analyze_goal(goal)
                    agent_hint = analysis.get("suggested_agent")
                except Exception:
                    pass

            # Only intercept if score exceeds threshold
            if not orchestrator.should_intercept(goal, agent_hint=agent_hint):
                return None

            self._emit("Skill detected — executing via Skill Engine…")
            orch_result = orchestrator.run(
                goal,
                agent_hint=agent_hint,
                extra_context={"profile": getattr(self.context, "profile", {})},
            )

            if not orch_result.success:
                # Skill matched but failed — let normal agent loop handle it
                self._emit(f"Skill execution failed ({orch_result.summary[:80]}), falling back to agent…")
                return None

            skills_label = " + ".join(orch_result.skills_used)
            self._emit(f"Skill(s) completed: {skills_label} ({orch_result.total_elapsed_s}s)")

            self._log_step("skill_execution", f"Skills: {skills_label}", {
                "success": True,
                "summary": orch_result.summary[:200],
            })

            # Support both old (.skill_results) and new (.step_results) schema
            details = getattr(orch_result, "step_results",
                              getattr(orch_result, "skill_results", []))
            return {
                "success": True,
                "summary": orch_result.summary,
                "steps_log": self._steps_log,
                "details": [r.to_dict() if hasattr(r, "to_dict") else r for r in details],
                "skills_used": orch_result.skills_used,
                "via_skill": True,
            }
        except Exception as exc:
            # Never let skill errors crash the main loop
            self._emit(f"Skill interception error: {exc} — continuing with normal routing.")
            return None

    # ------------------------------------------------------------------
    # Conversational query fast-path
    # ------------------------------------------------------------------

    _CAPABILITIES_TEXT = (
        "I am MegaV - a local AI operator that controls your computer.\n\n"
        "WHAT I CAN DO\n"
        "-------------\n"
        "  Coding        Write, read, edit, run and debug code in any language.\n"
        "                Example: \"Write a Python script that renames all files in a folder\"\n\n"
        "  Browser       Open websites, fill forms, log in, navigate, take screenshots.\n"
        "                Example: \"Go to https://linkedin.com and search for Python jobs\"\n\n"
        "  Desktop       Launch apps, click buttons, type into windows, automate UI.\n"
        "                Example: \"Open Notepad and type Hello World\"\n\n"
        "  Job Hunting   Match jobs to your profile, fill applications, write cover letters.\n"
        "                Example: \"Find Python developer jobs on LinkedIn and apply to 3\"\n\n"
        "  Sales         Research markets, find leads, draft outreach emails.\n"
        "                Example: \"Find 5 SaaS CRM competitors and draft outreach\"\n\n"
        "  Content       Write blog posts, YouTube descriptions, social captions, emails.\n"
        "                Example: \"Write a LinkedIn post about AI productivity tips\"\n\n"
        "  Skills        Search and install new capabilities.\n"
        "                Example: \"Install the web-scraping skill\"\n\n"
        "  Memory        Store and recall your profile, answers, and workflows.\n"
        "                Example: \"Remember that my email is you@example.com\"\n\n"
        "  Social Media  Post to LinkedIn, Facebook, Instagram, Google Business, TikTok.\n"
        "                Example: \"Post on LinkedIn: Excited to share my new project!\"\n\n"
        "  File Upload   Attach PDFs, Word docs, Excel sheets, images, code files.\n"
        "                Use the 📎 button to attach a file, then describe what to do with it.\n\n"
        "HOW TO USE\n"
        "----------\n"
        "  Just type your goal in plain English and press Send.\n"
        "  No commands or syntax needed - the agent figures out the rest.\n"
    )

    # Exact short phrases that ARE help-only requests (whole message = this phrase)
    _HELP_EXACT = {
        "help", "help me", "?", "commands", "features", "tutorial",
        "what can you do", "what do you do", "what are you", "who are you",
        "how do you work", "what can i ask", "what should i ask",
    }

    # Longer phrases — only checked when the message is short (≤ 120 chars)
    _HELP_TRIGGERS = [
        "what are your features", "what are your skills", "what are your capabilities",
        "show me what you can", "list your features", "list your skills",
        "tell me about yourself", "what do you know",
    ]

    # Action verbs that mean "do a task" — when present, never short-circuit.
    _ACTION_VERBS = (
        "build", "create", "write", "make", "generate", "fix", "refactor",
        "deploy", "send", "email", "search", "find", "open", "run", "install",
        "scrape", "automate", "schedule", "analyze", "summarize", "translate",
        "draft", "design", "implement", "debug", "test", "compile", "package",
        "post", "publish", "record", "download", "upload", "convert", "extract",
    )

    _GREETING_RE = re.compile(
        r"^(hi|hello|hey|yo|sup|thanks?|thank you|bye|goodbye|"
        r"good (morning|afternoon|evening|night))\b",
        re.IGNORECASE,
    )

    def _is_conversational(self, goal: str) -> bool:
        """True when the message is small-talk / a question, not a task."""
        g = goal.strip()
        if not g or len(g) > 200:
            return False
        if g.count("\n") > 1:
            return False
        gl = g.lower()
        # Action verb at the start = task, never conversational
        first_word = gl.split(maxsplit=1)[0].strip(".,!?:")
        if first_word in self._ACTION_VERBS:
            return False
        # Greeting/thanks/farewell
        if self._GREETING_RE.match(gl):
            return True
        # Question ending in '?' AND no action verb anywhere in body
        if g.rstrip().endswith("?") and not any(v in gl.split() for v in self._ACTION_VERBS):
            return True
        return False

    def _answer_conversationally(self, goal: str) -> dict:
        """Stream a direct LLM reply — no planner, no auto-export."""
        try:
            from src.providers.model_router import get_model_router
        except Exception:
            from providers.model_router import get_model_router  # type: ignore
        router = get_model_router()
        system = (
            "You are MegaV, a local AI operator. The user is chatting with you "
            "casually. Reply briefly and conversationally in 1-3 sentences. "
            "Do not produce plans, files, or code unless explicitly asked."
        )
        try:
            result = router.route_generate(prompt=goal, task_type="general", system_prompt=system)
            r = result or {}
            msg = r.get("message") or {}
            reply = (
                r.get("response")
                or r.get("text")
                or (msg.get("content") if isinstance(msg, dict) else "")
                or ""
            )
        except Exception as e:
            _fastpath_log.warning("conversational reply failed: %s", e)
            reply = ""
        if not reply:
            reply = "Hi — I'm here. What would you like me to do?"
        _fastpath_log.info("fastpath answered: %r", goal[:60])
        return {
            "success": True,
            "summary": reply,
            "steps_log": [],
            "skip_export": True,
        }

    def _try_handle_as_question(self, goal: str) -> Optional[dict]:
        # Conversational fast-path (greetings, simple questions, thanks)
        if self._is_conversational(goal):
            return self._answer_conversationally(goal)

        g = goal.lower().strip().rstrip("?.,!")

        # Exact-match: whole message is a help query
        if g in self._HELP_EXACT:
            return {"success": True, "summary": self._CAPABILITIES_TEXT, "steps_log": []}

        # Phrase-match: only for short messages to avoid false positives
        # e.g. "where AI can help them" should NOT trigger help
        if len(g) <= 120 and any(t in g for t in self._HELP_TRIGGERS):
            return {"success": True, "summary": self._CAPABILITIES_TEXT, "steps_log": []}

        return None
