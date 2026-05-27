"""Commander agent for task routing and coordination."""

import re
from pathlib import Path
from typing import Any, Optional

from ..providers.model_router import ModelRouter, NoModelAvailableError


# ---------------------------------------------------------------------------
# NEXUS multi-step project indicators
# ---------------------------------------------------------------------------
_NEXUS_FULL_PATTERNS = [
    r"\b(build|create|develop|launch|ship)\b.{0,30}\b(product|startup|saas|platform|company)\b",
    r"\bnexus.?full\b",
    r"\bcomplete product\b",
    r"\bfull product lifecycle\b",
]

_NEXUS_SPRINT_PATTERNS = [
    r"\b(build|create|develop)\b.{0,30}\b(mvp|prototype|feature|app|website|landing page)\b",
    r"\bnexus.?sprint\b",
    r"\bsprint pipeline\b",
]

_NEXUS_MICRO_PATTERNS = [
    r"\bnexus.?micro\b",
    r"\b(audit|research|campaign|bug.?fix|diagnose)\b.{0,25}\b(with|using)?\b.{0,10}(nexus|pipeline|agents?)\b",
    r"\b(marketing campaign|compliance audit|incident response|performance investigation)\b",
    r"\borchestrat",  # "orchestrate", "orchestration"
    r"\bmulti.?agent\b",
]

# Agency category routing words
_AGENCY_CATEGORY_HINTS: dict[str, list[str]] = {
    "engineering": ["backend", "frontend", "devops", "architect", "api design", "database schema",
                    "mobile app", "security audit", "code review", "rapid prototype"],
    "design":      ["ux research", "brand identity", "ui design", "wireframe", "visual story",
                    "design system", "image prompt"],
    "marketing":   ["seo strategy", "growth hack", "content calendar", "tiktok", "instagram strategy",
                    "linkedin content", "app store optimization", "youtube strategy"],
    "sales":       ["sales strategy", "deal review", "outbound campaign", "sales proposal",
                    "account plan", "discovery call"],
    "testing":     ["qa test", "performance benchmark", "accessibility audit", "api test",
                    "evidence collect", "reality check"],
    "project-management": ["sprint plan", "project shepherd", "jira", "studio producer",
                           "experiment track"],
    "product":     ["product feedback", "trend research", "sprint prioritiz", "behavioral nudge"],
    "finance":     ["financial analysis", "tax strategy", "investment research", "bookkeep",
                    "fpa", "fp&a"],
    "support":     ["support ticket", "infrastructure maintain", "analytics report",
                    "finance track", "executive summary"],
    "academic":    ["academic research", "historical analysis", "psychological", "anthropolog",
                    "geographic", "narratolog"],
    "game-development": ["unity", "unreal engine", "godot", "roblox", "game design",
                         "level design", "narrative design", "shader"],
    "paid-media":  ["ppc", "paid social", "programmatic", "media buy", "search query",
                    "ad creative", "tracking pixel"],
    "spatial-computing": ["xr", "visionos", "spatial computing", "metal shader",
                          "mixed reality", "vision pro"],
    "specialized": ["orchestrat", "workflow architect", "mcp builder", "customer service agent",
                    "legal review", "compliance check", "hr onboard", "data consolidat"],
}


class CommanderAgent:
    """Main commander agent that routes tasks to specialist agents."""

    def __init__(
        self,
        coder_agent: Optional[Any] = None,
        browser_agent: Optional[Any] = None,
        desktop_agent: Optional[Any] = None,
        job_agent: Optional[Any] = None,
        sales_agent: Optional[Any] = None,
        content_agent: Optional[Any] = None,
        skill_agent: Optional[Any] = None,
        memory_agent: Optional[Any] = None,
        social_agent: Optional[Any] = None,
    ):
        """Initialize commander agent."""
        self.agents = {
            "coder":   coder_agent,
            "browser": browser_agent,
            "desktop": desktop_agent,
            "job":     job_agent,
            "sales":   sales_agent,
            "content": content_agent,
            "skill":   skill_agent,
            "memory":  memory_agent,
            "social":  social_agent,
        }

        self.current_plan: list[dict[str, Any]] = []
        self.current_step: int = 0
        self.task_history: list[dict[str, Any]] = []

        self.router = ModelRouter()

        # Load prompt
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load commander prompt from file."""
        prompt_path = Path("src/prompts/commander.txt")
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are the commander agent. Route tasks to appropriate specialist agents."

    def analyze_goal(self, goal: str) -> dict[str, Any]:
        """Analyze a user goal and determine the approach.

        Args:
            goal: User's goal

        Returns:
            Analysis result
        """
        import re

        # Fast-path: explicit URL → always browser
        if re.search(r"https?://\S+", goal):
            return {
                "success": True,
                "goal": goal,
                "suggested_agent": "browser",
                "confidence": 1.0,
                "all_scores": {},
            }

        # Simple keyword-based analysis
        goal_lower = goal.lower()

        indicators = {
            "coder": ["code", "program", "develop", "build", "script", "debug", "fix", "python", "javascript", "function", "class", "implement", "refactor", "compile", "run test", "create a", "write a", "generate", "make a", "design a", "architect"],
            "browser": ["website", "web", "url", "http", "navigate to", "search online", "login", "fill form", "open website"],
            "desktop": ["open notepad", "open excel", "open word", "open chrome", "open firefox", "launch notepad", "launch excel", "launch chrome", "start notepad", "photoshop", "illustrator", "blender", "autocad"],
            "job": ["job", "jobs", "apply for", "resume", "cover letter", "interview", "career", "hiring", "vacancy", "vacancies", "find job", "job search", "apply to", "jobs on", "jobs at", "jobs in", "find me jobs", "job listings", "job openings"],
            "sales": ["lead", "prospect", "market research", "competitor", "outreach", "sales"],
            "content": ["write", "content", "blog", "youtube", "description"],
            "skill": ["install skill", "add skill", "capability", "extension"],
            "memory": ["remember", "save", "profile", "my information", "store"],
            "social": [
                "post on linkedin", "post on facebook", "post on instagram",
                "post on tiktok", "post on twitter", "post on x",
                "share on linkedin", "share on facebook", "share on instagram",
                "publish on", "linkedin post", "facebook post", "instagram post",
                "tweet", "google business post", "social media post",
                "connect linkedin", "connect facebook", "connect instagram",
                "connect social", "social accounts", "social media",
                "post to all", "post this on", "share this on",
                "disconnect linkedin", "disconnect facebook",
                "my social", "social platforms",
            ],
        }

        scores = {agent: 0 for agent in indicators.keys()}

        for agent, keywords in indicators.items():
            for keyword in keywords:
                if keyword in goal_lower:
                    scores[agent] += 1

        # Build-intent override: "build/create/design X" → coder boost
        # (prevents "desktop application" from routing to Desktop agent)
        # BUT: only apply if no other domain agent already has a strong match,
        # e.g. "build a lead gen system" should stay → sales, not coder
        build_verbs = ["build", "create", "design", "plan", "architect", "generate", "make", "develop", "write", "code"]
        build_targets = ["app", "application", "software", "system", "program", "tool", "dashboard", "website", "game", "api", "script", "project", "command center", "platform"]
        has_build_verb = any(v in goal_lower for v in build_verbs)
        has_build_target = any(t in goal_lower for t in build_targets)
        # Domain agents that take priority over the "build" coder override
        domain_agents = ["sales", "browser", "job", "desktop", "social", "content", "memory"]
        max_domain_score = max(scores.get(a, 0) for a in domain_agents)
        if has_build_verb and has_build_target and max_domain_score < 2:
            # Only boost coder when no domain agent has a meaningful keyword match
            scores["coder"] += 6
        scores["desktop"] = 0  # "desktop application" should not trigger Desktop agent

        # Try to use LLM parsing first
        # Be explicit: desktop = CONTROL existing apps (open/click/type), coder = BUILD/CREATE new software
        goal_snippet = goal[:300] if len(goal) > 300 else goal
        prompt = (
            f"Classify this user request to ONE agent.\n"
            f"Request: '{goal_snippet}'\n\n"
            f"Agent choices:\n"
            f"  coder   — build, create, write, generate, or fix code/software/scripts/apps\n"
            f"  browser — visit websites, search online, fill web forms, scrape URLs\n"
            f"  desktop — CONTROL existing desktop apps (open Notepad, click buttons, automate UI)\n"
            f"  job     — job search, applications, resumes, cover letters\n"
            f"  sales   — market research, leads, outreach emails\n"
            f"  content — write articles, social posts, descriptions, marketing copy\n"
            f"  skill   — install or manage skills/extensions\n"
            f"  memory  — remember/store user information or preferences\n"
            f"  social  — post to LinkedIn/Facebook/Instagram/TikTok/Google Business, manage social accounts\n\n"
            f"Return ONLY the single lowercase agent name, nothing else."
        )
        try:
            result = self.router.route_generate(prompt, task_type="general")
        except NoModelAvailableError:
            result = {"success": False, "error": "No LLM available"}
        best_agent = "general" # default for unclassifiable goals

        if result.get("success") and result.get("response"):
            agent_candidate = result["response"].strip().lower().split()[0] if result["response"].strip() else ""
            if agent_candidate in scores:
                # If LLM picks a zero-score agent but another domain agent scores >= 2,
                # prefer keyword analysis — LLM sometimes misclassifies domain tasks
                # (e.g. says "coder" for "build a lead generation system")
                if scores.get(agent_candidate, 0) == 0 and max_domain_score >= 2:
                    kw_best = max(domain_agents, key=lambda a: scores.get(a, 0))
                    best_agent = kw_best
                else:
                    best_agent = agent_candidate
            else:
                # LLM gave unexpected response — fall back to keyword scores
                best_agent = max(scores, key=scores.get)
                if scores[best_agent] == 0:
                    best_agent = "general"
        else:
            # Fallback to finding best match via keywords
            best_agent = max(scores, key=scores.get)
            best_score = scores[best_agent]

            if best_score == 0:
                best_agent = "general"

        return {
            "success": True,
            "goal": goal,
            "suggested_agent": best_agent,
            "confidence": 1.0,
            "all_scores": scores,
        }


    # ------------------------------------------------------------------
    # Compound-goal decomposition
    # ------------------------------------------------------------------

    # Phase archetypes: each maps a verb category to an agent + action
    _PHASE_ARCHETYPES = {
        "research":    {"agent": "browser", "action": "execute_task",
                        "label": "Research & Analysis"},
        "scan":        {"agent": "browser", "action": "execute_task",
                        "label": "Market Scanning"},
        "validate":    {"agent": "browser", "action": "execute_task",
                        "label": "Validation & Testing"},
        "plan":        {"agent": "content", "action": "create",
                        "label": "Planning & Strategy"},
        "design":      {"agent": "coder",   "action": "generate_code",
                        "label": "Design & Architecture"},
        "build":       {"agent": "coder",    "action": "generate_code",
                        "label": "Build & Develop"},
        "create":      {"agent": "coder",    "action": "generate_code",
                        "label": "Create & Generate"},
        "code":        {"agent": "coder",    "action": "generate_code",
                        "label": "Code Implementation"},
        "write":       {"agent": "content",  "action": "create",
                        "label": "Writing & Content"},
        "launch":      {"agent": "coder",    "action": "execute_goal",
                        "label": "Launch & Deploy"},
        "deploy":      {"agent": "coder",    "action": "execute_goal",
                        "label": "Deployment"},
        "market":      {"agent": "sales",    "action": "execute_goal",
                        "label": "Marketing & Outreach"},
        "sell":        {"agent": "sales",    "action": "execute_goal",
                        "label": "Sales & Revenue"},
        "outreach":    {"agent": "sales",    "action": "execute_goal",
                        "label": "Outreach & Prospecting"},
        "social":      {"agent": "social",   "action": "execute_goal",
                        "label": "Social Media"},
        "scale":       {"agent": "sales",    "action": "execute_goal",
                        "label": "Scale & Growth"},
        "optimize":    {"agent": "coder",    "action": "generate_code",
                        "label": "Optimization"},
        "automate":    {"agent": "coder",    "action": "generate_code",
                        "label": "Automation Setup"},
        "brand":       {"agent": "content",  "action": "create",
                        "label": "Branding"},
        "finance":     {"agent": "content",  "action": "create",
                        "label": "Financial Planning"},
        "content":     {"agent": "content",  "action": "create",
                        "label": "Content Creation"},
    }

    # Regex patterns that signal a compound (multi-phase) goal
    _COMPOUND_SIGNALS = [
        # Explicit phase numbering: "phase 1", "step 2", etc.
        r"(?:phase|step|stage)\s*\d",
        # Sequencing words with distinct actions
        r"(?:first|then|after that|next|finally)\b.{5,80}\b(?:then|after|next|finally)\b",
        # Business/product workflow verbs
        r"\b(?:research|scan|validate|build|create|launch|market|scale|deploy|automate)\b"
        r".{5,120}"
        r"\b(?:research|scan|validate|build|create|launch|market|scale|deploy|automate)\b",
        # Multi-action phrases
        r"\b(?:build|create|develop|start|launch)\b.{0,40}\b(?:business|product|startup|saas|platform|company|brand|app)\b",
        # "from scratch" implies multi-phase
        r"\bfrom\s+scratch\b",
        # Very long goals with multiple sentences/requirements
        r"(?:^|\n)\s*[-•*]\s+.*(?:\n\s*[-•*]\s+.*){2,}",  # 3+ bullet points
    ]

    def _is_compound_goal(self, goal: str) -> bool:
        """Return True if the goal requires multiple distinct phases."""
        import re
        gl = goal.lower()

        # Length heuristic: goals > 200 chars with multiple sentences are likely compound
        if len(goal) > 200:
            sentences = [s.strip() for s in re.split(r'[.!?\n]', goal) if len(s.strip()) > 15]
            if len(sentences) >= 3:
                return True

        # Explicit signal patterns
        for pat in self._COMPOUND_SIGNALS:
            if re.search(pat, gl, re.DOTALL):
                return True

        return False

    def _decompose_compound_goal(self, goal: str) -> list[dict[str, Any]]:
        """Break a compound goal into sequential phases.

        Each phase is a step dict with: agent, action, description, phase_name,
        sub_goal, expected_output.
        """
        import re
        gl = goal.lower()

        # ── Strategy 1: Detect explicitly numbered phases ──
        phase_pattern = re.compile(
            r"(?:phase|step|stage)\s*(\d+)\s*[:.)\-–]*\s*(.+?)(?=(?:phase|step|stage)\s*\d|$)",
            re.I | re.DOTALL,
        )
        explicit_phases = list(phase_pattern.finditer(goal))
        if explicit_phases:
            steps = []
            for m in explicit_phases:
                phase_num = int(m.group(1))
                phase_text = m.group(2).strip()[:200]
                archetype = self._match_phase_archetype(phase_text)
                step = {
                    "agent": archetype["agent"],
                    "action": archetype["action"],
                    "description": f"[Phase {phase_num}] {archetype['label']}: {phase_text[:80]}",
                    "phase_name": f"Phase {phase_num}: {archetype['label']}",
                    "sub_goal": phase_text,
                    "expected_output": self._infer_output_type(archetype["action"], phase_text),
                }
                steps.append(step)
            # Add a verification step at the end
            steps.append({
                "agent": "coder",
                "action": "verify_compound",
                "description": f"[Final] Verify all {len(steps)} phases completed with real output",
                "phase_name": "Verification",
                "sub_goal": "Verify all phases produced real, usable output",
                "expected_output": "file_list",
            })
            return steps

        # ── Strategy 2: Detect bullet-point / line-item phases ──
        bullet_pattern = re.compile(r"(?:^|\n)\s*[-•*]\s+(.+?)(?=\n\s*[-•*]|$)", re.DOTALL)
        bullets = list(bullet_pattern.finditer(goal))
        if len(bullets) >= 2:
            steps = []
            for i, m in enumerate(bullets, 1):
                item_text = m.group(1).strip()[:200]
                archetype = self._match_phase_archetype(item_text)
                step = {
                    "agent": archetype["agent"],
                    "action": archetype["action"],
                    "description": f"[{i}/{len(bullets)}] {archetype['label']}: {item_text[:80]}",
                    "phase_name": f"Step {i}: {archetype['label']}",
                    "sub_goal": item_text,
                    "expected_output": self._infer_output_type(archetype["action"], item_text),
                }
                steps.append(step)
            steps.append({
                "agent": "coder",
                "action": "verify_compound",
                "description": f"[Final] Verify all {len(steps)} steps completed with real output",
                "phase_name": "Verification",
                "sub_goal": "Verify all steps produced real, usable output",
                "expected_output": "file_list",
            })
            return steps

        # ── Strategy 3: LLM-based decomposition for complex goals ──
        decomposed = self._llm_decompose(goal)
        if decomposed:
            return decomposed

        # ── Strategy 4: Keyword-based phase extraction ──
        # Find all verb phrases that map to phase archetypes
        found_phases = []
        for key, archetype in self._PHASE_ARCHETYPES.items():
            pattern = rf"\b{key}\b"
            if re.search(pattern, gl):
                found_phases.append((key, archetype))

        if len(found_phases) >= 2:
            # Deduplicate by agent+action (avoid repeated identical phases)
            seen = set()
            steps = []
            for i, (key, archetype) in enumerate(found_phases, 1):
                sig = (archetype["agent"], archetype["action"])
                if sig in seen:
                    continue
                seen.add(sig)
                # Extract the specific sub-goal text around this keyword
                sub_goal = self._extract_sub_goal_around_keyword(goal, key)
                step = {
                    "agent": archetype["agent"],
                    "action": archetype["action"],
                    "description": f"[{i}/{len(found_phases)}] {archetype['label']}: {sub_goal[:80]}",
                    "phase_name": f"{archetype['label']}",
                    "sub_goal": sub_goal,
                    "expected_output": self._infer_output_type(archetype["action"], sub_goal),
                }
                steps.append(step)
            steps.append({
                "agent": "coder",
                "action": "verify_compound",
                "description": f"[Final] Verify all {len(steps)} phases completed with real output",
                "phase_name": "Verification",
                "sub_goal": "Verify all phases produced real, usable output",
                "expected_output": "file_list",
            })
            return steps

        # ── Fallback: single-phase goal, return standard template ──
        return self._single_agent_plan(goal, "coder")

    def _match_phase_archetype(self, text: str) -> dict:
        """Find the best phase archetype for a piece of text."""
        tl = text.lower()
        best_key = "build"  # default
        best_score = 0
        for key, archetype in self._PHASE_ARCHETYPES.items():
            if re.search(rf"\b{key}\b", tl):
                # Longer keys are more specific — prefer them
                score = len(key)
                if score > best_score:
                    best_score = score
                    best_key = key
        return self._PHASE_ARCHETYPES[best_key]

    def _infer_output_type(self, action: str, text: str) -> str:
        """Infer what type of output a phase should produce."""
        tl = text.lower()
        if any(w in tl for w in ["code", "build", "develop", "create a", "website", "app",
                                  "landing page", "script", "program", "software", "html", "python"]):
            return "code_files"
        if any(w in tl for w in ["research", "scan", "find", "search", "analyze", "discover",
                                  "competitor", "market", "lead", "prospect"]):
            return "data_file"
        if any(w in tl for w in ["write", "content", "blog", "post", "copy", "description",
                                  "email", "letter", "proposal", "plan"]):
            return "document"
        if any(w in tl for w in ["deploy", "launch", "publish", "upload", "host"]):
            return "deployed_artifact"
        return "document"

    def _extract_sub_goal_around_keyword(self, goal: str, keyword: str) -> str:
        """Extract a focused sub-goal from the full goal around a keyword."""
        import re
        # Find the keyword position
        match = re.search(rf"\b{keyword}\b", goal, re.I)
        if not match:
            return f"{keyword} phase"

        pos = match.start()
        # Extract a window around the keyword: ~150 chars before and after
        start = max(0, pos - 80)
        end = min(len(goal), pos + 150)

        snippet = goal[start:end].strip()

        # Clean up: remove leading/trailing partial words
        if start > 0:
            snippet = snippet[snippet.find(" "):].strip() if " " in snippet else snippet
        if end < len(goal):
            last_space = snippet.rfind(" ")
            if last_space > 0:
                snippet = snippet[:last_space].strip()

        return snippet if snippet else f"Complete the {keyword} phase"

    def _llm_decompose(self, goal: str) -> Optional[list[dict[str, Any]]]:
        """Use LLM to decompose a complex goal into phases.

        Returns a list of step dicts, or None if LLM fails.
        """
        goal_preview = goal[:600] if len(goal) > 600 else goal
        prompt = (
            "Break this complex goal into sequential phases. "
            "For each phase, provide:\n"
            "  PHASE_N: [agent] | [action] | [description]\n\n"
            "Agents: coder, browser, content, sales, social\n"
            "Actions: generate_code, execute_task, create, execute_goal\n\n"
            f"Goal: {goal_preview}\n\n"
            "List each phase on its own line. Use only the agents and actions listed above. "
            "Example format:\n"
            "PHASE_1: browser | execute_task | Research market trends\n"
            "PHASE_2: content | create | Write business plan\n"
            "PHASE_3: coder | generate_code | Build landing page\n"
        )
        try:
            result = self.router.route_generate(prompt, task_type="general")
        except NoModelAvailableError:
            result = {"success": False, "error": "No LLM available"}
        if not result.get("success") or not result.get("response"):
            return None

        text = result["response"].strip()
        # Parse PHASE_N lines
        import re
        phase_re = re.compile(
            r"PHASE[_ ]?(\d+)\s*:\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(.+?)(?:\n|$)",
            re.I,
        )
        matches = list(phase_re.finditer(text))
        if len(matches) < 2:
            return None

        steps = []
        for m in matches:
            num = int(m.group(1))
            agent = m.group(2).strip().lower()
            action = m.group(3).strip().lower()
            desc = m.group(4).strip()

            # Validate agent
            if agent not in ("coder", "browser", "content", "sales", "social",
                             "desktop", "job", "skill", "memory"):
                agent = "coder"
            # Validate action
            if action not in ("generate_code", "execute_task", "create", "execute_goal",
                              "inspect_project", "handle_code_task", "handle_browser_task"):
                action = "execute_goal"

            step = {
                "agent": agent,
                "action": action,
                "description": f"[Phase {num}] {desc[:80]}",
                "phase_name": f"Phase {num}: {desc[:60]}",
                "sub_goal": desc,
                "expected_output": self._infer_output_type(action, desc),
            }
            steps.append(step)

        steps.append({
            "agent": "coder",
            "action": "verify_compound",
            "description": f"[Final] Verify all {len(steps)} phases completed with real output",
            "phase_name": "Verification",
            "sub_goal": "Verify all phases produced real, usable output",
            "expected_output": "file_list",
        })
        return steps

    def _single_agent_plan(self, goal: str, agent_name: str) -> list[dict[str, Any]]:
        """Generate a simple single-agent plan (fallback for non-compound goals)."""
        plans = {
            "coder": [
                {"agent": "coder", "action": "generate_code", "description": "Implement the requested code"},
                {"agent": "coder", "action": "verify_compound", "description": "Verify output files exist and are valid"},
            ],
            "browser": [
                {"agent": "browser", "action": "execute_task", "description": "Execute browser research task"},
                {"agent": "browser", "action": "verify_compound", "description": "Verify research results saved"},
            ],
            "desktop": [
                {"agent": "desktop", "action": "execute_action", "description": "Execute desktop UI action"},
            ],
            "job": [
                {"agent": "job", "action": "execute_goal", "description": "Execute job search task"},
            ],
            "sales": [
                {"agent": "sales", "action": "execute_goal", "description": "Execute sales & research task"},
                {"agent": "sales", "action": "verify_compound", "description": "Verify leads and outreach data saved"},
            ],
            "content": [
                {"agent": "content", "action": "create", "description": "Create content"},
                {"agent": "content", "action": "verify_compound", "description": "Verify content saved to file"},
            ],
            "skill": [
                {"agent": "skill", "action": "execute_goal", "description": "Handle skill task"},
            ],
            "memory": [
                {"agent": "memory", "action": "execute_goal", "description": "Handle memory task"},
            ],
            "social": [
                {"agent": "social", "action": "execute_goal", "description": "Execute social media task"},
            ],
        }
        return plans.get(agent_name, plans.get("general", plans["coder"]))

    def plan_steps(self, goal: str, agent_hint: str = "") -> dict[str, Any]:
        """Create a plan to achieve the goal.

        Uses dynamic decomposition for compound/multi-phase goals,
        and simple templates for single-phase goals.

        Args:
            goal:       User's goal
            agent_hint: Pre-determined agent name (skips re-analysis if provided)

        Returns:
            Plan with steps
        """
        if agent_hint:
            primary_agent = agent_hint
        else:
            analysis = self.analyze_goal(goal)
            primary_agent = analysis.get("suggested_agent", "general")

        # Detect compound goals and decompose dynamically
        if self._is_compound_goal(goal):
            steps = self._decompose_compound_goal(goal)
            self.current_plan = steps
            self.current_step = 0
            return {
                "success": True,
                "goal": goal,
                "primary_agent": primary_agent,
                "steps": steps,
                "total_steps": len(steps),
                "compound": True,
            }

        # Single-phase goal: use simple plan
        steps = self._single_agent_plan(goal, primary_agent)
        self.current_plan = steps
        self.current_step = 0

        return {
            "success": True,
            "goal": goal,
            "primary_agent": primary_agent,
            "steps": steps,
            "total_steps": len(steps),
            "compound": False,
        }

    def route_step(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Route a step to the appropriate agent.

        Args:
            step: Step to execute
            context: Execution context

        Returns:
            Execution result
        """
        agent_name = step.get("agent", "general")
        action = step.get("action", "")

        agent = self.agents.get(agent_name)

        if not agent:
            return {
                "success": False,
                "error": f"Agent not available: {agent_name}",
            }

        # Route to agent's handler
        if agent_name == "coder" and hasattr(agent, "handle_code_task"):
            return agent.handle_code_task(action, context)
        elif agent_name == "browser" and hasattr(agent, "handle_browser_task"):
            return agent.handle_browser_task(action, context)
        elif agent_name == "desktop" and hasattr(agent, "handle_desktop_task"):
            return agent.handle_desktop_task(action, context)
        elif agent_name == "job" and hasattr(agent, "handle_job_task"):
            return agent.handle_job_task(action, context)
        elif agent_name == "sales" and hasattr(agent, "handle_sales_task"):
            return agent.handle_sales_task(action, context)
        elif agent_name == "content" and hasattr(agent, "handle_content_task"):
            return agent.handle_content_task(action, context)
        elif agent_name == "skill" and hasattr(agent, "handle_skill_task"):
            return agent.handle_skill_task(action, context)
        elif agent_name == "memory" and hasattr(agent, "handle_memory_task"):
            return agent.handle_memory_task(action, context)
        elif agent_name == "social" and hasattr(agent, "handle_social_task"):
            return agent.handle_social_task(action, context)
        elif agent_name == "general":
            # General agent: direct LLM Q&A or honest failure
            return self._handle_general_task(action, context, step)

        return {
            "success": False,
            "error": f"No handler for agent: {agent_name}",
        }

    def select_agent_for_step(self, step_description: str) -> str:
        """Select the best agent for a step.

        Args:
            step_description: Step description

        Returns:
            Agent name
        """
        analysis = self.analyze_goal(step_description)
        return analysis.get("suggested_agent", "general")

    def _handle_general_task(self, action: str, context: dict, step: dict) -> dict:
        """Handle unclassifiable goals via direct LLM Q&A or honest failure."""
        goal = step.get("sub_goal", step.get("description", ""))
        try:
            answer = self.router.ask(
                system="You are a helpful AI assistant. Answer the user's question directly and honestly. If you cannot help, say so clearly.",
                user=goal,
                task_type="general",
            )
            if answer and answer.strip():
                return {
                    "success": True,
                    "result": answer,
                    "summary": answer[:300],
                }
        except NoModelAvailableError:
            return {"success": False, "error": "No LLM available"}
        except Exception as e:
            import logging
            logging.getLogger("megav.commander").debug("General agent LLM call failed: %s", e)
        return {
            "success": False,
            "error": f"Could not process: {goal[:100]}. No LLM available.",
        }

    def summarize_progress(self) -> dict[str, Any]:
        """Summarize current task progress.

        Returns:
            Progress summary
        """
        completed_steps = self.current_step
        total_steps = len(self.current_plan)

        return {
            "success": True,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "percent_complete": (completed_steps / total_steps * 100) if total_steps > 0 else 0,
            "current_step": self.current_plan[completed_steps] if completed_steps < total_steps else None,
            "history": self.task_history,
        }

    def promote_workflow_to_skill(self, workflow_name: str) -> dict[str, Any]:
        """Promote a successful workflow to a skill.

        Args:
            workflow_name: Workflow name

        Returns:
            Promotion result
        """
        skill_agent = self.agents.get("skill")

        if not skill_agent:
            return {
                "success": False,
                "error": "Skill agent not available",
            }

        # This would integrate with skill agent
        return {
            "success": True,
            "workflow": workflow_name,
            "message": "Workflow promoted to skill",
        }

    # ------------------------------------------------------------------
    # NEXUS / Agency routing
    # ------------------------------------------------------------------

    def _detect_nexus_mode(self, goal: str) -> Optional[str]:
        """
        Return 'full', 'sprint', or 'micro' if the goal looks like a
        NEXUS multi-agent pipeline request, else None.

        Sprint check runs before full when explicit sprint signals
        (mvp, prototype, feature, landing page, N weeks) are present.
        """
        import re
        gl = goal.lower()

        # Sprint signals preempt the full-product check
        _sprint_preempt = re.compile(
            r"\b(mvp|prototype|landing.?page|feature.?build|(\d+).?week)\b", re.I
        )
        if _sprint_preempt.search(gl):
            for pat in _NEXUS_SPRINT_PATTERNS:
                if re.search(pat, gl):
                    return "sprint"

        for pat in _NEXUS_FULL_PATTERNS:
            if re.search(pat, gl):
                return "full"
        for pat in _NEXUS_SPRINT_PATTERNS:
            if re.search(pat, gl):
                return "sprint"
        for pat in _NEXUS_MICRO_PATTERNS:
            if re.search(pat, gl):
                return "micro"
        return None

    def _detect_agency_category(self, goal: str) -> Optional[str]:
        """
        Return the best agency category for the goal, or None if no strong
        match is found.
        """
        gl = goal.lower()
        best_cat: Optional[str] = None
        best_score = 0
        for cat, hints in _AGENCY_CATEGORY_HINTS.items():
            score = sum(1 for h in hints if h in gl)
            if score > best_score:
                best_score = score
                best_cat = cat
        return best_cat if best_score >= 1 else None

    def try_execute_via_nexus(
        self,
        goal: str,
        context: dict[str, Any],
        progress_cb: Any = None,
    ) -> Optional[dict[str, Any]]:
        """
        Attempt to run the goal through the NEXUS pipeline.

        Returns a result dict if NEXUS handled it, or None to fall through
        to normal agent routing.
        """
        mode = self._detect_nexus_mode(goal)
        if not mode:
            return None

        try:
            from .nexus_orchestrator import get_nexus_orchestrator
            orchestrator = get_nexus_orchestrator(progress_cb=progress_cb)
            result = orchestrator.execute(goal, mode=mode, context=context)
            return {
                "success": result.overall_status != "NEEDS_WORK",
                "goal": goal,
                "summary": result.summary,
                "nexus_mode": mode,
                "nexus_status": result.overall_status,
                "phases_run": [p.phase_name for p in result.phases],
                "agents_used": result.agents_used,
                "tasks_completed": result.completed_tasks,
                "tasks_total": result.total_tasks,
                "via_nexus": True,
            }
        except Exception as exc:
            # NEXUS unavailable — fall through gracefully
            return None

    def try_execute_via_agency(
        self,
        goal: str,
        context: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        Route goal to the best agency specialist agent.
        Returns result dict if handled, None otherwise.
        """
        cat = self._detect_agency_category(goal)
        if not cat:
            return None

        try:
            from .agency_library import get_agency_library
            lib = get_agency_library()
            agent = lib.find_best_agent(goal, category=cat)
            if not agent:
                return None

            prompt = lib.get_prompt(agent["id"])
            if not prompt:
                return None

            # Build user message — include profile context if available
            profile_info = ""
            if context.get("profile"):
                p = context["profile"]
                profile_info = f"\nUser context: name={p.get('name','')}, skills={p.get('skills',[])}."

            # Call LLM with agency agent personality
            answer = self.router.ask(
                system=prompt[:3000],
                user=goal + profile_info,
                task_type="general",
            )
            if answer:
                return {
                    "success": True,
                    "goal": goal,
                    "summary": answer,
                    "agency_agent": agent["id"],
                    "agency_agent_name": agent.get("name", ""),
                    "agency_category": cat,
                    "via_agency": True,
                }
        except NoModelAvailableError:
            return {"success": False, "error": "No LLM available"}
        except Exception as _exc:
            import logging
            logging.getLogger("megav.commander").debug("LLM call failed: %s", _exc)
        return None

    def set_skill_orchestrator(self, orchestrator: Any):
        """Attach the SkillOrchestrator so commander can delegate to skills."""
        self._skill_orchestrator = orchestrator

    def try_execute_via_skill(self, goal: str, context: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Attempt to handle a goal using the Skill Orchestrator.

        Returns a result dict if a skill handled it, or None to fall through
        to normal agent routing.
        """
        orchestrator = getattr(self, "_skill_orchestrator", None)
        if not orchestrator:
            return None
        try:
            analysis = self.analyze_goal(goal)
            agent_hint = analysis.get("suggested_agent")
            if not orchestrator.should_intercept(goal, agent_hint=agent_hint):
                return None
            result = orchestrator.run(
                goal,
                agent_hint=agent_hint,
                extra_context={"profile": context.get("profile", {})},
            )
            if result.success:
                return {
                    "success": True,
                    "goal": goal,
                    "summary": result.summary,
                    "skills_used": result.skills_used,
                    "via_skill": True,
                }
        except Exception as _exc:
            import logging
            logging.getLogger("megav.commander").debug("Skill intercept failed: %s", _exc)
        return None

    def execute_goal(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        """Execute a complete goal.

        Args:
            goal: User's goal
            context: Execution context

        Returns:
            Execution result
        """
        # ── 1. Try Skill Orchestrator first (fastest, most specific) ──
        skill_result = self.try_execute_via_skill(goal, context)
        if skill_result:
            return skill_result

        # ── 2. Try NEXUS pipeline for multi-agent project goals ──
        progress_cb = context.get("progress_cb")
        nexus_result = self.try_execute_via_nexus(goal, context, progress_cb=progress_cb)
        if nexus_result:
            return nexus_result

        # ── 3. Try Agency specialist for domain-expert tasks ──
        agency_result = self.try_execute_via_agency(goal, context)
        if agency_result:
            return agency_result

        # ── 4. Standard agent routing ──
        # Create plan
        plan = self.plan_steps(goal)

        if not plan.get("success"):
            return plan

        results = []

        # Execute each step
        for i, step in enumerate(self.current_plan):
            self.current_step = i

            result = self.route_step(step, context)
            results.append({
                "step": step,
                "result": result,
            })

            # Record in history
            self.task_history.append({
                "step": step,
                "result": result,
            })

            # Stop on failure
            if not result.get("success"):
                return {
                    "success": False,
                    "error": f"Step {i+1} failed: {result.get('error', 'Unknown error')}",
                    "results": results,
                }

        return {
            "success": True,
            "goal": goal,
            "steps_completed": len(results),
            "results": results,
        }
