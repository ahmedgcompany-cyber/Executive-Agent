"""Job agent for job application tasks."""

import logging
from pathlib import Path
from typing import Any, Optional

from ..memory.profile_store import ProfileStore
from ..tools_ext.browser_tools import BrowserTools
from ..tools_ext.form_tools import FormTools

_log = logging.getLogger("megav.job")


class JobAgent:
    """Specialist agent for job applications."""

    def __init__(
        self,
        profile_store: ProfileStore,
        browser_tools: Optional[BrowserTools] = None,
    ):
        """Initialize job agent.

        Args:
            profile_store: ProfileStore instance
            browser_tools: Optional BrowserTools instance
        """
        self.profile = profile_store
        self.browser = browser_tools or BrowserTools()
        self.form = FormTools(self.browser)

        # Load prompt
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load job prompt from file."""
        prompt_path = Path("src/prompts/jobs.txt")
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a job application specialist agent."

    def match_job(self, job_description: str) -> dict[str, Any]:
        """Match job requirements to user profile.

        Args:
            job_description: Job description text

        Returns:
            Match analysis
        """
        job_lower = job_description.lower()

        # Get user skills and experience
        user_skills = self.profile.get_profile_value("skills", [])
        job_titles = self.profile.get_profile_value("job_titles", [])
        years_exp = self.profile.get_job_answer("years_of_experience", "")

        # Simple keyword matching
        matched_skills = []
        for skill in user_skills:
            if skill.lower() in job_lower:
                matched_skills.append(skill)

        # Calculate match score
        skill_match = len(matched_skills) / max(len(user_skills), 1) * 100

        return {
            "success": True,
            "matched_skills": matched_skills,
            "skill_match_percent": round(skill_match, 1),
            "user_job_titles": job_titles,
            "years_experience": years_exp,
            "recommendation": "apply" if skill_match > 50 else "review",
        }

    def prepare_application_payload(self, job_title: str) -> dict[str, Any]:
        """Prepare application materials.

        Args:
            job_title: Job title

        Returns:
            Application payload
        """
        # Get default resume
        resume_path = self.profile.get_default_resume()

        # Get relevant answers
        answers = {
            "work_authorization": self.profile.get_job_answer("work_authorization"),
            "notice_period": self.profile.get_job_answer("notice_period"),
            "salary_expectation": self.profile.get_job_answer("salary_expectation"),
            "years_of_experience": self.profile.get_job_answer("years_of_experience"),
            "why_this_role": self.profile.get_job_answer("why_this_role"),
            "about_you": self.profile.get_job_answer("about_you"),
        }

        # Get contact info
        contact = {
            "name": self.profile.get_profile_value("name", ""),
            "email": self.profile.get_primary_email(),
            "phone": self.profile.get_primary_phone(),
            "linkedin": self.profile.get_profile_value("linkedin", ""),
        }

        return {
            "success": True,
            "resume_path": resume_path,
            "answers": answers,
            "contact": contact,
            "job_title": job_title,
        }

    async def fill_application(
        self,
        job_url: str,
        custom_answers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Fill a job application form.

        Args:
            job_url: Job application URL
            custom_answers: Optional custom answers

        Returns:
            Fill result
        """
        # Open the job page
        open_result = await self.browser.browser_open(job_url)
        if not open_result.get("success"):
            return open_result

        # Analyze form
        form_analysis = await self.form.analyze_form_fields()
        if not form_analysis.get("success"):
            return form_analysis

        # Prepare answers
        profile = self.profile.user_profile
        job_answers = self.profile.job_answers

        if custom_answers:
            job_answers.update(custom_answers)

        # Fill form
        fill_result = await self.form.fill_form_from_profile(profile, job_answers)

        return {
            "success": fill_result.get("success"),
            "filled_fields": fill_result.get("filled_count", 0),
            "results": fill_result.get("results", []),
        }

    def select_resume_variant(self, job_type: str) -> dict[str, Any]:
        """Select the best resume variant for a job type.

        Args:
            job_type: Type of job

        Returns:
            Selected resume
        """
        default_resume = self.profile.get_default_resume()

        try:
            from ..providers.model_router import ModelRouter, NoModelAvailableError
            router = ModelRouter()
            resp = router.ask(
                system="You are a career advisor. Given a job type, recommend which resume variant or emphasis to use.",
                user=f"Job type: {job_type}. Available resume: {default_resume}. Which resume variant or emphasis is best?",
                task_type="general",
            )
            if resp:
                return {
                    "success": True,
                    "selected_resume": default_resume,
                    "job_type": job_type,
                    "recommendation": resp,
                }
        except NoModelAvailableError:
            return {
                "success": False,
                "error": "No LLM available for resume selection.",
                "selected_resume": default_resume,
                "job_type": job_type,
                "note": "Using default resume — LLM selection unavailable.",
            }
        except Exception:
            import logging
            logging.getLogger(__name__).exception("select_resume_variant error")

        return {
            "success": False,
            "error": "Resume selection failed.",
            "selected_resume": default_resume,
            "job_type": job_type,
        }

    def generate_cover_letter(
        self,
        company: str,
        position: str,
        job_description: str,
    ) -> dict[str, Any]:
        """Generate a cover letter.

        Args:
            company: Company name
            position: Position title
            job_description: Job description

        Returns:
            Generated cover letter
        """
        name = self.profile.get_profile_value("name", "")
        skills = self.profile.get_profile_value("skills", [])
        about = self.profile.get_job_answer("about_you", "")
        why = self.profile.get_job_answer("why_this_role", "")

        try:
            from ..providers.model_router import ModelRouter, NoModelAvailableError
            router = ModelRouter()
            resp = router.ask(
                system="You are an expert cover letter writer. Write a compelling, personalised cover letter.",
                user=(
                    f"Write a cover letter for:\n"
                    f"Company: {company}\nPosition: {position}\n"
                    f"Job description: {job_description}\n"
                    f"Applicant name: {name}\nSkills: {skills}\n"
                    f"About: {about}\nWhy this role: {why}"
                ),
                task_type="general",
            )
            if resp:
                return {
                    "success": True,
                    "cover_letter": resp,
                    "company": company,
                    "position": position,
                }
        except NoModelAvailableError:
            return {"success": False, "error": "No LLM available to generate cover letter.", "company": company, "position": position}
        except Exception:
            import logging
            logging.getLogger(__name__).exception("generate_cover_letter error")

        return {"success": False, "error": "Cover letter generation failed.", "company": company, "position": position}

    # ── Email + CRM patterns the job agent handles ──────────────────
    _EMAIL_RE = None
    _EMAIL_PATTERNS = [
        r"\b(check|read|get|show|fetch)\b.{0,20}\b(email|inbox|mail)\b",
        r"\b(reply|respond)\b.{0,25}\b(recruiter|hiring|job|email)\b",
        r"\b(email|inbox).{0,25}\b(important|urgent|recruiter)\b",
        r"\bfollow.?up\b",
    ]

    @classmethod
    def _is_email_goal(cls, goal: str) -> bool:
        import re
        if cls._EMAIL_RE is None:
            cls._EMAIL_RE = re.compile("|".join(cls._EMAIL_PATTERNS), re.IGNORECASE)
        return bool(cls._EMAIL_RE.search(goal))

    def _try_email_action(self, goal: str, context: Any) -> Optional[dict[str, Any]]:
        """Route email/CRM goals to the appropriate services."""
        if not self._is_email_goal(goal):
            return None
        try:
            from ..integrations.email_service import get_email_service
            from ..integrations.crm_service import get_crm_service
            email_svc = get_email_service()
            profile = {}
            try:
                profile = dict(getattr(context, "profile", {}) or {})
            except Exception:
                pass
            default_account = profile.get("email", "")

            # Follow-up / CRM path
            import re
            if re.search(r"\bfollow.?up\b", goal, re.IGNORECASE):
                crm = get_crm_service()
                summary = crm.get_pipeline_summary()
                fus = summary.get("follow_ups", [])
                lines = [f"CRM: {summary['total_contacts']} contacts, {summary['follow_ups_due']} follow-ups due."]
                for c in fus[:5]:
                    lines.append(f"  • {c.get('name') or c['email']} — {c.get('stage')} — {c.get('next_action','')}")
                return {"success": True, "summary": "\n".join(lines), "via_email": True}

            # Email path
            if not email_svc.is_connected():
                return None  # fall through
            result = email_svc.handle_prompt(goal, default_account=default_account)
            if result.get("success"):
                return {"success": True, "summary": result.get("summary") or result.get("message", "Done."), "via_email": True}
        except Exception:
            pass
        return None

    def handle_job_task(self, action: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle a job task.

        Args:
            action: Action to perform
            context: Task context

        Returns:
            Task result
        """
        goal_text = getattr(context, "goal", "") or getattr(context, "current_goal", "") or ""

        # ── Email/CRM intercept ────────────────────────────────────────
        if action in ("execute_goal", "fill_application") and goal_text:
            email_result = self._try_email_action(goal_text, context)
            if email_result:
                return email_result
        # ── End intercept ─────────────────────────────────────────────

        handlers = {
            "match_job": lambda: self.match_job(context.get("job_description", "")),
            "prepare_payload": lambda: self.prepare_application_payload(
                context.get("job_title", "")
            ),
            "select_resume": lambda: self.select_resume_variant(context.get("job_type", "")),
            "generate_cover_letter": lambda: self.generate_cover_letter(
                context.get("company", ""),
                context.get("position", ""),
                context.get("job_description", ""),
            ),
        }

        handlers["execute_goal"]     = lambda: self._execute_from_goal_sync(goal_text)
        # fill_application → actually opens the browser and searches
        handlers["fill_application"] = lambda: self._execute_from_goal_sync(goal_text)
        # submit → confirm we attempted the search
        handlers["submit"]           = lambda: {
            "success": True,
            "summary": (
                "Browser search initiated. Check the browser window that opened.\n"
                "Review the job listings, then tell me which ones to apply to."
            )
        }
        handlers["verify"]           = lambda: {"success": True, "summary": "Job task verified."}

        handler = handlers.get(action)
        if handler:
            result = handler()
            # execute_goal may return a coroutine — surface it so AgentLoop can await it
            import inspect as _i
            if _i.isawaitable(result):
                return result          # returned to AgentLoop which will await it
            return result

        return {"success": False, "error": f"Unknown action: {action}"}

    # ------------------------------------------------------------------
    # Goal-driven execution
    # ------------------------------------------------------------------

    def _execute_from_goal_sync(self, goal: str):
        """Return a coroutine if browser is needed, otherwise a plain dict."""
        import re
        goal_lower = goal.lower()

        # Detect target site
        if "linkedin" in goal_lower:
            search_url = "https://www.linkedin.com/jobs/search/?keywords="
            site = "LinkedIn"
        elif "indeed" in goal_lower:
            search_url = "https://www.indeed.com/jobs?q="
            site = "Indeed"
        elif "glassdoor" in goal_lower:
            search_url = "https://www.glassdoor.com/Search/results.htm?keyword="
            site = "Glassdoor"
        else:
            search_url = "https://www.linkedin.com/jobs/search/?keywords="
            site = "LinkedIn"

        # Extract count
        count_match = re.search(r"\b(\d+)\b", goal)
        count = int(count_match.group(1)) if count_match else 3

        # Extract keywords from profile + goal
        profile_title = self.profile.get_profile_value("job_titles", ["developer"])
        if isinstance(profile_title, list):
            profile_title = profile_title[0] if profile_title else "developer"

        # Extract role from goal text
        role_match = re.search(
            r"(?:for|as|position|role|jobs?|vacancies)\s+(?:a\s+)?([a-z ]+?)(?:\s+on|\s+at|\s+in|\s+and|$)",
            goal_lower
        )
        role = role_match.group(1).strip() if role_match else profile_title
        query = role.replace(" ", "%20")
        full_url = f"{search_url}{query}"

        # Use LLM to generate a detailed plan
        try:
            from ..providers.model_router import ModelRouter, NoModelAvailableError
            router = ModelRouter()
            profile_summary = f"Name: {self.profile.get_profile_value('name', 'User')}, Skills: {self.profile.get_profile_value('skills', [])}"
            plan_text = router.ask(
                system="You are a job hunting assistant. Be concise and practical.",
                user=(
                    f"Goal: {goal}\n"
                    f"Profile: {profile_summary}\n"
                    f"Target site: {site}, search URL: {full_url}\n"
                    f"Target count: {count} jobs\n\n"
                    "Write a step-by-step plan (5 steps max) describing exactly what you will do "
                    "to find and apply to these jobs. Be specific about the site and role."
                ),
                task_type="general",
            )
        except NoModelAvailableError:
            _log.warning("Job plan generation skipped — no model available")
            plan_text = ""
        except Exception as _e:
            _log.error("Job plan generation failed: %s", _e)
            plan_text = ""

        # Return async execution (opens the browser)
        return self._execute_job_search_async(full_url, site, role, count, plan_text)

    async def _execute_job_search_async(
        self, url: str, site: str, role: str, count: int, plan: str
    ) -> dict[str, Any]:
        """Actually open the browser and search for jobs."""
        steps_done = []

        # Step 1 — open browser
        open_result = await self.browser.browser_open(url, headless=False)
        if open_result.get("success"):
            steps_done.append(f"Opened {site} jobs search for '{role}'")
        else:
            # Browser not available — return a detailed plan instead
            summary = (
                f"Browser unavailable ({open_result.get('error', 'Playwright not installed')}).\n\n"
                f"Here is the plan to find {count} '{role}' jobs on {site}:\n\n"
            )
            if plan:
                summary += plan
            else:
                summary += (
                    f"1. Open {url}\n"
                    f"2. Search for '{role}' positions\n"
                    f"3. Filter by relevance and date posted\n"
                    f"4. Open each job and check requirements against your profile\n"
                    f"5. Apply to the best {count} matches using your saved profile data\n"
                )
            return {"success": True, "summary": summary}

        # Step 2 — take screenshot
        screenshot = await self.browser.browser_screenshot()
        if screenshot.get("success"):
            steps_done.append(f"Screenshot saved: {screenshot.get('path', 'screenshot.png')}")

        # Step 3 — extract job listings from the page
        extract = await self.browser.browser_extract_jobs()
        jobs_found = []
        if extract.get("success"):
            for job in extract.get("jobs", []):
                title = job.get("title", "").strip()
                company = job.get("company", "").strip()
                loc = job.get("location", "").strip()
                parts = [title]
                if company:
                    parts.append(f"@ {company}")
                if loc:
                    parts.append(f"({loc})")
                jobs_found.append(" ".join(parts))
        jobs_found = jobs_found[:count] if jobs_found else []

        summary_lines = [f"Opened {site} and searched for '{role}' jobs."]
        if jobs_found:
            summary_lines.append(f"\nFound {len(jobs_found)} job listings:")
            summary_lines.extend(f"  {i+1}. {j}" for i, j in enumerate(jobs_found))
        else:
            summary_lines.append("\nNo job listings extracted yet — the page may still be loading or requires login.")
        summary_lines.append(f"\nURL: {url}")
        if plan:
            summary_lines.append(f"\nExecution plan:\n{plan}")
        summary_lines.append(
            f"\nNext steps: Review the browser window, select the best {count} matches, "
            "and use 'fill application' to apply."
        )

        return {
            "success": True,
            "summary": "\n".join(summary_lines),
            "site": site,
            "role": role,
            "url": url,
            "jobs_found": jobs_found,
        }
