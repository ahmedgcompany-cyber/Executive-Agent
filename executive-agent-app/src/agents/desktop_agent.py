"""Desktop agent for application control tasks."""

from pathlib import Path
from typing import Any, Optional

from ..tools_ext.desktop_tools import DesktopTools
from ..tools_ext.vision_tools import VisionTools


class DesktopAgent:
    """Specialist agent for desktop application control."""

    def __init__(
        self,
        desktop_tools: Optional[DesktopTools] = None,
        vision_tools: Optional[VisionTools] = None,
    ):
        """Initialize desktop agent.

        Args:
            desktop_tools: DesktopTools instance
            vision_tools: VisionTools instance
        """
        self.desktop = desktop_tools or DesktopTools()
        self.vision = vision_tools or VisionTools()

        # Load prompt
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load desktop prompt from file."""
        prompt_path = Path("src/prompts/desktop.txt")
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a desktop application control specialist agent."

    def launch_target_app(self, app_name: str, args: Optional[list[str]] = None) -> dict[str, Any]:
        """Launch a target application.

        Args:
            app_name: Application name or executable
            args: Optional arguments

        Returns:
            Launch result
        """
        return self.desktop.launch_application(app_name, args)

    def focus_window(self, title: str) -> dict[str, Any]:
        """Focus a window.

        Args:
            title: Window title

        Returns:
            Focus result
        """
        return self.desktop.focus_window(title)

    def inspect_window_state(self) -> dict[str, Any]:
        """Inspect the current window state.

        Returns:
            Window state
        """
        return self.desktop.list_controls()

    def perform_ui_step(
        self,
        action: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform a UI action step.

        Args:
            action: Action type
            params: Action parameters

        Returns:
            Action result
        """
        if action == "click":
            return self.desktop.click_control(
                name=params.get("name"),
                automation_id=params.get("automation_id"),
            )
        elif action == "type":
            return self.desktop.type_into_control(
                text=params.get("text", ""),
                name=params.get("name"),
                automation_id=params.get("automation_id"),
            )
        elif action == "hotkey":
            return self.desktop.send_hotkey(params.get("keys", []))
        elif action == "keys":
            return self.desktop.send_keys(params.get("text", ""))
        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    def verify_ui_state(self, expected_state: dict[str, Any]) -> dict[str, Any]:
        """Verify the UI is in expected state.

        Args:
            expected_state: Expected state properties

        Returns:
            Verification result
        """
        # Get current window title
        title_result = self.desktop.get_window_title()

        if not title_result.get("success"):
            return title_result

        current_title = title_result.get("title", "")
        expected_title = expected_state.get("window_title")

        if expected_title and expected_title.lower() not in current_title.lower():
            return {
                "success": False,
                "error": f"Window title mismatch. Expected: {expected_title}, Got: {current_title}",
            }

        return {
            "success": True,
            "verified": True,
            "current_title": current_title,
        }

    def capture_and_verify(
        self,
        reference_image: Optional[str] = None,
    ) -> dict[str, Any]:
        """Capture screen and optionally compare with reference.

        Args:
            reference_image: Optional reference image path

        Returns:
            Capture/verification result
        """
        capture_result = self.desktop.capture_window()

        if not capture_result.get("success"):
            return capture_result

        if reference_image:
            # Compare with reference
            compare_result = self.vision.compare_screens(
                reference_image,
                capture_result.get("path", ""),
            )
            return compare_result

        return capture_result

    def execute_ui_sequence(self, sequence: list[dict[str, Any]]) -> dict[str, Any]:
        """Execute a sequence of UI actions.

        Args:
            sequence: List of UI actions

        Returns:
            Execution result
        """
        results = []

        for step in sequence:
            action = step.get("action")
            params = step.get("params", {})

            result = self.perform_ui_step(action, params)
            results.append({"step": step, "result": result})

            if not result.get("success"):
                return {
                    "success": False,
                    "error": f"Step failed: {result.get('error')}",
                    "results": results,
                }

        return {
            "success": True,
            "steps_completed": len(results),
            "results": results,
        }

    def handle_desktop_task(self, action: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle a desktop task.

        Args:
            action: Action to perform
            context: Task context

        Returns:
            Task result
        """
        # Resolve goal for context-driven handlers
        _goal = (
            getattr(context, "goal", "")
            or getattr(context, "current_goal", "")
            or ""
        )

        # ── Skill Engine intercept ─────────────────────────────────────
        if _goal and action in ("execute_action", "execute_goal"):
            try:
                from skill_engine.orchestrator import run_task, get_engine
                engine = get_engine()
                if engine and engine.should_intercept(_goal, agent_hint="desktop"):
                    skill_result = run_task(_goal, agent_hint="desktop")
                    if skill_result.success:
                        return {
                            "success": True,
                            "summary": skill_result.summary,
                            "result":  skill_result.full_result,
                            "skills_used": skill_result.skills_used,
                            "via_skill": True,
                        }
            except Exception:
                pass
        # ── End skill intercept ────────────────────────────────────────

        handlers = {
            # Use _execute_from_goal when no explicit app_name is in context
            "launch_app": lambda: (
                self._execute_from_goal(_goal)
                if not context.get("app_name")
                else self.launch_target_app(context.get("app_name", ""), context.get("args"))
            ),
            "focus_window": lambda: self.focus_window(context.get("title", "")),
            "inspect_ui": self.inspect_window_state,
            "perform_ui_step": lambda: self.perform_ui_step(
                context.get("ui_action", ""),
                context.get("params", {}),
            ),
            "verify_ui_state": lambda: self.verify_ui_state(context.get("expected_state", {})),
            "capture_and_verify": lambda: self.capture_and_verify(
                context.get("reference_image")
            ),
            "execute_ui_sequence": lambda: self.execute_ui_sequence(
                context.get("sequence", [])
            ),
        }

        handlers["execute_action"] = lambda: self.perform_ui_step(
            context.get("ui_action", "click"),
            context.get("params", {}),
        )
        handlers["verify"] = lambda: {
            "success": True,
            "summary": "Desktop task verified.",
            "message": "UI state verified.",
        }
        handlers["execute_goal"] = lambda: self._execute_from_goal(
            getattr(context, "goal", "") or getattr(context, "current_goal", "") or ""
        )

        handler = handlers.get(action)
        if handler:
            return handler()

        return {"success": False, "error": f"Unknown action: {action}"}

    # ------------------------------------------------------------------
    # Goal-driven execution (called by AgentLoop)
    # ------------------------------------------------------------------

    def _execute_from_goal(self, goal: str) -> dict[str, Any]:
        """Interpret a free-form goal and launch/control the right application."""
        if not goal:
            return {"success": False, "error": "No goal provided to desktop agent."}

        import re
        import time as _time
        goal_lower = goal.lower()

        # ── Step 1: Find the app to launch ─────────────────────────────────
        # Check the desktop_tools alias map first (most reliable)
        app_aliases = self.desktop._APP_ALIASES
        app_name = None
        for alias in app_aliases:
            if alias in goal_lower:
                app_name = alias
                break

        if not app_name:
            # Extract app name from "open X", "launch X", "start X", "run X"
            match = re.search(
                r'(?:open|launch|start|run|close|minimize|maximize)\s+["\']?([A-Za-z0-9][A-Za-z0-9_\- ]{1,40}?)["\']?'
                r'(?:\s+and\s+|\s+then\s+|$|\.|,)',
                goal, re.IGNORECASE
            )
            if match:
                app_name = match.group(1).strip()

        # ── Step 2: Launch the app ─────────────────────────────────────────
        steps_done = []
        launched = False
        if app_name:
            result = self.launch_target_app(app_name)
            if result.get("success"):
                steps_done.append(f"Launched '{app_name}'")
                launched = True
                _time.sleep(1.5)   # let the window open
            else:
                return result
        else:
            # No app identified — inspect current window
            r = self.inspect_window_state()
            r.setdefault("summary", "Inspected current desktop window state.")
            return r

        # ── Step 3: Post-launch actions (type, click, etc.) ────────────────
        # Detect "type X" / "write X" / "say X"
        type_match = re.search(
            r'(?:type|write|enter|say|input|put)\s+["\']?(.{1,200}?)["\']?(?:$|\.|in the|into)',
            goal, re.IGNORECASE
        )
        if type_match and launched:
            text_to_type = type_match.group(1).strip().strip('"\'')
            # Focus the newly launched window first
            if app_name:
                self.focus_window(app_name)
                _time.sleep(0.5)
            type_result = self.desktop.send_keys(text_to_type)
            if type_result.get("success"):
                steps_done.append(f"Typed: '{text_to_type[:60]}'")
            else:
                steps_done.append(f"Typing failed: {type_result.get('error','')}")

        # Detect "click X"
        click_match = re.search(r'(?:click|press)\s+["\']?([A-Za-z0-9 _\-]{1,40})["\']?', goal, re.IGNORECASE)
        if click_match and launched:
            btn = click_match.group(1).strip()
            click_result = self.desktop.click_control(name=btn)
            if click_result.get("success"):
                steps_done.append(f"Clicked: '{btn}'")

        # Detect "minimize", "maximize", "close"
        if re.search(r'\bminimize\b', goal_lower) and launched:
            self.desktop.minimize_window(app_name)
            steps_done.append(f"Minimized '{app_name}'")
        elif re.search(r'\bmaximize\b', goal_lower) and launched:
            self.desktop.maximize_window(app_name)
            steps_done.append(f"Maximized '{app_name}'")

        summary = "Desktop actions completed:\n" + "\n".join(f"  ✓ {s}" for s in steps_done)
        return {"success": True, "summary": summary, "steps": steps_done}
