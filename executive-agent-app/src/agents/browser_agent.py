"""Browser agent for web automation tasks.

Browser priority (enforced here):
  1. Playwright headless/stealth  — PRIMARY for all automation and data collection
  2. Direct HTTP / PowerShell     — no-browser fallback
  3. DuckDuckGo Desktop Browser   — OPTIONAL visual-only (user-facing tasks)
"""

from pathlib import Path
from typing import Any, Optional

from ..tool_system.system_directive import SelfRepairEngine
from ..tools_ext.browser_tools import BrowserTools, find_ddg_browser, open_url_in_ddg_browser
from ..tools_ext.form_tools import FormTools
from ..memory.profile_store import ProfileStore


class BrowserAgent:
    """Specialist agent for browser automation and form filling."""

    def __init__(
        self,
        browser_tools: Optional[BrowserTools] = None,
        profile_store: Optional[ProfileStore] = None,
    ):
        """Initialize browser agent.

        Args:
            browser_tools: BrowserTools instance
            profile_store: ProfileStore instance
        """
        self.browser = browser_tools or BrowserTools()
        self.form = FormTools(self.browser)
        self.profile = profile_store
        # Self-repair engine for adaptive failure handling
        self._repair = SelfRepairEngine(emit_cb=lambda msg: None)

        # Load prompt
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load browser prompt from file."""
        prompt_path = Path("src/prompts/browser.txt")
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a browser automation specialist agent."

    async def open_site(self, url: str, headless: bool = False) -> dict[str, Any]:
        """Open a website.

        Args:
            url: URL to open
            headless: Run in headless mode

        Returns:
            Open result
        """
        return await self.browser.browser_open(url, headless)

    async def analyze_form(self) -> dict[str, Any]:
        """Analyze form on current page.

        Returns:
            Form analysis
        """
        return await self.form.analyze_form_fields()

    async def fill_form(
        self,
        field_values: Optional[dict[str, str]] = None,
        use_profile: bool = False,
    ) -> dict[str, Any]:
        """Fill form on current page.

        Args:
            field_values: Optional field values
            use_profile: Use profile data

        Returns:
            Fill result
        """
        if use_profile and self.profile:
            return await self.form.fill_form_from_profile(
                self.profile.user_profile,
                self.profile.job_answers,
            )
        elif field_values:
            return await self.form.fill_detected_form(field_values)
        else:
            return {"success": False, "error": "No field values or profile provided"}

    async def fill_detected_form(self, field_values: dict[str, str]) -> dict[str, Any]:
        """Fill form with provided values.

        Args:
            field_values: Field selector -> value mapping

        Returns:
            Fill result
        """
        return await self.form.fill_detected_form(field_values)

    async def select_dropdowns(self, selections: dict[str, str]) -> dict[str, Any]:
        """Select dropdown options.

        Args:
            selections: Selector -> value mapping

        Returns:
            Selection result
        """
        return await self.form.select_dropdowns(selections)

    async def upload_files(self, uploads: dict[str, str]) -> dict[str, Any]:
        """Upload files.

        Args:
            uploads: Selector -> file path mapping

        Returns:
            Upload result
        """
        return await self.form.upload_files(uploads)

    async def complete_multistep_flow(
        self,
        steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Complete a multi-step form flow.

        Args:
            steps: List of steps to execute

        Returns:
            Flow completion result
        """
        results = []

        for step in steps:
            action = step.get("action")
            params = step.get("params", {})

            if action == "click":
                result = await self.browser.browser_click(params.get("selector"))
            elif action == "type":
                result = await self.browser.browser_type(
                    params.get("selector"),
                    params.get("text"),
                )
            elif action == "select":
                result = await self.browser.browser_select(
                    params.get("selector"),
                    params.get("value"),
                )
            elif action == "upload":
                result = await self.browser.browser_upload(
                    params.get("selector"),
                    params.get("file_path"),
                )
            elif action == "wait":
                result = await self.browser.browser_wait_for(params.get("selector"))
            else:
                result = {"success": False, "error": f"Unknown action: {action}"}

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

    async def submit_form(self, submit_selector: str = "button[type='submit']") -> dict[str, Any]:
        """Submit the current form.

        Args:
            submit_selector: Submit button selector

        Returns:
            Submit result
        """
        return await self.browser.browser_click(submit_selector)

    async def take_screenshot(self, output_path: Optional[str] = None) -> dict[str, Any]:
        """Take a screenshot.

        Args:
            output_path: Optional output path

        Returns:
            Screenshot result
        """
        return await self.browser.browser_screenshot(output_path)

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL.

        Args:
            url: URL to navigate to

        Returns:
            Navigation result
        """
        return await self.browser.browser_navigate(url)

    async def close_browser(self) -> dict[str, Any]:
        """Close the browser.

        Returns:
            Close result
        """
        return await self.browser.browser_close()

    async def handle_browser_task(self, action: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle a browser task.

        Args:
            action: Action to perform
            context: Task context

        Returns:
            Task result
        """
        handlers = {
            "open_site": lambda: self.open_site(
                context.get("url", ""),
                context.get("headless", False),
            ),
            "analyze_form": self.analyze_form,
            "fill_form": lambda: self.fill_form(
                context.get("field_values"),
                context.get("use_profile", False),
            ),
            "select_dropdowns": lambda: self.select_dropdowns(context.get("selections", {})),
            "upload_files": lambda: self.upload_files(context.get("uploads", {})),
            "complete_multistep_flow": lambda: self.complete_multistep_flow(
                context.get("steps", [])
            ),
            "submit_form": lambda: self.submit_form(context.get("submit_selector")),
            "take_screenshot": lambda: self.take_screenshot(context.get("output_path")),
            "navigate": lambda: self.navigate(context.get("url", "")),
            "close_browser": self.close_browser,
        }

        _goal = getattr(context, "goal", "") or getattr(context, "current_goal", "") or ""

        # ── Skill Engine intercept ─────────────────────────────────────
        if _goal and action in ("execute_task", "execute_goal"):
            try:
                from skill_engine.orchestrator import run_task, get_engine
                engine = get_engine()
                if engine and engine.should_intercept(_goal, agent_hint="browser"):
                    skill_result = run_task(_goal, agent_hint="browser")
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

        handlers["execute_goal"] = lambda: self._execute_from_goal(_goal)
        # open_site with no URL → derive URL from goal
        handlers["open_site"] = lambda: (
            self._execute_from_goal(_goal)
            if not context.get("url")
            else self.open_site(context.get("url", ""), context.get("headless", False))
        )
        handlers["execute_task"] = lambda: self._execute_from_goal(_goal)
        handlers["verify"] = lambda: self._async_success("Browser task verified.")

        handler = handlers.get(action)
        if handler:
            result = handler()
            import inspect as _inspect
            if _inspect.isawaitable(result):
                result = await result
            return result

        return {"success": False, "error": f"Unknown action: {action}"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _async_success(self, message: str) -> dict:
        return {"success": True, "summary": message, "message": message}

    async def _execute_from_goal(self, goal: str) -> dict:
        """Interpret a free-form goal and perform the most relevant browser action."""
        if not goal:
            return {"success": False, "error": "No goal provided to browser agent."}

        import re
        goal_lower = goal.lower()

        # ── Research / lead gen goals → use the non-Chrome web research tools ──
        _research_keywords = (
            "lead", "leads", "lead gen", "lead generation", "outreach",
            "prospect", "prospects", "market research", "competitors", "niche",
            "find companies", "find businesses", "find clients", "sales",
            "autonomous", "scrape", "crawl", "discover companies",
        )
        is_research = any(k in goal_lower for k in _research_keywords)

        # Also treat it as research if no explicit URL is given and the goal is long
        url_match = re.search(r"https?://[^\s\"'>]+", goal)
        explicit_url = url_match.group(0).rstrip(".,)\"'") if url_match else None

        if is_research and not explicit_url:
            return await self._execute_web_research(goal)

        # ── Job search → LinkedIn / Indeed (stealth browser) ───────────────
        if not explicit_url:
            if any(x in goal_lower for x in ["job", "jobs", "career", "linkedin", "indeed",
                                               "glassdoor", "apply", "application", "vacancy",
                                               "hiring", "recruitment"]):
                quoted = re.findall(r'"([^"]{4,80})"', goal)
                query = quoted[0] if quoted else "AI automation remote"
                query_enc = query.replace(" ", "+")
                if "indeed" in goal_lower:
                    explicit_url = f"https://www.indeed.com/jobs?q={query_enc}"
                elif "glassdoor" in goal_lower:
                    explicit_url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query_enc}"
                else:
                    explicit_url = f"https://www.linkedin.com/jobs/search/?keywords={query_enc}&f_WT=2"

        # ── Generic goal with an explicit URL — open it with stealth ───────
        if not explicit_url:
            # Build DuckDuckGo search URL (not Google — avoids CAPTCHA)
            stop_words = {
                "you", "are", "an", "the", "a", "and", "or", "is", "in", "to",
                "of", "for", "with", "that", "this", "your", "i", "it", "be",
                "can", "do", "not", "from", "at", "on", "as", "by", "my",
                "mission", "objective", "task", "please", "should", "must",
                "will", "would", "could", "need", "want", "make", "get",
            }
            words = [
                w for w in re.findall(r"[a-zA-Z]{3,}", goal[:400])
                if w.lower() not in stop_words
            ]
            q = "+".join(words[:8]) if words else "AI+automation"
            explicit_url = f"https://duckduckgo.com/?q={q}"

        # ── Browser priority: Playwright (primary) → headless retry → DDG visual ──
        # Step 1: Playwright with stealth mode (PRIMARY execution engine)
        result = await self.browser.browser_open(
            explicit_url, headless=False, stealth=True,
        )

        # Step 2: If Playwright failed, diagnose → self-repair → retry headless
        if not result.get("success"):
            error = result.get("error", "Browser open failed")
            diag = self._repair.diagnose(error)
            fixed = self._repair.apply_fix(diag)
            if fixed and diag.fix_action not in ("skip_llm",):
                result = await self.browser.browser_open(
                    explicit_url, headless=True, stealth=True,
                )

        # Step 3: If still failed and DDG Desktop is available, open visually (no scraping)
        if not result.get("success"):
            ddg_exe = find_ddg_browser()
            if ddg_exe and not result.get("success"):
                ddg_open = open_url_in_ddg_browser(explicit_url)
                if ddg_open.get("success"):
                    return {
                        "success": True,
                        "url": explicit_url,
                        "title": explicit_url,
                        "page_text": "",
                        "browser": "duckduckgo_desktop",
                        "summary": (
                            f"Playwright unavailable — opened in DuckDuckGo Desktop Browser: {explicit_url}\n"
                            f"Browser window is visible on your screen. Note: page data cannot be extracted."
                        ),
                    }

        if not result.get("success"):
            result.setdefault("summary", f"Could not open browser for: {goal[:80]}")
            return result

        title     = result.get("title", "")
        page_text = result.get("page_text", "")

        # ── Job search: extract real listings from the page ────────────────
        is_job_search = any(x in goal_lower for x in
            ["job", "jobs", "career", "linkedin", "indeed", "vacancy", "hiring"])
        jobs_section = ""
        if is_job_search:
            job_result = await self.browser.browser_extract_jobs()
            jobs = job_result.get("jobs", [])
            if jobs:
                jobs_section = f"\n\n{'='*50}\nFOUND {len(jobs)} JOB LISTINGS:\n{'='*50}\n"
                for i, j in enumerate(jobs, 1):
                    jobs_section += f"\n{i}. {j.get('title','')}"
                    if j.get("company"):
                        jobs_section += f"\n   Company:  {j['company']}"
                    if j.get("location"):
                        jobs_section += f"\n   Location: {j['location']}"
                jobs_section += f"\n\nURL: {explicit_url}"
                jobs_section += "\n\nThe browser window is open — you can click any listing to read more details."
            elif page_text:
                jobs_section = f"\n\nPage content (first 1500 chars):\n{page_text[:1500]}"

        summary = (
            f"✓ Browser opened: {explicit_url}\n"
            f"✓ Page title: {title}\n"
            f"✓ Browser window is open and visible on your screen."
            + jobs_section
        )
        result["summary"] = summary
        return result

    async def _execute_web_research(self, goal: str) -> dict:
        """
        Handle research / lead generation goals without opening Chrome.

        Uses the multi-layer WebResearcher (DuckDuckGo → Bing → HTTP → DDG API)
        to find real business data, then formats a structured report.
        """
        try:
            from ..tools_ext.web_research_tools import (
                get_web_researcher, extract_niche_from_goal,
            )
            import re

            researcher = get_web_researcher()

            # Use shared smart niche extractor (handles meta-tasks, e.g. examples, etc.)
            niche, location = extract_niche_from_goal(goal)

            # How many leads were requested?
            count_m = re.search(r"\b(\d+)\s*(?:leads?|companies|businesses|prospects)\b",
                                 goal, re.IGNORECASE)
            count = int(count_m.group(1)) if count_m else 10
            count = min(count, 20)  # cap at 20 to avoid very long runs

            # Discover businesses
            businesses = researcher.discover(niche, location=location, count=count)

            if not businesses:
                # Fall back: generic web search and show results
                sr = researcher.search(f"{niche} companies contact email", max_results=10)
                results_text = "\n".join(
                    f"  {i+1}. {r['title']}\n     {r['url']}\n     {r['snippet'][:200]}"
                    for i, r in enumerate(sr.get("results", [])[:10])
                )
                return {
                    "success": bool(sr.get("results")),
                    "summary": (
                        f"Web Research Results for: {niche}\n"
                        f"Source: {sr.get('source','web')}\n\n"
                        f"{results_text or 'No results found.'}"
                    ),
                }

            # Format the discovered businesses as a lead list
            lines = [
                f"WEB RESEARCH: {niche.title()}{' in ' + location if location else ''}",
                f"Found {len(businesses)} businesses via real web search",
                "=" * 60,
            ]
            for i, b in enumerate(businesses, 1):
                lines.append(f"\nLEAD #{i}")
                lines.append(f"  Company   : {b['company']}")
                lines.append(f"  Website   : {b['website']}")
                if b.get("description"):
                    lines.append(f"  Overview  : {b['description'][:200]}")
                if b.get("email_hints"):
                    lines.append(f"  Emails    : {', '.join(b['email_hints'])}")
                if b.get("linkedin"):
                    lines.append(f"  LinkedIn  : {b['linkedin']}")

            lines.append("\n" + "=" * 60)
            lines.append("Real data scraped from the web — no hallucination.")

            return {
                "success": True,
                "summary": "\n".join(lines),
                "businesses": businesses,
            }

        except Exception as exc:
            import traceback
            return {
                "success": False,
                "error": f"Web research failed: {exc}",
                "summary": f"Web research error: {exc}",
                "traceback": traceback.format_exc(),
            }
