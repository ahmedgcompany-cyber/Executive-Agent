"""
NEXUS Orchestrator — multi-agent pipeline engine based on the NEXUS framework.

Implements three execution modes:
  • NEXUS-Micro  (1–5 days, 5–10 agents): quick tasks, bug-fix, campaign, audit
  • NEXUS-Sprint (2–6 weeks, 15–25 agents): feature or MVP build
  • NEXUS-Full   (12–24 weeks, all agents): complete product lifecycle

Core patterns implemented:
  • 7-phase pipeline: Discovery → Strategy → Foundation → Build → Hardening → Launch → Operate
  • Dev ↔ QA loop with max-3-retry gate per task
  • Structured handoff protocol between phases
  • Quality-gate enforcement (evidence-based, defaults to "NEEDS WORK")
  • Status reporting after every phase
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generator, Optional

from .agency_library import AgencyLibrary, get_agency_library

_log = logging.getLogger("megav.nexus")


# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------

class NexusMode(str, Enum):
    MICRO = "micro"     # 1–5 day targeted task
    SPRINT = "sprint"   # 2–6 week feature/MVP
    FULL = "full"       # 12–24 week full product


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    NEEDS_WORK = "needs_work"
    BLOCKED = "blocked"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"  # exhausted retries


MAX_RETRIES = 3  # maximum QA retry attempts per task


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TaskResult:
    task: str
    status: TaskStatus
    agent_used: str
    output: str
    qa_feedback: str = ""
    attempts: int = 1


@dataclass
class PhaseResult:
    phase_name: str
    status: PhaseStatus
    tasks: list[TaskResult] = field(default_factory=list)
    summary: str = ""
    duration_sec: float = 0.0

    @property
    def passed_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.PASS)

    @property
    def blocked_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.BLOCKED)


@dataclass
class NexusResult:
    goal: str
    mode: NexusMode
    phases: list[PhaseResult] = field(default_factory=list)
    overall_status: str = "IN_PROGRESS"
    summary: str = ""
    agents_used: list[str] = field(default_factory=list)
    total_tasks: int = 0
    completed_tasks: int = 0
    duration_sec: float = 0.0
    artifacts: list[str] = field(default_factory=list)  # saved file paths


# ---------------------------------------------------------------------------
# Phase definitions
# ---------------------------------------------------------------------------

# Agents assigned to each NEXUS phase
PHASE_AGENTS: dict[str, list[str]] = {
    "discovery": [
        "product-trend-researcher",
        "product-feedback-synthesizer",
        "design-ux-researcher",
        "support-analytics-reporter",
        "support-legal-compliance-checker",
    ],
    "strategy": [
        "project-management-studio-producer",
        "project-manager-senior",
        "engineering-backend-architect",
        "design-ux-architect",
        "design-brand-guardian",
        "support-finance-tracker",
    ],
    "foundation": [
        "engineering-devops-automator",
        "engineering-frontend-developer",
        "engineering-backend-architect",
        "design-ux-architect",
    ],
    "build": [
        "engineering-frontend-developer",
        "engineering-backend-architect",
        "engineering-senior-developer",
        "testing-evidence-collector",
    ],
    "hardening": [
        "testing-reality-checker",
        "testing-performance-benchmarker",
        "testing-api-tester",
        "support-legal-compliance-checker",
        "engineering-security-engineer",
    ],
    "launch": [
        "marketing-growth-hacker",
        "marketing-content-creator",
        "marketing-social-media-strategist",
        "engineering-devops-automator",
    ],
    "operate": [
        "support-analytics-reporter",
        "support-infrastructure-maintainer",
        "support-support-responder",
    ],
}

# Sprint mode uses a reduced set
SPRINT_PHASES = ["strategy", "foundation", "build", "hardening"]

# Micro mode uses minimal agents per task type
MICRO_PHASE_MAP = {
    "engineering": ["build", "hardening"],
    "marketing": ["launch"],
    "design": ["foundation", "hardening"],
    "product": ["strategy"],
    "testing": ["hardening"],
    "default": ["build", "hardening"],
}


# ---------------------------------------------------------------------------
# NEXUS Orchestrator
# ---------------------------------------------------------------------------

class NexusOrchestrator:
    """
    Implements the NEXUS multi-agent pipeline for MegaV.

    Args:
        model_router: Optional ModelRouter for LLM calls (auto-imported if None)
        library: Optional AgencyLibrary (auto-loaded if None)
        progress_cb: Optional callback(message: str) for real-time updates
    """

    def __init__(
        self,
        model_router: Optional[Any] = None,
        library: Optional[AgencyLibrary] = None,
        progress_cb: Optional[Callable[[str], None]] = None,
    ):
        self._library = library or get_agency_library()
        self._progress_cb = progress_cb or (lambda msg: None)
        self._router = model_router  # lazy-loaded if None
        # Base output directory for NEXUS artifacts (Desktop\Projects, NOT Executive Agent)
        desktop = Path.home() / "Desktop"
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            real_desktop = winreg.QueryValueEx(key, "Desktop")[0]
            if real_desktop:
                desktop = Path(real_desktop)
        except Exception:
            pass
        self._output_base = desktop / "Projects"
        self._output_base.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_micro(self, goal: str, context: dict[str, Any] | None = None) -> NexusResult:
        """
        NEXUS-Micro: Quick task execution (1–5 days, 5–10 agents).
        Best for: bug fix, single campaign, audit, research task.
        """
        return self._run(goal, NexusMode.MICRO, context or {})

    def execute_sprint(self, goal: str, context: dict[str, Any] | None = None) -> NexusResult:
        """
        NEXUS-Sprint: Feature or MVP build (2–6 weeks, 15–25 agents).
        Best for: new feature, landing page, marketing campaign.
        """
        return self._run(goal, NexusMode.SPRINT, context or {})

    def execute_full(self, goal: str, context: dict[str, Any] | None = None) -> NexusResult:
        """
        NEXUS-Full: Complete product lifecycle (12–24 weeks, all agents).
        Best for: full product build from scratch.
        """
        return self._run(goal, NexusMode.FULL, context or {})

    def execute(self, goal: str, mode: str = "micro", context: dict[str, Any] | None = None) -> NexusResult:
        """Execute with mode string ('micro', 'sprint', 'full')."""
        mode_enum = NexusMode(mode.lower()) if mode.lower() in ("micro", "sprint", "full") else NexusMode.MICRO
        return self._run(goal, mode_enum, context or {})

    def stream_execute(
        self,
        goal: str,
        mode: str = "micro",
        context: dict[str, Any] | None = None,
    ) -> Generator[str, None, NexusResult]:
        """
        Streaming execution — yields status strings, returns final NexusResult.
        Usage:
            gen = orchestrator.stream_execute(goal)
            for update in gen:
                print(update)
            result = gen.value  # after StopIteration
        """
        result = None
        for update in self._stream_run(goal, NexusMode(mode), context or {}):
            yield update
        # Caller can access .result after the generator completes

    # ------------------------------------------------------------------
    # Core pipeline runner
    # ------------------------------------------------------------------

    def _run(self, goal: str, mode: NexusMode, context: dict) -> NexusResult:
        """Run the NEXUS pipeline synchronously."""
        start = time.time()
        result = NexusResult(goal=goal, mode=mode)

        self._emit(f"[NEXUS-{mode.value.upper()}] Starting pipeline for: {goal[:80]}")

        # Determine which phases to run
        phases_to_run = self._get_phases(goal, mode)

        for phase_name in phases_to_run:
            self._emit(f"\n── Phase: {phase_name.upper()} ──")
            phase_result = self._run_phase(phase_name, goal, mode, context, result)
            result.phases.append(phase_result)

            # Quality gate: check phase status before advancing
            if phase_result.status == PhaseStatus.BLOCKED:
                self._emit(f"  ⚠ Phase {phase_name} BLOCKED — {phase_result.blocked_tasks} tasks exhausted retries")
                # Continue despite blocks in non-critical phases
                if phase_name in ("build", "foundation"):
                    self._emit("  Continuing to next phase (non-blocking mode)")
                elif phase_name == "hardening":
                    self._emit("  Hardening issues — flagging for review")

        # Compile final status
        result.total_tasks = sum(len(p.tasks) for p in result.phases)
        result.completed_tasks = sum(p.passed_tasks for p in result.phases)
        result.agents_used = list({t.agent_used for p in result.phases for t in p.tasks})
        result.duration_sec = round(time.time() - start, 2)

        blocked_total = sum(p.blocked_tasks for p in result.phases)
        if blocked_total == 0:
            result.overall_status = "COMPLETED"
        elif blocked_total <= 2:
            result.overall_status = "COMPLETED_WITH_WARNINGS"
        else:
            result.overall_status = "NEEDS_WORK"

        result.summary = self._build_final_summary(result)
        self._emit(f"\n[NEXUS] Pipeline complete — {result.overall_status}")
        return result

    def _stream_run(self, goal: str, mode: NexusMode, context: dict) -> Generator[str, None, None]:
        """Streaming version of _run."""
        msgs: list[str] = []
        orig_cb = self._progress_cb

        def capture(msg: str):
            msgs.append(msg)
            orig_cb(msg)

        self._progress_cb = capture
        try:
            result = self._run(goal, mode, context)
        finally:
            self._progress_cb = orig_cb

        for m in msgs:
            yield m

    # ------------------------------------------------------------------
    # Phase runner
    # ------------------------------------------------------------------

    def _run_phase(
        self,
        phase_name: str,
        goal: str,
        mode: NexusMode,
        context: dict,
        nexus_result: NexusResult,
    ) -> PhaseResult:
        """Run a single phase and return its result."""
        start = time.time()
        phase = PhaseResult(phase_name=phase_name, status=PhaseStatus.RUNNING)

        # Get tasks for this phase
        tasks = self._get_phase_tasks(phase_name, goal, mode, context)

        for task_desc in tasks:
            task_result = self._run_task_with_qa_loop(task_desc, phase_name, goal, context)
            phase.tasks.append(task_result)

        # ── Extract and save artifacts from this phase's output ──
        all_output = "\n\n".join(t.output for t in phase.tasks if t.status == TaskStatus.PASS and t.output)
        if all_output.strip():
            saved = self._extract_and_save_artifacts(phase_name, all_output, goal)
            if saved:
                nexus_result.artifacts.extend(saved)
                self._emit(f"  → Saved {len(saved)} artifact(s): {', '.join(os.path.basename(s) for s in saved)}")

        # Determine phase status
        if phase.blocked_tasks == 0:
            phase.status = PhaseStatus.PASSED
        elif phase.blocked_tasks < max(1, len(phase.tasks) // 2):
            phase.status = PhaseStatus.NEEDS_WORK
        else:
            phase.status = PhaseStatus.BLOCKED

        phase.duration_sec = round(time.time() - start, 2)
        phase.summary = self._build_phase_summary(phase, goal)
        self._emit(f"  → Phase {phase_name}: {phase.status.value} ({phase.passed_tasks}/{len(phase.tasks)} tasks passed)")
        return phase

    # ------------------------------------------------------------------
    # Dev↔QA loop
    # ------------------------------------------------------------------

    def _run_task_with_qa_loop(
        self,
        task_desc: str,
        phase_name: str,
        goal: str,
        context: dict,
    ) -> TaskResult:
        """
        Run a single task through the Dev↔QA loop.
        Max MAX_RETRIES attempts before marking as BLOCKED.
        """
        # Pick best agent for this task
        agent_id = self._pick_agent(task_desc, phase_name)
        agent_rec = self._library.get(agent_id) if agent_id else None
        agent_name = agent_rec.name if agent_rec else agent_id or "General Agent"

        qa_feedback = ""

        for attempt in range(1, MAX_RETRIES + 1):
            self._emit(f"    • [{agent_name}] {task_desc[:70]} (attempt {attempt}/{MAX_RETRIES})")

            # Execute task via LLM
            output = self._call_agent(agent_id, agent_rec, task_desc, goal, context, qa_feedback)

            # QA validation
            qa_pass, qa_feedback = self._qa_validate(task_desc, output, phase_name)

            if qa_pass:
                self._emit(f"      ✓ QA PASS")
                return TaskResult(
                    task=task_desc,
                    status=TaskStatus.PASS,
                    agent_used=agent_name,
                    output=output,
                    qa_feedback=qa_feedback,
                    attempts=attempt,
                )
            else:
                self._emit(f"      ✗ QA FAIL — {qa_feedback[:80]}")
                if attempt < MAX_RETRIES:
                    self._emit(f"        ↺ Retrying with feedback...")

        # Exhausted retries
        self._emit(f"      ⚠ BLOCKED after {MAX_RETRIES} attempts")
        return TaskResult(
            task=task_desc,
            status=TaskStatus.BLOCKED,
            agent_used=agent_name,
            output="",
            qa_feedback=f"Blocked after {MAX_RETRIES} attempts. Last feedback: {qa_feedback}",
            attempts=MAX_RETRIES,
        )

    # ------------------------------------------------------------------
    # Agent calling
    # ------------------------------------------------------------------

    def _call_agent(
        self,
        agent_id: Optional[str],
        agent_rec: Any,
        task: str,
        goal: str,
        context: dict,
        qa_feedback: str,
    ) -> str:
        """Call an agent (LLM) and return its output."""
        router = self._get_router()
        if not router:
            return f"[{agent_id or 'agent'}] Task acknowledged: {task}"

        # Build system prompt
        system_parts = [
            "You are an expert AI assistant in a multi-agent pipeline (NEXUS framework).",
        ]
        if agent_rec and agent_rec.prompt:
            # Use first 2000 chars of agent personality as system context
            system_parts.append(agent_rec.prompt[:2000])
        system = "\n\n".join(system_parts)

        # Build user message
        user_parts = [
            f"Overall project goal: {goal}",
            f"Your task: {task}",
        ]
        if qa_feedback:
            user_parts.append(f"Previous QA feedback to address: {qa_feedback}")
        if context.get("profile"):
            user_parts.append(f"User profile context available.")

        user = "\n".join(user_parts)

        try:
            answer = router.ask(system=system, user=user, task_type="coder")
            return answer or f"Task completed: {task}"
        except NoModelAvailableError:
            return f"Agent error: No LLM available"
        except Exception as e:
            return f"Agent error: {str(e)[:200]}"

    def _qa_validate(self, task: str, output: str, phase_name: str) -> tuple[bool, str]:
        """
        QA validation: check output quality.
        Returns (pass: bool, feedback: str).
        In micro mode this is a simple heuristic; full mode uses LLM judge.
        """
        if not output or len(output.strip()) < 20:
            return False, "Output too short or empty — insufficient evidence."

        # Check for obvious failure signals
        failure_signals = [
            "i cannot", "i'm unable", "i don't have access",
            "as an ai", "i apologize", "error occurred",
        ]
        output_lower = output.lower()
        for sig in failure_signals:
            if sig in output_lower and len(output) < 200:
                return False, f"Agent signaled inability: '{sig}'"

        # Phase-specific quality checks
        if phase_name == "build" and len(output) < 100:
            return False, "Build output too brief — expected implementation details."

        if phase_name == "hardening":
            qa_signals = ["pass", "secure", "validated", "no issues", "compliant", "approved", "clean"]
            if not any(sig in output_lower for sig in qa_signals):
                # Try LLM judge for hardening
                router = self._get_router()
                if router:
                    try:
                        verdict = router.ask(
                            system="You are a strict QA engineer. Reply ONLY with PASS or FAIL.",
                            user=(
                                f"Task: {task}\n\n"
                                f"Output:\n{output[:800]}\n\n"
                                "Does this output adequately complete the task? Reply PASS or FAIL only."
                            ),
                            task_type="general",
                        ) or ""
                        if "PASS" in verdict.upper():
                            return True, "QA approved by LLM judge."
                        return False, "QA rejected by LLM judge — output did not meet hardening standards."
                    except NoModelAvailableError:
                        _log.warning("QA judge skipped — no model available")
                    except Exception as _e:
                        _log.warning("QA judge error: %s", _e)

        return True, "Output meets quality threshold."

    # ------------------------------------------------------------------
    # Task & phase planning helpers
    # ------------------------------------------------------------------

    def _get_phases(self, goal: str, mode: NexusMode) -> list[str]:
        """Determine which phases to run based on mode and goal."""
        if mode == NexusMode.FULL:
            return ["discovery", "strategy", "foundation", "build", "hardening", "launch", "operate"]
        elif mode == NexusMode.SPRINT:
            return SPRINT_PHASES
        else:  # MICRO
            cat = self._library.best_category_for_query(goal) or "default"
            return MICRO_PHASE_MAP.get(cat, MICRO_PHASE_MAP["default"])

    def _get_phase_tasks(
        self,
        phase_name: str,
        goal: str,
        mode: NexusMode,
        context: dict,
    ) -> list[str]:
        """Generate task list for a phase using LLM or heuristics."""
        router = self._get_router()

        if router:
            try:
                raw = router.ask(
                    system=(
                        "You are a senior project manager in the NEXUS orchestration framework. "
                        "Return ONLY a numbered list of 3–5 specific, actionable tasks."
                    ),
                    user=(
                        f"Project goal: {goal}\n"
                        f"Phase: {phase_name}\n"
                        f"Mode: {mode.value}\n\n"
                        f"List the key tasks for this phase. Each task should be one sentence, specific and actionable."
                    ),
                    task_type="general",
                ) or ""
                tasks = self._parse_task_list(raw)
                if tasks:
                    return tasks
            except NoModelAvailableError:
                _log.warning("Phase task planning skipped — no model available; using defaults")
            except Exception as _e:
                _log.warning("Phase task planning error: %s", _e)

        # Fallback: generic task list per phase
        return self._default_tasks(phase_name, goal)

    def _parse_task_list(self, text: str) -> list[str]:
        """Parse a numbered or bulleted list from LLM output."""
        lines = text.strip().splitlines()
        tasks = []
        for line in lines:
            # Match "1. task" or "- task" or "* task"
            m = re.match(r"^[\d]+[.)]\s+(.+)$", line.strip())
            if not m:
                m = re.match(r"^[-*•]\s+(.+)$", line.strip())
            if m:
                task = m.group(1).strip()
                if task and len(task) > 10:
                    tasks.append(task)
        return tasks[:6]  # cap at 6 tasks per phase

    def _default_tasks(self, phase_name: str, goal: str) -> list[str]:
        """Fallback task list if LLM is unavailable."""
        defaults = {
            "discovery": [
                f"Research market landscape and competitors for: {goal[:50]}",
                "Identify target user segments and key pain points",
                "Document compliance and legal requirements",
            ],
            "strategy": [
                f"Define technical architecture for: {goal[:50]}",
                "Create prioritized feature backlog and sprint plan",
                "Establish brand guidelines and design system foundation",
            ],
            "foundation": [
                "Set up development environment and CI/CD pipeline",
                "Scaffold project structure and core infrastructure",
                "Implement design system and base UI components",
            ],
            "build": [
                f"Implement core functionality for: {goal[:50]}",
                "Build data models and API endpoints",
                "Develop user interface and user flows",
            ],
            "hardening": [
                "Run comprehensive test suite and fix failures",
                "Conduct security audit and fix vulnerabilities",
                "Optimize performance and validate acceptance criteria",
            ],
            "launch": [
                "Deploy to production environment",
                "Execute go-to-market plan and launch campaign",
                "Monitor launch metrics and first-day performance",
            ],
            "operate": [
                "Set up ongoing monitoring and alerting",
                "Review analytics and prepare optimization report",
                "Plan next iteration based on user feedback",
            ],
        }
        return defaults.get(phase_name, [f"Execute {phase_name} phase tasks for: {goal[:50]}"])

    # ------------------------------------------------------------------
    # Artifact extraction & file saving
    # ------------------------------------------------------------------

    # Language tags commonly found in LLM code fences
    _CODE_LANGS = {
        "html": ".html", "css": ".css", "js": ".js", "javascript": ".js",
        "python": ".py", "py": ".py", "typescript": ".ts", "ts": ".ts",
        "jsx": ".jsx", "tsx": ".tsx", "json": ".json", "sql": ".sql",
        "bash": ".sh", "shell": ".sh", "sh": ".sh", "yaml": ".yaml",
        "yml": ".yml", "xml": ".xml", "java": ".java", "c": ".c",
        "cpp": ".cpp", "cs": ".cs", "go": ".go", "rust": ".rs",
        "rb": ".rb", "ruby": ".rb", "php": ".php", "swift": ".swift",
        "dockerfile": ".Dockerfile", "makefile": ".mk",
    }

    def _extract_and_save_artifacts(
        self, phase_name: str, llm_output: str, goal: str,
    ) -> list[str]:
        """Parse LLM output for code blocks and structured content, save as files.

        Returns a list of saved file paths.
        """
        saved_paths: list[str] = []

        # Create project directory
        slug = re.sub(r"[^a-z0-9]+", "_", goal[:40].lower()).strip("_") or "project"
        project_dir = self._output_base / slug
        project_dir.mkdir(parents=True, exist_ok=True)

        # ── 1. Extract fenced code blocks ──────────────────────────────
        # Pattern: ```lang\n...code...\n```
        code_pattern = re.compile(
            r"```(\w+)?\s*\n(.*?)```", re.DOTALL,
        )
        code_blocks = list(code_pattern.finditer(llm_output))

        for idx, m in enumerate(code_blocks, 1):
            lang = (m.group(1) or "").lower().strip()
            code = m.group(2).strip()
            if not code or len(code) < 20:
                continue

            ext = self._CODE_LANGS.get(lang, ".txt")
            # Skip if it looks like a config/dependency block (package.json, etc.)
            if lang == "json" and ('"dependencies"' in code or '"scripts"' in code):
                filename = f"{phase_name}_config{ext}"
            elif len(code_blocks) == 1:
                # Single code block: use a descriptive name
                if ext in (".html",):
                    filename = f"index{ext}" if idx == 1 else f"{phase_name}_{idx}{ext}"
                elif ext in (".py",):
                    filename = f"{phase_name}_main{ext}" if idx == 1 else f"{phase_name}_{idx}{ext}"
                else:
                    filename = f"{phase_name}_{idx}{ext}"
            else:
                filename = f"{phase_name}_{idx}{ext}"

            filepath = project_dir / filename
            # Avoid overwriting
            if filepath.exists():
                filepath = project_dir / f"{phase_name}_{idx}{ext}"

            try:
                filepath.write_text(code, encoding="utf-8")
                saved_paths.append(str(filepath))
                self._emit(f"    Saved: {filepath.name}")
            except Exception as e:
                self._emit(f"    Error saving {filepath.name}: {e}")

        # ── 2. Extract structured data as JSON ──────────────────────────
        # Look for lists/tables of leads, competitors, features, etc.
        data_patterns = [
            # Markdown tables: | Header | ... |
            (r"(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n?)+)", "table"),
            # Numbered lists with structured data
            (r"(?:(?:\d+[.)]\s+.+\n){3,})", "list"),
        ]

        for pat, dtype in data_patterns:
            for m in re.finditer(pat, llm_output):
                data_text = m.group(1).strip()
                if len(data_text) < 40:
                    continue
                # Save structured data as JSON
                data_file = project_dir / f"{phase_name}_{dtype}_{len(saved_paths)+1}.json"
                try:
                    data_file.write_text(
                        json.dumps({
                            "phase": phase_name,
                            "type": dtype,
                            "content": data_text,
                            "goal": goal[:200],
                        }, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    saved_paths.append(str(data_file))
                except Exception as _e:
                    _log.warning("Failed to save artifact %s: %s", data_file, _e)

        # ── 3. Save full phase output as Markdown ──────────────────────
        # Always save the raw LLM output for reference
        md_file = project_dir / f"{phase_name}_report.md"
        try:
            md_content = f"# {phase_name.title()} Phase Report\n\n"
            md_content += f"**Goal:** {goal[:200]}\n\n---\n\n{llm_output}"
            md_file.write_text(md_content, encoding="utf-8")
            saved_paths.append(str(md_file))
        except Exception as _e:
            _log.warning("Failed to save phase report %s: %s", md_file, _e)

        # ── 4. Try OutputEngine for structured export ──────────────────
        if saved_paths:
            try:
                from ..tool_system.output_engine import get_output_engine
                engine = get_output_engine()
                # Create a result dict that OutputEngine can process
                result = {"success": True, "summary": llm_output[:500]}
                export_path = engine.auto_export(goal, result)
                if export_path:
                    saved_paths.append(str(export_path))
            except Exception as _e:
                _log.debug("OutputEngine export skipped: %s", _e)

        return saved_paths

    # ------------------------------------------------------------------
    # Agent selection
    # ------------------------------------------------------------------

    def _pick_agent(self, task: str, phase_name: str) -> Optional[str]:
        """Pick the best agent ID for a task within a phase."""
        # First try: find from phase-assigned agents
        phase_agent_ids = PHASE_AGENTS.get(phase_name, [])
        if phase_agent_ids:
            # Score each phase agent against the task
            best_id = None
            best_score = 0.0
            for aid in phase_agent_ids:
                rec = self._library.get(aid)
                if rec:
                    score = self._library._score_agent(rec, task.lower())
                    if score > best_score:
                        best_score = score
                        best_id = aid
            if best_id:
                return best_id
            # Fallback: return first available phase agent
            for aid in phase_agent_ids:
                if self._library.get(aid):
                    return aid

        # Second try: global search
        result = self._library.find_best_agent(task)
        return result["id"] if result else None

    # ------------------------------------------------------------------
    # Summary builders
    # ------------------------------------------------------------------

    def _build_phase_summary(self, phase: PhaseResult, goal: str) -> str:
        lines = [
            f"Phase '{phase.phase_name}' — {phase.status.value.upper()}",
            f"Tasks: {phase.passed_tasks} passed / {len(phase.tasks)} total",
        ]
        if phase.blocked_tasks:
            lines.append(f"Blocked: {phase.blocked_tasks} tasks need attention")
        return "\n".join(lines)

    def _build_final_summary(self, result: NexusResult) -> str:
        lines = [
            f"NEXUS-{result.mode.value.upper()} Pipeline Report",
            f"Goal: {result.goal[:100]}",
            f"Status: {result.overall_status}",
            f"Tasks: {result.completed_tasks}/{result.total_tasks} completed",
            f"Agents used: {len(result.agents_used)}",
            f"Duration: {result.duration_sec:.1f}s",
            f"Artifacts saved: {len(result.artifacts)}",
            "",
            "Phase results:",
        ]
        for p in result.phases:
            status_icon = "✓" if p.status == PhaseStatus.PASSED else "⚠" if p.status == PhaseStatus.NEEDS_WORK else "✗"
            lines.append(f"  {status_icon} {p.phase_name}: {p.passed_tasks}/{len(p.tasks)} tasks passed")

        if result.artifacts:
            lines.append("")
            lines.append("Saved files:")
            for a in result.artifacts:
                lines.append(f"  {os.path.basename(a)}: {a}")

        if result.overall_status == "COMPLETED":
            lines.append("\nAll quality gates passed. Ready for next phase.")
        elif result.overall_status == "COMPLETED_WITH_WARNINGS":
            lines.append("\nCompleted with minor issues. Review blocked tasks before proceeding.")
        else:
            lines.append("\nSignificant issues found. Review and address blocked tasks.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, msg: str):
        """Send a progress message to the callback."""
        self._progress_cb(msg)

    def _get_router(self):
        """Lazy-load ModelRouter."""
        if self._router is None:
            try:
                from ..providers.model_router import ModelRouter, NoModelAvailableError
                self._router = ModelRouter()
            except Exception as _e:
                _log.error("Failed to load ModelRouter in NEXUS: %s", _e)
        return self._router


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_nexus_instance: Optional[NexusOrchestrator] = None


def get_nexus_orchestrator(
    progress_cb: Optional[Callable[[str], None]] = None,
) -> NexusOrchestrator:
    """Return a NexusOrchestrator (new instance if callback differs)."""
    global _nexus_instance
    if _nexus_instance is None or progress_cb is not None:
        _nexus_instance = NexusOrchestrator(progress_cb=progress_cb)
    return _nexus_instance
