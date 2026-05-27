"""
SYSTEM MODE: REAL-WORLD AUTONOMOUS OPERATOR

Shared directive and self-repair engine for every agent in the MegaV system.
Import SelfRepairEngine and SYSTEM_DIRECTIVE wherever adaptive problem-solving
or system-mode awareness is needed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# System-mode directive text (injected into agent prompts as system context)
# ---------------------------------------------------------------------------

SYSTEM_DIRECTIVE = """
══════════════════════════════════════════════════════════════
SYSTEM MODE: REAL-WORLD AUTONOMOUS OPERATOR
══════════════════════════════════════════════════════════════

You are NOT a chatbot. You are an execution agent responsible for completing
real tasks using tools, logic, and adaptive problem solving.

CORE DIRECTIVES
───────────────
1. NO FAKE EXECUTION
   • Never simulate results — never assume success
   • Every output must come from a real tool action or a clearly-marked failure
   • If data is not found → return "NOT FOUND", never hallucinate

2. TOOL-FIRST BEHAVIOR
   • Use tools (browser, scripts, APIs, file I/O) for all real-world tasks
   • Do NOT rely on internal knowledge when live data is required

3. FAILURE IS NOT AN END
   • A failed step triggers the Self-Repair chain (see below)
   • Continue until maximum real completion is reached

SYSTEM ARCHITECTURE (MANDATORY EXECUTION ORDER)
────────────────────────────────────────────────
Search Layer (Bing / DDG HTML / APIs)
        ↓
Playwright (PRIMARY execution engine — automation, scraping, form-filling)
        ↓
HTTP Requests (fallback: urllib / requests / PowerShell Invoke-WebRequest)
        ↓
DDG Desktop Browser (OPTIONAL — visual only, NOT for scraping or automation)

BROWSER EXECUTION RULE
──────────────────────
PRIMARY ENGINE: Playwright / Chromium

When a browser task is required:
  Step 1 — Use Playwright (headless or stealth) — this is ALWAYS first
  Step 2 — If Playwright fails (CAPTCHA / block / crash) → apply Self-Repair:
              a. Retry with different user-agent or headless toggle
              b. Switch to stealth mode (hide webdriver flag)
              c. Fall back to direct HTTP requests (urllib / PowerShell)
  Step 3 — DuckDuckGo Desktop Browser is OPTIONAL — only open it when the
            user explicitly needs to VIEW a page visually. Never use it for
            scraping, form-filling, or automated data extraction.
  Step 4 — NEVER retry the same failing method twice without changing strategy

SEARCH PIPELINE RULE
────────────────────
When searching for data:
  Step 1 — Generate 3–5 diverse query variants per task
  Step 2 — Try DuckDuckGo HTML → Bing HTML → DDG Instant Answer → Direct HTTP
  Step 3 — Validate results: remove duplicates, skip noise domains
  Step 4 — If results are sparse after 3 queries → modify query wording and retry
  Step 5 — Extract structured data using BeautifulSoup (preferred) or stdlib parser

EXTRACTION RULE
───────────────
After fetching any page:
  1. Parse HTML with ExtractionEngine (BS4 + stdlib fallback)
  2. Extract: business name, website, email, phone, social links, JSON-LD
  3. Validate: confirm site loads, skip noise domains, remove duplicates
  4. Score leads by richness (email > phone > LinkedIn > description)

SELF-REPAIR CHAIN
─────────────────
When ANY problem occurs, execute this chain:
  1. IDENTIFY  — what exactly failed (error message, exit code, empty result)
  2. ANALYZE   — root cause (network? missing tool? bot block? parse error?)
  3. DETERMINE — the correct fix
  4. EXECUTE   — apply the fix (or log exact manual steps if code-execution is blocked)
  5. CONTINUE  — resume the task from the point of failure

This chain applies to:
  • Missing tools / packages
  • Browser failures
  • Network / timeout issues
  • Parsing / selector errors
  • Empty or blocked search results
  • LLM unavailability

EXECUTION FLOW
──────────────
  1. Plan task (break into steps)
  2. Execute each step with real tools
  3. Validate each step result
  4. On failure → invoke Self-Repair chain
  5. Continue until maximum completion is reached

OUTPUT REQUIREMENTS
───────────────────
  ✓ Completed results (real data only)
  ✓ Partial results if full completion is not possible
  ✓ Error log: what failed | why | what fix was attempted | outcome

BEHAVIOUR STANDARD
──────────────────
Think like: a developer + a problem-solver + a system operator
NOT like  : a chatbot or a text generator

Real imperfect execution > fake perfect output.
══════════════════════════════════════════════════════════════
"""


# ---------------------------------------------------------------------------
# Problem diagnosis
# ---------------------------------------------------------------------------

@dataclass
class ProblemDiagnosis:
    """Encapsulates a diagnosed problem and its recommended fix."""
    error: str
    category: str
    fix_description: str
    fix_action: str
    severity: str = "medium"          # low | medium | high | critical
    fix_attempted: bool = False
    fix_succeeded: bool = False
    attempts: int = 0

    def summary_line(self) -> str:
        status = "FIXED" if self.fix_succeeded else ("ATTEMPTED" if self.fix_attempted else "PENDING")
        return f"[{status}] {self.category} — {self.fix_description}"

    def full_log(self) -> str:
        status = "FIXED" if self.fix_succeeded else ("ATTEMPTED" if self.fix_attempted else "DIAGNOSED")
        return (
            f"[SELF-REPAIR {status}]\n"
            f"  Problem  : {self.error[:120]}\n"
            f"  Category : {self.category}\n"
            f"  Fix      : {self.fix_description}\n"
            f"  Action   : {self.fix_action}\n"
            f"  Severity : {self.severity}\n"
        )


# ---------------------------------------------------------------------------
# Self-repair engine
# ---------------------------------------------------------------------------

class SelfRepairEngine:
    """
    Diagnoses failures and determines + applies automated fixes.

    Used by AgentLoop, BrowserAgent, and any agent that needs adaptive
    problem-solving behaviour.

    Usage:
        engine = SelfRepairEngine(emit_cb=self._emit)
        diagnosis = engine.diagnose(error_string)
        engine.apply_fix(diagnosis, context)
    """

    # (keywords, category, fix_description, fix_action, severity)
    _ERROR_PATTERNS: list[tuple] = [
        # ── Browser / bot detection ────────────────────────────────────
        (["captcha", "verify you are human", "i am not a robot", "bot detection",
          "403 forbidden", "403", "access denied", "blocked by", "rate limit"],
         "bot_detection",
         "Switch to headless Playwright with stealth mode or change IP / user-agent",
         "playwright_stealth", "high"),

        # ── Network / connectivity ─────────────────────────────────────
        (["timeout", "timed out", "read timed out", "connection refused",
          "connection reset", "connection error", "network unreachable",
          "ssl", "certificate"],
         "network_error",
         "Retry with extended timeout or switch to alternative data source",
         "retry_extended", "medium"),

        # ── Playwright / browser automation ───────────────────────────
        (["playwright not installed", "playwright not found",
          "no module named 'playwright'"],
         "missing_playwright",
         "Install Playwright: pip install playwright && playwright install chromium",
         "install_playwright", "high"),

        (["browser disconnected", "target closed", "page crashed",
          "execution context was destroyed"],
         "browser_crash",
         "Close and reopen browser session with fresh context",
         "restart_browser", "medium"),

        (["element not found", "no element matches", "could not find element",
          "selector not found", "timeout waiting for selector"],
         "element_missing",
         "Update selector strategy; try text-based or XPath selectors as fallback",
         "update_selector", "medium"),

        # ── DuckDuckGo / search ────────────────────────────────────────
        (["duckduckgo unavailable", "ddg blocked", "duckduckgo not installed"],
         "ddg_unavailable",
         "Fall back to Bing HTML search, then direct HTTP requests",
         "fallback_search", "medium"),

        (["0 results", "no results found", "empty result", "nothing found"],
         "no_data",
         "Broaden search query, try alternative source or change search engine",
         "change_query", "low"),

        # ── Missing packages / tools ───────────────────────────────────
        (["no module named", "modulenotfounderror", "importerror",
          "cannot import name"],
         "missing_package",
         "Install missing Python package via pip",
         "install_package", "high"),

        (["winget not found", "winget: command not found",
          "'winget' is not recognized"],
         "missing_winget",
         "Use PowerShell Invoke-WebRequest to download installer directly",
         "powershell_download", "medium"),

        # ── LLM ───────────────────────────────────────────────────────
        (["ollama connection refused", "no llm available", "llm not available",
          "model not found", "model not loaded"],
         "llm_unavailable",
         "Continue with web research data only; LLM enrichment skipped",
         "skip_llm", "low"),

        # ── Permissions / file system ──────────────────────────────────
        (["permission denied", "access is denied", "operation not permitted",
          "winerror 5"],
         "permissions",
         "Run as administrator or check file/directory permissions",
         "check_permissions", "high"),

        (["file not found", "no such file or directory", "path does not exist"],
         "missing_file",
         "Verify file path and create parent directories if needed",
         "check_path", "medium"),
    ]

    def __init__(self, emit_cb: Optional[Callable[[str], None]] = None):
        self._emit = emit_cb or (lambda _: None)

    # ------------------------------------------------------------------

    def diagnose(self, error: str) -> ProblemDiagnosis:
        """Map an error string to a ProblemDiagnosis with fix details."""
        err_lower = error.lower()
        for keywords, category, fix_desc, fix_action, severity in self._ERROR_PATTERNS:
            if any(k in err_lower for k in keywords):
                return ProblemDiagnosis(
                    error=error,
                    category=category,
                    fix_description=fix_desc,
                    fix_action=fix_action,
                    severity=severity,
                )
        return ProblemDiagnosis(
            error=error,
            category="unknown",
            fix_description="Log error, try alternative approach or skip non-critical step",
            fix_action="try_alternative",
            severity="medium",
        )

    def apply_fix(self, diagnosis: ProblemDiagnosis, context: dict | None = None) -> bool:  # noqa: ARG002
        """
        Attempt the automated fix for the given diagnosis.
        Returns True if the fix was successfully applied.
        """
        diagnosis.fix_attempted = True
        diagnosis.attempts += 1
        action = diagnosis.fix_action
        self._emit(f"[SELF-REPAIR] {diagnosis.category} — {diagnosis.fix_description}")

        try:
            if action == "install_playwright":
                ok = self._install_playwright()
                diagnosis.fix_succeeded = ok
                return ok

            elif action == "install_package":
                pkg = self._extract_package_name(diagnosis.error)
                if pkg:
                    ok = self._pip_install(pkg)
                    diagnosis.fix_succeeded = ok
                    return ok

            elif action == "retry_extended":
                # Caller handles the retry; just signal that it's worth retrying
                diagnosis.fix_succeeded = True
                return True

            elif action in ("playwright_stealth", "fallback_search",
                            "change_query", "try_alternative",
                            "restart_browser", "update_selector",
                            "skip_llm", "check_permissions",
                            "check_path", "powershell_download"):
                # Strategy changes: don't claim success, just recommend retry
                diagnosis.fix_succeeded = False
                diagnosis.retry_recommended = True
                return False

        except Exception as exc:
            self._emit(f"[SELF-REPAIR] Fix execution error: {exc}")

        diagnosis.fix_succeeded = False
        return False

    # ------------------------------------------------------------------
    # Internal fix implementations
    # ------------------------------------------------------------------

    def _install_playwright(self) -> bool:
        self._emit("[SELF-REPAIR] Installing Playwright…")
        try:
            r1 = subprocess.run(
                [sys.executable, "-m", "pip", "install", "playwright", "-q"],
                capture_output=True, text=True, timeout=120,
            )
            if r1.returncode != 0:
                self._emit(f"[SELF-REPAIR] pip install failed: {r1.stderr[:200]}")
                return False
            r2 = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, text=True, timeout=300,
            )
            ok = r2.returncode == 0
            self._emit(f"[SELF-REPAIR] Playwright install {'succeeded' if ok else 'failed'}")
            return ok
        except Exception as exc:
            self._emit(f"[SELF-REPAIR] Playwright install error: {exc}")
            return False

    def _pip_install(self, package: str) -> bool:
        self._emit(f"[SELF-REPAIR] Installing package: {package}")
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", package, "-q"],
                capture_output=True, text=True, timeout=120,
            )
            ok = r.returncode == 0
            self._emit(f"[SELF-REPAIR] pip install {package} {'OK' if ok else 'FAILED'}")
            return ok
        except Exception as exc:
            self._emit(f"[SELF-REPAIR] pip install error: {exc}")
            return False

    @staticmethod
    def _extract_package_name(error: str) -> str | None:
        m = re.search(r"No module named '([^']+)'", error, re.IGNORECASE)
        if m:
            return m.group(1).split(".")[0]
        m = re.search(r"cannot import name .+ from '([^']+)'", error, re.IGNORECASE)
        if m:
            return m.group(1).split(".")[0]
        return None

    # ------------------------------------------------------------------
    # Convenience: wrap a callable with automatic self-repair on failure
    # ------------------------------------------------------------------

    async def run_with_repair(
        self,
        coro_factory: Callable,
        max_attempts: int = 3,
        context: dict | None = None,
    ) -> dict:
        """
        Execute coro_factory() up to max_attempts times.
        On failure, diagnose → fix → retry.

        coro_factory must be a zero-argument callable that returns an
        awaitable yielding a dict with 'success' and optionally 'error'.
        """
        import asyncio
        last_result: dict = {"success": False, "error": "Not started"}

        for attempt in range(1, max_attempts + 1):
            import inspect
            result = coro_factory()
            if inspect.isawaitable(result):
                result = await result

            if result.get("success"):
                return result

            error = result.get("error", "Unknown error")
            self._emit(f"[SELF-REPAIR] Attempt {attempt}/{max_attempts} failed: {error[:80]}")
            last_result = result

            if attempt < max_attempts:
                diag = self.diagnose(error)
                self._emit(diag.full_log())
                self.apply_fix(diag, context)
                # Brief back-off before retry
                await asyncio.sleep(min(2 ** (attempt - 1), 8))

        self._emit("[SELF-REPAIR] All attempts exhausted — returning partial result.")
        return last_result
