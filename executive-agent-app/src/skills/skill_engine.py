"""
Skill Engine — executes individual skills by their execution_type.

Execution types
---------------
  prompt   — inject SKILL.md as LLM system context, let the model respond
  script   — run the skill's shell/Python script via subprocess
  hybrid   — run any scripts first, then use SKILL.md as model context
"""

from __future__ import annotations

import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Optional

from .skill_registry import SkillRegistry
from .skill_selector import SkillMatch
from .skill_handlers import get_handler as _get_native_handler
from ..providers.model_router import NoModelAvailableError


class SkillEngine:
    """Executes skills based on their type (prompt / script / hybrid)."""

    def __init__(
        self,
        registry: SkillRegistry,
        model_router: Optional[Any] = None,
        progress_cb: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            registry:     Loaded SkillRegistry instance.
            model_router: ModelRouter for LLM calls (may be None — prompt skills
                          will return the raw context text instead).
            progress_cb:  Optional callback for real-time progress messages.
        """
        self._registry = registry
        self._router = model_router
        self._emit: Callable[[str], None] = progress_cb or (lambda _: None)

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def execute(
        self,
        match: SkillMatch,
        user_input: str,
        extra_context: Optional[dict] = None,
    ) -> dict:
        """Execute a skill by dispatching to the correct sub-executor.

        Args:
            match:         SkillMatch (from SkillSelector) describing which skill.
            user_input:    Original user query / goal text.
            extra_context: Optional dict of extra values (profile, chat_history…).

        Returns:
            dict with keys: success, result, summary, skill_id, execution_type, elapsed_s
        """
        skill = self._registry.get_by_id(match.skill_id)
        if not skill:
            return self._err(match.skill_id, "Skill definition not found")

        exec_type = skill.get("execution_type", "prompt")
        self._emit(f"[Skill:{skill['name']}] Executing ({exec_type})…")

        t0 = time.time()
        try:
            # ── 1. Native Python handler takes priority ──────────────────
            native = _get_native_handler(match.skill_id)
            if native:
                self._emit(f"  [native handler]")
                result = native(
                    user_input,
                    extra_context or {},
                    self._router,
                    self._emit,
                )
            # ── 2. Legacy execution paths ────────────────────────────────
            elif exec_type == "prompt":
                result = self._exec_prompt(skill, user_input, extra_context)
            elif exec_type == "script":
                result = self._exec_script(skill, user_input, extra_context)
            elif exec_type == "hybrid":
                result = self._exec_hybrid(skill, user_input, extra_context)
            else:
                result = self._err(match.skill_id, f"Unknown execution_type: {exec_type!r}")
        except Exception as exc:
            tb = traceback.format_exc()
            result = self._err(match.skill_id, f"Unhandled exception: {exc}", tb)

        elapsed = round(time.time() - t0, 2)
        result["skill_id"] = match.skill_id
        result["skill_name"] = skill.get("name", match.skill_id)
        result["execution_type"] = exec_type
        result["elapsed_s"] = elapsed
        return result

    def execute_by_id(
        self,
        skill_id: str,
        user_input: str,
        extra_context: Optional[dict] = None,
    ) -> dict:
        """Execute a skill directly by its id (bypasses selector)."""
        from .skill_selector import SkillMatch
        skill = self._registry.get_by_id(skill_id)
        if not skill:
            return self._err(skill_id, f"Unknown skill id: {skill_id!r}")
        match = SkillMatch(
            skill_id=skill_id,
            skill_name=skill.get("name", skill_id),
            score=1.0,
            category=skill.get("category", ""),
            execution_type=skill.get("execution_type", "prompt"),
            agent_affinity=skill.get("agent_affinity", []),
        )
        return self.execute(match, user_input, extra_context)

    # ------------------------------------------------------------------
    # Executors
    # ------------------------------------------------------------------

    def _exec_prompt(self, skill: dict, user_input: str, extra_context: Optional[dict]) -> dict:
        """Use SKILL.md as system context, call model with user input."""
        context_text = skill.get("context_text", "")
        skill_name = skill.get("name", skill["id"])

        if not context_text:
            # No SKILL.md — fall back to a generic prompt
            context_text = (
                f"You are using the '{skill_name}' skill to help the user. "
                f"Description: {skill.get('description', '')}"
            )

        system_prompt = (
            f"You are executing the '{skill_name}' skill.\n\n"
            f"--- SKILL CONTEXT ---\n{context_text[:4000]}\n--- END SKILL CONTEXT ---\n\n"
            f"Use the skill context above to fulfil the user's request as precisely as possible."
        )

        if self._router:
            try:
                # Use chat mode (system/user separation) so the model ANSWERS rather
                # than completing/echoing the combined prompt string
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_input},
                ]
                response = self._router.route_chat(messages, task_type="skill_execution")
                if response.get("success"):
                    msg = response.get("message", {})
                    text = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                    return {
                        "success": True,
                        "result": text,
                        "summary": text[:300],
                        "mode": "prompt",
                    }
                # Chat failed — last resort: try generate (handles providers without chat endpoint)
                response = self._router.route_generate(
                    user_input,
                    system_prompt=system_prompt,
                    task_type="skill_execution",
                )
                if response.get("success"):
                    text = response.get("response", "")
                    return {
                        "success": True,
                        "result": text,
                        "summary": text[:300],
                        "mode": "prompt",
                    }
                return self._err(skill["id"], response.get("error", "Model call failed"))
            except NoModelAvailableError:
                return {"success": False, "error": "No LLM available"}
        else:
            # No router — return the context text so caller can use it manually
            return {
                "success": True,
                "result": context_text,
                "summary": f"Skill context loaded for '{skill_name}'. Use this context to process the request.",
                "mode": "prompt_no_router",
                "system_prompt": system_prompt,
            }

    def _exec_script(self, skill: dict, user_input: str, extra_context: Optional[dict]) -> dict:
        """Run the first available script in skill["scripts"]."""
        scripts: list[str] = skill.get("scripts", [])
        if not scripts:
            return self._err(skill["id"], "No scripts defined for this skill")

        outputs = []
        for script_rel in scripts:
            script_path = self._registry.script_path(skill["id"], script_rel)
            if not script_path.exists():
                self._emit(f"  Script not found, skipping: {script_path}")
                continue

            self._emit(f"  Running script: {script_path.name}")
            result = self._run_script(script_path, user_input, extra_context)
            outputs.append(result)
            if not result.get("success"):
                break

        if not outputs:
            return self._err(skill["id"], "No scripts could be executed (files not found)")

        combined_output = "\n---\n".join(o.get("output", "") for o in outputs if o.get("output"))
        success = all(o.get("success") for o in outputs)
        return {
            "success": success,
            "result": combined_output,
            "summary": combined_output[:300] if combined_output else "Script(s) executed.",
            "mode": "script",
            "scripts_run": [o.get("script") for o in outputs],
        }

    def _exec_hybrid(self, skill: dict, user_input: str, extra_context: Optional[dict]) -> dict:
        """Run scripts (if any exist on disk), then use SKILL.md as prompt context."""
        script_result: Optional[dict] = None
        scripts: list[str] = skill.get("scripts", [])
        runnable = [
            s for s in scripts
            if self._registry.script_path(skill["id"], s).exists()
        ]

        if runnable:
            script_result = self._exec_script(skill, user_input, extra_context)
            self._emit(f"  Script phase complete — proceeding to prompt phase.")

        # Always run prompt phase for hybrid skills
        prompt_result = self._exec_prompt(skill, user_input, extra_context)

        if script_result and not script_result.get("success"):
            # Script failed — still return prompt result but flag the error
            prompt_result["script_warning"] = script_result.get("error", "Script phase failed")

        if script_result:
            # Merge script output into the final result
            combined = (
                (script_result.get("result") or "") + "\n\n" +
                (prompt_result.get("result") or "")
            ).strip()
            prompt_result["result"] = combined
            prompt_result["mode"] = "hybrid"

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
        """Run a single script file via subprocess.

        Python scripts (.py) are executed with the current interpreter.
        Shell scripts (.sh / .bat) are run directly.
        """
        script_name = script_path.name
        suffix = script_path.suffix.lower()

        try:
            if suffix == ".py":
                cmd = [sys.executable, str(script_path)]
            elif suffix == ".sh":
                cmd = ["bash", str(script_path)]
            elif suffix in (".bat", ".cmd"):
                cmd = ["cmd", "/c", str(script_path)]
            else:
                return {"success": False, "error": f"Unknown script type: {suffix}", "script": script_name}

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(script_path.parent),
                env=self._build_env(user_input, extra_context),
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            success = proc.returncode == 0
            return {
                "success": success,
                "output": output.strip(),
                "returncode": proc.returncode,
                "script": script_name,
                "error": proc.stderr.strip() if not success else None,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Script timed out after {timeout}s", "script": script_name}
        except FileNotFoundError as exc:
            return {"success": False, "error": f"Cannot run script: {exc}", "script": script_name}
        except Exception as exc:
            return {"success": False, "error": str(exc), "script": script_name}

    @staticmethod
    def _build_env(user_input: str, extra_context: Optional[dict]) -> dict:
        """Build environment variables for script execution."""
        import os
        env = os.environ.copy()
        env["EXEC_AGENT_INPUT"] = user_input[:2000]
        if extra_context:
            for k, v in extra_context.items():
                if isinstance(v, str):
                    env[f"EXEC_AGENT_{k.upper()}"] = v[:500]
        return env

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _err(skill_id: str, message: str, traceback_str: str = "") -> dict:
        return {
            "success": False,
            "error": message,
            "traceback": traceback_str,
            "result": "",
            "summary": f"Skill '{skill_id}' failed: {message}",
            "mode": "error",
        }
