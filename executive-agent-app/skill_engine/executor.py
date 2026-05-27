"""
Skill Engine — Executor.

Handles the three execution types:
  A. PROMPT  — inject SKILL.md as LLM system context, call model
  B. SCRIPT  — run skill scripts via subprocess
  C. HYBRID  — scripts first, then LLM with combined context

Design principles:
  - All execution is synchronous (called from a thread, not the GUI loop)
  - Script failures are non-fatal in hybrid mode
  - Provides rich ExecutionResult regardless of how skill ran
  - Silent execution (no terminal popup windows)
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Optional

from .schemas import ExecutionResult, ExecutionType, Skill

from src.providers.model_router import NoModelAvailableError


class SkillExecutor:
    """Executes a single skill."""

    def __init__(
        self,
        model_router: Optional[Any] = None,
        progress_cb: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            model_router: ModelRouter instance for LLM calls (optional).
                          If None, prompt-type skills return raw context text.
            progress_cb:  Callback for real-time status messages.
        """
        self._router = model_router
        self._emit: Callable[[str], None] = progress_cb or (lambda _: None)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def execute(
        self,
        skill: Skill,
        user_input: str,
        extra_context: Optional[dict] = None,
    ) -> ExecutionResult:
        """Execute a skill and return an ExecutionResult.

        Args:
            skill:         The Skill to execute.
            user_input:    Raw user prompt.
            extra_context: Optional dict of supplementary data.
        """
        self._emit(f"[Executor] Running skill '{skill.name}' ({skill.execution_type.value})")
        t0 = time.time()

        try:
            # Built-in Agency / NEXUS skills — delegate to NexusOrchestrator / AgencyLibrary
            if skill.id in (
                "nexus-orchestrator", "nexus-sprint", "nexus-micro",
                "agency-engineering", "agency-design", "agency-marketing",
                "agency-sales", "agency-testing", "agency-project-management",
                "agency-product", "agency-specialized", "agency-finance", "agency-support",
            ):
                result = self._exec_agency_skill(skill, user_input, extra_context)
            # Built-in Email skills — delegate to EmailService / CRMService
            elif skill.id in ("email-reader", "email-sender", "email-reply",
                            "smart-inbox-sorter", "crm-followup-manager", "recruiter-reply-drafter"):
                result = self._exec_email_skill(skill, user_input, extra_context)
            # Built-in GitHub skills — delegate to GitHubService
            elif skill.id in ("github-repo-creator", "github-issue-manager", "github-commit-pusher"):
                result = self._exec_github_skill(skill, user_input, extra_context)
            elif skill.execution_type == ExecutionType.PROMPT:
                result = self._exec_prompt(skill, user_input, extra_context)
            elif skill.execution_type == ExecutionType.SCRIPT:
                result = self._exec_script(skill, user_input, extra_context)
            elif skill.execution_type == ExecutionType.HYBRID:
                result = self._exec_hybrid(skill, user_input, extra_context)
            else:
                result = self._err(skill, f"Unknown execution type: {skill.execution_type}")
        except Exception as exc:
            tb = traceback.format_exc()
            result = self._err(skill, f"Unhandled exception: {exc}", tb)

        result.elapsed_s = round(time.time() - t0, 2)
        self._emit(f"[Executor] '{skill.name}' done in {result.elapsed_s}s "
                   f"— {'OK' if result.success else 'FAIL'}")
        return result

    # ------------------------------------------------------------------
    # Prompt executor
    # ------------------------------------------------------------------

    def _exec_prompt(
        self,
        skill: Skill,
        user_input: str,
        extra_context: Optional[dict],
    ) -> ExecutionResult:
        """Call the LLM with SKILL.md as system context."""
        context_text = skill.skill_md_text

        if not context_text:
            context_text = (
                f"You are using the '{skill.name}' skill.\n"
                f"Description: {skill.description}\n\n"
                f"Use cases:\n" + "\n".join(f"- {uc}" for uc in skill.use_cases)
            )

        # Build system prompt
        system_parts = [
            f"You are executing the '{skill.name}' skill for the MegaV AI system.\n",
            "--- SKILL INSTRUCTIONS ---\n",
            context_text[:6000],
            "\n--- END SKILL INSTRUCTIONS ---\n\n",
            "Apply the skill instructions precisely to fulfil the user's request.",
        ]

        # Inject profile context if available
        profile = (extra_context or {}).get("profile", {})
        if profile:
            profile_snippet = "\n".join(
                f"  {k}: {v}" for k, v in list(profile.items())[:10] if v
            )
            if profile_snippet:
                system_parts.append(f"\n\nUser profile context:\n{profile_snippet}")

        system_prompt = "".join(system_parts)

        if self._router:
            try:
                response = self._router.route_generate(
                    user_input,
                    system_prompt=system_prompt,
                    task_type="skill_execution",
                )
                if response.get("success"):
                    text = response.get("response", "")
                    return ExecutionResult(
                        skill_id=skill.id,
                        skill_name=skill.name,
                        success=True,
                        result=text,
                        summary=text[:300],
                        mode="prompt",
                        system_prompt=system_prompt,
                    )
                return self._err(skill, response.get("error", "LLM call failed"))
            except NoModelAvailableError:
                return self._err(skill, "No LLM available")

        # No router — honest failure, not silent success
        return ExecutionResult(
            skill_id=skill.id,
            skill_name=skill.name,
            success=False,
            result="",
            error="No LLM available. Start Ollama or set an API key.",
            summary=f"Skill '{skill.name}' failed: no LLM available.",
            mode="prompt_no_router",
            system_prompt=system_prompt,
        )

    # ------------------------------------------------------------------
    # Script executor
    # ------------------------------------------------------------------

    def _exec_script(
        self,
        skill: Skill,
        user_input: str,
        extra_context: Optional[dict],
    ) -> ExecutionResult:
        """Run the skill's scripts via subprocess."""
        if not skill.scripts:
            return self._err(skill, "No scripts defined for this skill")

        script_outputs: list[dict] = []
        skill_folder = Path(skill.folder_path)

        for script_rel in skill.scripts:
            script_path = skill_folder / script_rel
            if not script_path.exists():
                self._emit(f"  Script not found, skipping: {script_rel}")
                continue

            self._emit(f"  Running: {script_path.name}")
            out = self._run_script(script_path, user_input, extra_context)
            script_outputs.append(out)
            if not out.get("success"):
                break   # stop on first failure

        if not script_outputs:
            return self._err(skill, "No scripts could run (files not found on disk)")

        combined = "\n\n".join(o.get("output", "") for o in script_outputs if o.get("output"))
        ok = all(o.get("success") for o in script_outputs)

        return ExecutionResult(
            skill_id=skill.id,
            skill_name=skill.name,
            success=ok,
            result=combined,
            summary=combined[:300] if combined else "Scripts executed.",
            mode="script",
            script_outputs=script_outputs,
            error="" if ok else (script_outputs[-1].get("error") or "Script failed"),
        )

    # ------------------------------------------------------------------
    # Agency / NEXUS built-in skill executor
    # ------------------------------------------------------------------

    def _exec_agency_skill(
        self,
        skill: "Skill",
        user_input: str,
        extra_context: Optional[dict],
    ) -> "ExecutionResult":
        """
        Route agency/NEXUS skill IDs to NexusOrchestrator or AgencyLibrary.
        """
        sid = skill.id

        # ── NEXUS pipeline skills ──────────────────────────────────────
        if sid in ("nexus-orchestrator", "nexus-sprint", "nexus-micro"):
            mode_map = {
                "nexus-orchestrator": "full",
                "nexus-sprint": "sprint",
                "nexus-micro": "micro",
            }
            mode = mode_map[sid]
            progress_lines: list[str] = []

            def _cb(msg: str):
                progress_lines.append(msg)

            try:
                from src.agents.nexus_orchestrator import get_nexus_orchestrator
            except ImportError:
                return self._err(skill, "NEXUS orchestrator not available.")

            orchestrator = get_nexus_orchestrator(progress_cb=_cb)
            nx_result = orchestrator.execute(user_input, mode=mode)
            summary = nx_result.summary or "\n".join(progress_lines[-20:])
            return ExecutionResult(
                skill_id=sid,
                skill_name=skill.name,
                success=nx_result.overall_status != "NEEDS_WORK",
                result=nx_result.summary,
                summary=summary,
                mode="agency",
                error="" if nx_result.overall_status != "NEEDS_WORK" else "Pipeline has blocked tasks — review summary.",
            )

        # ── Agency category skills ─────────────────────────────────────
        # Map skill ID to agency library category
        category_map = {
            "agency-engineering":        "engineering",
            "agency-design":             "design",
            "agency-marketing":          "marketing",
            "agency-sales":              "sales",
            "agency-testing":            "testing",
            "agency-project-management": "project-management",
            "agency-product":            "product",
            "agency-specialized":        "specialized",
            "agency-finance":            "finance",
            "agency-support":            "support",
        }
        category = category_map.get(sid)
        if not category:
            return self._err(skill, f"Unknown agency skill ID: {sid}")

        try:
            from src.agents.agency_library import get_agency_library
        except ImportError:
            return self._err(skill, "Agency library not available.")

        lib = get_agency_library()
        agent_rec = lib.find_best_agent(user_input, category=category)

        if not agent_rec:
            # Fallback: list available agents in category
            agents = lib.list_by_category(category)
            names = ", ".join(a["name"] for a in agents[:8])
            return ExecutionResult(
                skill_id=sid,
                skill_name=skill.name,
                success=True,
                result=f"Available {category} agents: {names}",
                summary=f"Available {category} specialist agents: {names}",
                mode="agency",
                error="",
            )

        prompt = lib.get_prompt(agent_rec["id"])
        if not prompt:
            return self._err(skill, f"Could not load prompt for agent {agent_rec['id']}")

        # Call LLM with agent personality
        router = self._router
        if not router:
            return ExecutionResult(
                skill_id=sid,
                skill_name=skill.name,
                success=False,
                result="",
                error="No LLM configured. Start Ollama or set an API key.",
                summary=f"[{agent_rec['name']}] Failed: no LLM configured.",
                mode="agency",
            )

        profile_ctx = ""
        if extra_context and extra_context.get("profile"):
            p = extra_context["profile"]
            profile_ctx = f"\n\nUser profile: name={p.get('name','')}, skills={p.get('skills',[])}."

        try:
            answer = router.ask(
                system=prompt[:3000],
                user=user_input + profile_ctx,
                task_type="general",
            ) or ""
        except NoModelAvailableError:
            return self._err(skill, "No LLM available")
        except Exception as exc:
            return self._err(skill, f"LLM call failed: {exc}")

        agent_label = f"[{agent_rec.get('emoji','🤖')} {agent_rec['name']}]"
        summary = f"{agent_label}\n\n{answer[:500]}" if answer else f"{agent_label} Task completed."

        return ExecutionResult(
            skill_id=sid,
            skill_name=skill.name,
            success=True,
            result=answer,
            summary=summary,
            mode="agency",
            error="",
        )

    # ------------------------------------------------------------------
    # Email built-in skill executor
    # ------------------------------------------------------------------

    def _exec_email_skill(
        self,
        skill: Skill,
        user_input: str,
        extra_context: Optional[dict],
    ) -> ExecutionResult:
        """Route to EmailService / CRMService for built-in email skills."""
        try:
            import sys as _sys, os as _os
            _app_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
            if _app_root not in _sys.path:
                _sys.path.insert(0, _app_root)
            from src.integrations.email_service import get_email_service
            from src.integrations.crm_service   import get_crm_service

            email_svc = get_email_service()
            profile   = (extra_context or {}).get("profile", {})
            default_account = profile.get("email", "")

            # ── CRM follow-up manager ────────────────────────────────
            if skill.id == "crm-followup-manager":
                crm = get_crm_service()
                summary = crm.get_pipeline_summary()
                follow_ups = summary.get("follow_ups", [])
                lines = [
                    f"CRM Pipeline Summary:",
                    f"  Total contacts: {summary['total_contacts']}",
                    f"  Follow-ups due: {summary['follow_ups_due']}",
                    "",
                    "By stage:",
                ]
                for stage, count in summary.get("by_stage", {}).items():
                    if count:
                        lines.append(f"  {stage}: {count}")
                if follow_ups:
                    lines.append("\nOverdue / Upcoming Follow-ups:")
                    for c in follow_ups[:5]:
                        lines.append(f"  • {c.get('name') or c['email']} — {c.get('stage')} — due {c.get('follow_up_date','')}")
                msg = "\n".join(lines)
                return ExecutionResult(
                    skill_id=skill.id, skill_name=skill.name,
                    success=True, result=str(summary), summary=msg, mode="crm",
                )

            # ── Check connected ──────────────────────────────────────
            if not email_svc.is_connected():
                return ExecutionResult(
                    skill_id=skill.id, skill_name=skill.name,
                    success=False, result="",
                    summary="No email account connected. Please add an account in the Email tab.",
                    mode="email", error="Email not connected",
                )

            # ── Dispatch per skill ───────────────────────────────────
            if skill.id == "email-reader":
                r = email_svc.get_smart_summary(default_account)
            elif skill.id == "smart-inbox-sorter":
                r = email_svc.classify_inbox(default_account, limit=25)
                if r.get("success"):
                    msgs   = r.get("messages", [])
                    urgent = [m["subject"] for m in msgs if m.get("classification", {}).get("priority") == "Urgent"]
                    reply  = [m["subject"] for m in msgs if m.get("classification", {}).get("needs_reply")]
                    r["summary"] = (
                        f"Sorted {len(msgs)} emails.\n"
                        f"Urgent ({len(urgent)}): {', '.join(urgent[:3])}\n"
                        f"Need reply ({len(reply)}): {', '.join(reply[:3])}"
                    )
            elif skill.id == "email-sender":
                r = {"success": False,
                     "error": "To send an email, provide: recipient, subject, and body.",
                     "needs_input": True}
            elif skill.id in ("email-reply", "recruiter-reply-drafter"):
                # Smart-select the first unread job/urgent email and draft a reply
                inbox = email_svc.classify_inbox(default_account, limit=15)
                if inbox.get("success"):
                    target = None
                    for m in inbox.get("messages", []):
                        cls = m.get("classification", {})
                        if cls.get("is_job_related") or cls.get("needs_reply"):
                            target = m
                            break
                    if target:
                        router = None
                        try:
                            from src.providers.model_router import ModelRouter
                            router = ModelRouter()
                        except Exception:
                            pass
                        r = email_svc.generate_reply_draft(
                            target["email_id"],
                            model_router=router,
                            user_profile=profile,
                        )
                        if r.get("success"):
                            r["summary"] = (
                                f"Draft for '{target['subject'][:60]}':\n\n{r.get('draft','')[:400]}"
                            )
                    else:
                        r = {"success": True,
                             "summary": "No emails needing a reply found in the last 15 messages."}
                else:
                    r = inbox
            else:
                r = email_svc.handle_prompt(user_input, default_account=default_account)

            if r.get("success"):
                msg = r.get("summary") or r.get("message", "Email action completed.")
                return ExecutionResult(
                    skill_id=skill.id, skill_name=skill.name,
                    success=True, result=str(r), summary=msg[:500], mode="email",
                )
            err = r.get("error", "Email action failed")
            return ExecutionResult(
                skill_id=skill.id, skill_name=skill.name,
                success=False, result="", summary=f"Email error: {err}",
                mode="email", error=err,
            )
        except Exception as exc:
            return self._err(skill, f"Email skill error: {exc}")

    # ------------------------------------------------------------------
    # GitHub built-in skill executor
    # ------------------------------------------------------------------

    def _exec_github_skill(
        self,
        skill: Skill,
        user_input: str,
        extra_context: Optional[dict],
    ) -> ExecutionResult:
        """Route to GitHubService.handle_prompt() for built-in GitHub skills."""
        try:
            import sys as _sys
            import os as _os
            # Ensure src package is importable
            _app_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
            if _app_root not in _sys.path:
                _sys.path.insert(0, _app_root)
            from src.integrations.github_service import get_github_service

            svc = get_github_service()
            if not svc.is_connected():
                return ExecutionResult(
                    skill_id=skill.id,
                    skill_name=skill.name,
                    success=False,
                    result="",
                    summary="GitHub is not connected. Please add a Personal Access Token in the Social tab.",
                    mode="github",
                    error="GitHub not connected",
                )

            # Extract default repo from profile or extra_context
            default_repo = ""
            if extra_context:
                profile = extra_context.get("profile", {})
                default_repo = (
                    profile.get("github_default_repo", "")
                    or extra_context.get("default_repo", "")
                )

            result = svc.handle_prompt(user_input, default_repo=default_repo)
            if result.get("success"):
                msg = result.get("message", "GitHub action completed successfully.")
                return ExecutionResult(
                    skill_id=skill.id,
                    skill_name=skill.name,
                    success=True,
                    result=str(result),
                    summary=msg[:400],
                    mode="github",
                )
            else:
                err = result.get("error", "GitHub action failed")
                return ExecutionResult(
                    skill_id=skill.id,
                    skill_name=skill.name,
                    success=False,
                    result="",
                    summary=f"GitHub error: {err}",
                    mode="github",
                    error=err,
                )
        except Exception as exc:
            return self._err(skill, f"GitHub skill error: {exc}")

    # ------------------------------------------------------------------
    # Hybrid executor
    # ------------------------------------------------------------------

    def _exec_hybrid(
        self,
        skill: Skill,
        user_input: str,
        extra_context: Optional[dict],
    ) -> ExecutionResult:
        """Run scripts (if present on disk) then use LLM with SKILL.md context."""
        skill_folder = Path(skill.folder_path)
        runnable = [s for s in skill.scripts if (skill_folder / s).exists()]

        script_result: Optional[ExecutionResult] = None
        if runnable:
            script_result = self._exec_script(skill, user_input, extra_context)
            self._emit("  Script phase complete — entering prompt phase.")

        # Build enriched input for LLM
        enriched_input = user_input
        if script_result and script_result.result:
            enriched_input = (
                f"{user_input}\n\n"
                f"[Script output from skill '{skill.name}':]\n{script_result.result[:2000]}"
            )

        prompt_result = self._exec_prompt(skill, enriched_input, extra_context)
        prompt_result.mode = "hybrid"
        prompt_result.script_outputs = getattr(script_result, "script_outputs", [])

        if script_result and not script_result.success:
            prompt_result.error = f"Script warning: {script_result.error}"

        return prompt_result

    # ------------------------------------------------------------------
    # Script runner
    # ------------------------------------------------------------------

    def _run_script(
        self,
        script_path: Path,
        user_input: str,
        extra_context: Optional[dict],
        timeout: int = 30,
    ) -> dict:
        suffix = script_path.suffix.lower()

        try:
            if suffix == ".py":
                cmd = [sys.executable, str(script_path)]
            elif suffix in (".sh", ".bash"):
                cmd = ["bash", str(script_path)]
            elif suffix in (".bat", ".cmd"):
                cmd = ["cmd", "/c", str(script_path)]
            elif suffix in (".js",):
                cmd = ["node", str(script_path)]
            else:
                return {"success": False, "error": f"Unsupported script type: {suffix}",
                        "script": script_path.name}

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(script_path.parent),
                env=self._build_env(user_input, extra_context),
                # Windows: no console window
                creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0),
            )
            output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            ok = proc.returncode == 0
            return {
                "success": ok,
                "output": output,
                "returncode": proc.returncode,
                "script": script_path.name,
                "error": proc.stderr.strip() if not ok else "",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Timeout after {timeout}s",
                    "script": script_path.name}
        except FileNotFoundError as exc:
            return {"success": False, "error": f"Runtime not found: {exc}",
                    "script": script_path.name}
        except Exception as exc:
            return {"success": False, "error": str(exc), "script": script_path.name}

    @staticmethod
    def _build_env(user_input: str, extra_context: Optional[dict]) -> dict:
        env = os.environ.copy()
        env["MEGAV_INPUT"] = user_input[:2000]
        if extra_context:
            for k, v in extra_context.items():
                if isinstance(v, str):
                    env[f"MEGAV_{k.upper()}"] = v[:500]
        return env

    # ------------------------------------------------------------------
    # Error factory
    # ------------------------------------------------------------------

    @staticmethod
    def _err(skill: Skill, message: str, traceback_text: str = "") -> ExecutionResult:
        detail = f" | {traceback_text[:200]}" if traceback_text else ""
        return ExecutionResult(
            skill_id=skill.id,
            skill_name=skill.name,
            success=False,
            result="",
            summary=f"Skill '{skill.name}' failed: {message}{detail}",
            mode="error",
            error=message,
        )
