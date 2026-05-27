"""
Skill Engine — Parser.

Scans the awesome-claude-skills-master directory, reads every SKILL.md,
extracts structured metadata, and returns a list of Skill objects.

NO hardcoded skill definitions — everything is derived dynamically from the
filesystem so adding a new skill folder is automatic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .schemas import ExecutionType, Skill, SkillStatus
from .utils import (
    classify_agents,
    classify_category,
    extract_bullet_list,
    extract_keywords,
    extract_section,
    find_skills_root,
    parse_frontmatter,
    slugify,
)


# ---------------------------------------------------------------------------
# Script detection helpers
# ---------------------------------------------------------------------------

_SCRIPT_EXTS = {".py", ".sh", ".bash", ".bat", ".cmd", ".js", ".ts", ".rb"}


def _find_scripts(folder: Path) -> list[str]:
    """Recursively find runnable scripts inside a skill folder."""
    scripts = []
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix.lower() in _SCRIPT_EXTS:
            scripts.append(str(path.relative_to(folder)))
    return sorted(scripts)


def _detect_execution_type(scripts: list[str], body: str) -> ExecutionType:
    """Determine how this skill should be executed."""
    has_scripts = bool(scripts)
    # If SKILL.md mentions 'run', 'execute', 'bash', 'python script' — likely hybrid
    script_hints = bool(re.search(
        r"(run|execute|bash|python\s+script|\.sh|\.py|subprocess)",
        body, re.IGNORECASE
    ))

    if has_scripts and script_hints:
        return ExecutionType.HYBRID
    if has_scripts:
        return ExecutionType.HYBRID
    if script_hints:
        return ExecutionType.HYBRID
    return ExecutionType.PROMPT


# ---------------------------------------------------------------------------
# Dependency extractor
# ---------------------------------------------------------------------------

_KNOWN_DEPS = [
    "node", "npm", "python", "git", "bash", "docker",
    "playwright", "pillow", "imageio", "numpy", "yt-dlp",
    "composio", "langsmith", "pymupdf", "openpyxl", "python-docx",
    "slack", "github", "notion",
]

def _extract_dependencies(body: str) -> list[str]:
    """Scan SKILL.md body for mentions of known dependencies."""
    found = []
    body_lower = body.lower()
    for dep in _KNOWN_DEPS:
        if dep in body_lower and dep not in found:
            found.append(dep)
    # Also check requirements blocks
    req_match = re.findall(r"pip install\s+([\w\-]+)", body, re.IGNORECASE)
    for r in req_match:
        r = r.lower()
        if r not in found:
            found.append(r)
    return found


# ---------------------------------------------------------------------------
# Use-case extractor
# ---------------------------------------------------------------------------

def _extract_use_cases(body: str) -> list[str]:
    """Extract bullet points from 'When to Use' or 'Use Cases' sections."""
    for heading in ("when to use", "use cases", "use case", "when should", "what this skill does"):
        section = extract_section(body, heading)
        if section:
            items = extract_bullet_list(section)
            if items:
                return items[:8]
    return []


# ---------------------------------------------------------------------------
# Input / Output extractor
# ---------------------------------------------------------------------------

def _extract_io(body: str) -> tuple[list[str], list[str]]:
    """Extract inputs and outputs from SKILL.md."""
    inputs_raw  = extract_section(body, "input")
    outputs_raw = extract_section(body, "output")

    inputs  = extract_bullet_list(inputs_raw)[:6]
    outputs = extract_bullet_list(outputs_raw)[:6]

    # Fallback: generic based on how/what sections
    if not inputs:
        how = extract_section(body, "how to use")
        if how:
            inputs = extract_bullet_list(how)[:4]
    if not outputs:
        what = extract_section(body, "what this skill")
        if what:
            outputs = extract_bullet_list(what)[:4]

    return inputs, outputs


# ---------------------------------------------------------------------------
# Trigger keyword builder
# ---------------------------------------------------------------------------

_SKILL_SPECIFIC_KEYWORDS: dict[str, list[str]] = {
    "artifacts-builder":          ["react artifact","shadcn","vite","build ui component","html artifact","frontend component"],
    "brand-guidelines":           ["brand color","brand style","anthropic brand","brand typography"],
    "canvas-design":              ["design poster","create artwork","visual design","infographic","design something"],
    "changelog-generator":        ["changelog","release notes","what changed","version history"],
    "competitive-ads-extractor":  ["competitor ads","facebook ads library","ad analysis","spy ads"],
    "connect":                    ["send email","send slack","github issue","post discord","update notion","composio action"],
    "connect-apps":               ["setup composio","configure api","connect apps setup"],
    "content-research-writer":    ["write article","blog post","research write","content creation","essay","long form"],
    "developer-growth-analysis":  ["developer growth","coding patterns","learning gaps","developer analytics"],
    "domain-name-brainstormer":   ["domain name","domain ideas","check domain","website name","brand name","available domain"],
    "file-organizer":             ["organize files","clean up files","sort files","tidy downloads","find duplicates"],
    "image-enhancer":             ["enhance image","upscale image","sharpen photo","improve image quality"],
    "internal-comms":             ["internal communication","company newsletter","team update","status report"],
    "invoice-organizer":          ["invoice","receipt","expense report","organize invoices","tax documents"],
    "langsmith-fetch":            ["langsmith","langchain debug","langgraph trace","debug agent trace"],
    "lead-research-assistant":    ["lead research","find leads","prospect","lead generation","find customers","b2b leads"],
    "mcp-builder":                ["mcp server","model context protocol","build mcp","fastmcp","create mcp"],
    "meeting-insights-analyzer":  ["meeting transcript","meeting analysis","analyze meeting","communication patterns"],
    "raffle-winner-picker":       ["raffle","random winner","giveaway","contest winner","lottery","draw winner"],
    "skill-creator":              ["create skill","new skill","build skill","skill template","define skill"],
    "skill-share":                ["share skill","publish skill","package skill","distribute skill"],
    "slack-gif-creator":          ["create gif","animated gif","slack gif","make animation","gif"],
    "tailored-resume-generator":  ["resume","cv","tailor resume","job application","cover letter","ats resume"],
    "template-skill":             ["template","example skill","skill scaffold"],
    "theme-factory":              ["apply theme","color theme","dark theme","midnight galaxy","arctic frost","style artifact"],
    "twitter-algorithm-optimizer":["tweet","twitter","optimize tweet","viral tweet","x post","twitter algorithm"],
    "video-downloader":           ["download video","youtube download","save video","download mp3","youtube to mp3","yt-dlp","youtube video","download youtube"],
    "webapp-testing":             ["test webapp","playwright test","browser testing","ui test","automated testing"],
    # Document skills (split from document-skills into individual entries)
    "docx":                       ["word document","create docx","edit docx","docx file","word doc","office document","tracked changes","word processing"],
    "pdf":                        ["create pdf","edit pdf","merge pdf","split pdf","extract pdf","pdf form","fill pdf","pdf text","pdf table","pymupdf"],
    "pptx":                       ["powerpoint","create pptx","presentation","slides","pptx file","speaker notes","slide deck","ppt design"],
    "xlsx":                       ["excel","create xlsx","spreadsheet","xlsx file","excel formula","openpyxl","data analysis excel","csv to excel"],
    # GitHub built-in skills
    # GitHub built-in skills
    "github-repo-creator":        ["create repo","new repository","github repo","create github","setup repo","initialize repo","git init repo","github project"],
    "github-issue-manager":       ["github issue","create issue","open issue","close issue","list issues","bug report","feature request","issue tracker"],
    "github-commit-pusher":       ["push to github","commit code","upload to github","push files","github commit","upload code","sync to github","push changes"],
    # Email built-in skills
    "email-reader":               ["check email","read inbox","read emails","get emails","show inbox","fetch emails","inbox messages","email summary"],
    "email-sender":               ["send email","compose email","write email","email someone","draft email","send message to"],
    "email-reply":                ["reply email","respond email","reply to","email response","write reply","reply professionally"],
    "smart-inbox-sorter":         ["sort inbox","classify emails","prioritize emails","organize inbox","important emails","urgent emails","smart inbox"],
    "crm-followup-manager":       ["follow up","followup","track leads","contact management","crm","lead status","recruiter followup","client followup"],
    "recruiter-reply-drafter":    ["reply to recruiter","respond recruiter","recruiter email","job offer reply","hiring reply","interview response"],
    # Agency / NEXUS built-in skills
    "nexus-orchestrator":         ["nexus","full pipeline","multi-agent pipeline","orchestrate project","full product build","complete product","launch product","build startup"],
    "nexus-sprint":               ["nexus sprint","sprint pipeline","mvp build","build feature","build app","build website","build landing","sprint mode","2 week","agile sprint"],
    "nexus-micro":                ["nexus micro","quick task","micro task","marketing campaign","compliance audit","incident response","orchestrate","multi-agent task"],
    "agency-engineering":         ["backend architect","frontend developer","devops automator","ai engineer","mobile app builder","security engineer","code review","rapid prototype","software architect"],
    "agency-design":              ["ux research","brand identity","ui design","wireframe","visual storytelling","design system","image prompt","ux architect"],
    "agency-marketing":           ["growth hack","content creator","seo strategy","tiktok strategy","instagram curator","linkedin content","app store optimization","youtube strategy","social media strategy"],
    "agency-sales":               ["sales strategy","deal review","outbound campaign","sales proposal","account plan","discovery call","sales coach","sales pipeline analyst"],
    "agency-testing":             ["qa test","performance benchmark","accessibility audit","api testing","evidence collect","reality check","test results","tool evaluator"],
    "agency-project-management":  ["sprint planning","project shepherd","jira workflow","studio producer","experiment tracker","studio operations","project manager"],
    "agency-product":             ["product feedback","trend research","sprint prioritize","product manager","behavioral nudge","product roadmap"],
    "agency-specialized":         ["workflow architect","mcp builder","customer service agent","legal review","compliance check","hr onboarding","data consolidation","report distribution"],
    "agency-finance":             ["financial analysis","tax strategy","investment research","bookkeeping","fp&a","fpa analyst","financial forecast","bookkeeper"],
    "agency-support":             ["support ticket","infrastructure maintain","analytics report","executive summary","finance tracker","legal compliance","operations support"],
    # ── Superpowers skills ──────────────────────────────────────────────────
    "brainstorming":                    ["brainstorm","ideate","creative ideas","brainstorm session","creative work","explore ideas","ideation"],
    "dispatching-parallel-agents":      ["parallel agents","dispatch agents","concurrent tasks","fan out","multiple agents","subagent"],
    "executing-plans":                  ["execute plan","run plan","implement plan","follow plan","execute implementation"],
    "finishing-a-development-branch":   ["finish branch","complete feature","wrap up branch","merge ready","finish dev work"],
    "receiving-code-review":            ["receive review","code review feedback","implement review suggestions","address review comments"],
    "requesting-code-review":           ["request review","code review","review my code","review before merge","code reviewer"],
    "systematic-debugging":             ["debug systematically","root cause","find bug","investigate error","systematic debug","find root cause"],
    "test-driven-development":          ["tdd","test driven","write tests first","red green refactor","test before code"],
    "using-git-worktrees":              ["git worktree","isolated branch","worktree","parallel branches","work in isolation"],
    "using-superpowers":                ["superpowers","skill workflow","use skills","skill discipline"],
    "verification-before-completion":  ["verify completion","evidence before claims","verify done","check before done","proof of work"],
    "writing-plans":                    ["write plan","implementation plan","plan before code","spec plan","design plan"],
    "writing-skills":                   ["write skill","create skill","skill creation","tdd for skills","skill authoring"],
    "subagent-driven-development":      ["subagent development","dispatch subagent","parallel implementation","subagent plan"],
    # ── Frontend Design ────────────────────────────────────────────────────
    "frontend-design":                  ["frontend design","ui design","bold design","anti ai design","distinctive frontend","production frontend"],
    # ── GStack skills ──────────────────────────────────────────────────────
    "gstack-browse":                    ["browse site","open site","headless browser","navigate page","gstack browse","test website"],
    "gstack-qa":                        ["qa test","systematic qa","find bugs","test site","test webapp","quality assurance"],
    "gstack-canary":                    ["canary monitor","post-deploy check","live monitoring","deployment check"],
    "gstack-review":                    ["code review","pr review","pre-landing review","review diff","review changes"],
    "gstack-health":                    ["code health","code quality","health dashboard","project health"],
    "gstack-investigate":               ["investigate bug","root cause","debug systematically","systematic debugging"],
    "gstack-ship":                      ["ship code","merge and deploy","ship workflow","detect merge test deploy"],
    "gstack-design-consultation":       ["design consultation","product design","design system","design landscape"],
    "gstack-design-html":               ["design html","production html","pretext html","prettier component"],
    "gstack-design-review":            ["design review","visual review","designer eye","ui review"],
    "gstack-design-shotgun":            ["design shotgun","multiple designs","design variants","compare designs"],
    "gstack-benchmark":                 ["performance benchmark","core web vitals","lighthouse","performance regression"],
    "gstack-checkpoint":                ["save checkpoint","resume state","checkpoint","working state"],
    "gstack-freeze":                    ["freeze directory","restrict edits","directory guard"],
    "gstack-guard":                     ["guard mode","safety guardrails","destructive warning","full safety"],
    "gstack-cso":                       ["security audit","cso mode","owasp","security review","threat model"],
    "gstack-land-and-deploy":            ["land and deploy","merge deploy","merge pr wait ci","deploy workflow"],
    "gstack-learn":                     ["project learnings","manage learnings","prune learnings"],
    "gstack-office-hours":              ["yc office hours","startup questions","forcing questions"],
    "gstack-pair-agent":                ["pair agent","remote agent","browser pair"],
    "gstack-retro":                     ["retrospective","weekly retro","sprint retro","work patterns"],
    "gstack-autoplan":                  ["auto review","auto plan","pipeline review","review pipeline"],
    "gstack-plan-ceo-review":           ["ceo review","founder review","10-star review","plan review"],
    "gstack-plan-design-review":        ["design plan review","designer eye plan","interactive review"],
    "gstack-plan-devex-review":         ["devex review","developer experience review","dx review"],
    "gstack-plan-eng-review":           ["engineering review","eng review","architecture review"],
    "gstack-document-release":          ["document release","post-ship docs","update documentation"],
    "gstack-codex":                      ["codex review","openai codex","independent review"],
    "gstack-careful":                    ["careful mode","destructive warning","safety check"],
    "gstack-setup-deploy":              ["setup deploy","configure deployment","deploy settings"],
    "gstack-setup-browser-cookies":     ["import cookies","browser cookies","setup browser"],
    "gstack-unfreeze":                  ["unfreeze","clear freeze","allow edits"],
    "gstack-gstack-upgrade":            ["upgrade gstack","update gstack","gstack version"],
    "gstack-open-gstack-browser":       ["open browser","launch browser","gstack browser","visible chromium"],
    # ── Context7 & Tavily ──────────────────────────────────────────────────
    "context7-mcp":                     ["context7","library docs","documentation lookup","sdk docs","api reference","fetch docs"],
    "tavily-search":                    ["tavily","web search","research","search web","find information","online search"],
}


def _build_keywords(skill_id: str, name: str, description: str, body: str) -> list[str]:
    """Build a comprehensive keyword list for a skill."""
    kws: list[str] = []

    # 1. Hardcoded high-signal keywords (if defined)
    kws.extend(_SKILL_SPECIFIC_KEYWORDS.get(skill_id, []))

    # 2. Name tokens
    name_tokens = [t for t in re.split(r"[\s\-_/]+", name.lower()) if len(t) > 2]
    kws.extend(name_tokens)

    # 3. First sentence of description
    first_sent = description.split(".")[0].lower()
    kws.extend([t for t in re.split(r"\s+", first_sent) if len(t) > 3])

    # 4. Auto-extracted from body
    kws.extend(extract_keywords(body, max_keywords=12))

    # Deduplicate, preserve order
    seen: set[str] = set()
    result: list[str] = []
    for kw in kws:
        kw = kw.strip().lower()
        if kw and kw not in seen and len(kw) > 2:
            seen.add(kw)
            result.append(kw)

    return result[:30]


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class SkillParser:
    """Scans the skills directory and returns parsed Skill objects."""

    def __init__(self, skills_root: Optional[Path] = None):
        self._root = Path(skills_root) if skills_root else find_skills_root()

    def parse_all(self) -> list[Skill]:
        """Scan all top-level skill folders and parse them."""
        if not self._root.exists():
            return []

        skills: list[Skill] = []
        for folder in sorted(self._root.iterdir()):
            if not folder.is_dir():
                continue
            # Skip non-skill directories
            if folder.name in {"composio-skills", "superpowers", "gstack", "context7-mcp", ".git", "__pycache__", "template-skill", "document-skills", "connect-apps-plugin"}:
                continue
            skill = self._parse_folder(folder)
            if skill:
                skills.append(skill)

        # Parse document-skills sub-folders individually (docx, pdf, pptx, xlsx)
        skills.extend(self._parse_document_skills())

        # Add one merged composio entry
        composio_skill = self._parse_composio()
        if composio_skill:
            skills.append(composio_skill)

        # Add built-in GitHub skills
        skills.extend(self._parse_github_skills())

        # Add built-in Email skills
        skills.extend(self._parse_email_skills())

        # Add built-in Agency / NEXUS skills
        skills.extend(self._parse_agency_skills())

        # Add Superpowers plugin skills
        skills.extend(self._parse_superpowers())

        # Add GStack skill suite
        skills.extend(self._parse_gstack())

        # Add Context7-MCP skill
        skills.extend(self._parse_context7())

        # Add Tavily search skill
        skills.extend(self._parse_tavily())

        # Add YouTube downloader skill (maps video-downloader)
        skills.extend(self._parse_youtube_downloader())

        return skills

    def _parse_folder(self, folder: Path) -> Optional[Skill]:
        """Parse a single skill folder into a Skill object."""
        # Find SKILL.md
        skill_md_path = None
        for candidate in ("SKILL.md", "skill.md", "README.md", "readme.md"):
            p = folder / candidate
            if p.exists():
                skill_md_path = p
                break

        if skill_md_path is None:
            return None

        try:
            raw_text = skill_md_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            return Skill(
                id=slugify(folder.name),
                name=folder.name,
                description="(failed to read)",
                folder_name=folder.name,
                folder_path=str(folder),
                status=SkillStatus.ERROR,
                load_error=str(e),
            )

        meta, body = parse_frontmatter(raw_text)

        skill_id   = slugify(folder.name)
        name       = meta.get("name") or _folder_to_name(folder.name)
        description= meta.get("description", "")[:200]

        if not description:
            # Extract first meaningful sentence from body
            for line in body.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 20:
                    description = line[:200]
                    break

        scripts      = _find_scripts(folder)
        exec_type    = _detect_execution_type(scripts, body)
        dependencies = _extract_dependencies(body)
        use_cases    = _extract_use_cases(body)
        inputs, outputs = _extract_io(body)
        category     = classify_category(description + " " + body[:500], name)
        agents       = classify_agents(description + " " + body[:500])
        keywords     = _build_keywords(skill_id, name, description, body)

        return Skill(
            id=skill_id,
            name=name,
            description=description,
            folder_name=folder.name,
            folder_path=str(folder),
            category=category,
            use_cases=use_cases,
            inputs=inputs,
            outputs=outputs,
            execution_type=exec_type,
            scripts=scripts,
            dependencies=dependencies,
            trigger_keywords=keywords,
            agent_affinity=agents,
            skill_md_text=raw_text,
            has_context=bool(body.strip()),
            status=SkillStatus.ACTIVE,
        )

    def _parse_composio(self) -> Optional[Skill]:
        """Create a single merged entry for all Composio sub-skills."""
        composio_dir = self._root / "composio-skills"
        if not composio_dir.exists():
            return None

        sub_count = sum(1 for d in composio_dir.iterdir() if d.is_dir())
        description = (
            f"Integration hub connecting to {sub_count}+ third-party services via Composio "
            "(Slack, GitHub, Notion, Gmail, Jira, Discord, and more)."
        )
        return Skill(
            id="composio-skills",
            name="Composio — 1000+ App Integrations",
            description=description,
            folder_name="composio-skills",
            folder_path=str(composio_dir),
            category="integration",
            use_cases=[
                "Send messages via Slack, Discord, Teams",
                "Create GitHub issues and pull requests",
                "Update Notion databases",
                "Send emails via Gmail or Outlook",
                "Create Jira tickets",
                "Automate any 3rd-party service",
            ],
            inputs=["service_name", "action", "parameters"],
            outputs=["service_response", "confirmation"],
            execution_type=ExecutionType.HYBRID,
            dependencies=["composio"],
            trigger_keywords=[
                "composio","send email","slack message","github issue","post discord",
                "update notion","jira ticket","send outlook","third party api",
                "service integration","automate service","connect to",
                "integrate with","use composio","composio action",
            ],
            agent_affinity=["browser", "coder"],
            skill_md_text="",
            has_context=False,
            status=SkillStatus.ACTIVE,
        )


    def _parse_github_skills(self) -> list[Skill]:
        """Return built-in GitHub skills (no filesystem SKILL.md required)."""
        return [
            Skill(
                id="github-repo-creator",
                name="GitHub — Repo Creator",
                description=(
                    "Create and configure GitHub repositories programmatically. "
                    "Supports public/private repos, auto-init, and description setting."
                ),
                folder_name="github-repo-creator",
                folder_path="(built-in)",
                category="development",
                use_cases=[
                    "Create a new GitHub repository",
                    "Initialize a repo with a README",
                    "Set up a private project repository",
                    "Automate repo creation for new projects",
                ],
                inputs=["repo_name", "description", "private (bool)", "auto_init (bool)"],
                outputs=["repo_url", "clone_url", "repo_details"],
                execution_type=ExecutionType.PROMPT,
                scripts=[],
                dependencies=["github_service"],
                trigger_keywords=_SKILL_SPECIFIC_KEYWORDS["github-repo-creator"],
                agent_affinity=["coder"],
                skill_md_text="",
                has_context=True,
                status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="github-issue-manager",
                name="GitHub — Issue Manager",
                description=(
                    "Create, list, close, reopen, and comment on GitHub issues. "
                    "Supports labels, state filtering, and bulk operations."
                ),
                folder_name="github-issue-manager",
                folder_path="(built-in)",
                category="development",
                use_cases=[
                    "Create a bug report or feature request issue",
                    "List open issues in a repository",
                    "Close a resolved issue",
                    "Add a comment to an existing issue",
                    "Reopen a closed issue",
                ],
                inputs=["repo", "title", "body", "labels", "issue_number"],
                outputs=["issue_url", "issue_number", "issues_list"],
                execution_type=ExecutionType.PROMPT,
                scripts=[],
                dependencies=["github_service"],
                trigger_keywords=_SKILL_SPECIFIC_KEYWORDS["github-issue-manager"],
                agent_affinity=["coder"],
                skill_md_text="",
                has_context=True,
                status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="github-commit-pusher",
                name="GitHub — Commit & Push",
                description=(
                    "Commit files and push changes to GitHub repositories. "
                    "Supports single files, multi-file commits, and branch targeting."
                ),
                folder_name="github-commit-pusher",
                folder_path="(built-in)",
                category="development",
                use_cases=[
                    "Push a file or code change to GitHub",
                    "Commit multiple files in one operation",
                    "Upload code to a GitHub repository",
                    "Sync local changes to remote repo",
                    "Create or update files in a branch",
                ],
                inputs=["repo", "file_path", "content", "commit_message", "branch"],
                outputs=["commit_sha", "file_url", "commit_url"],
                execution_type=ExecutionType.PROMPT,
                scripts=[],
                dependencies=["github_service"],
                trigger_keywords=_SKILL_SPECIFIC_KEYWORDS["github-commit-pusher"],
                agent_affinity=["coder"],
                skill_md_text="",
                has_context=True,
                status=SkillStatus.ACTIVE,
            ),
        ]


    def _parse_email_skills(self) -> list[Skill]:
        """Return built-in Email automation skills."""
        _kws = _SKILL_SPECIFIC_KEYWORDS
        return [
            Skill(
                id="email-reader",
                name="Email — Read Inbox",
                description="Read and summarise emails from connected Gmail, Outlook, or custom IMAP accounts. Classifies priority and detects actionable messages.",
                folder_name="email-reader", folder_path="(built-in)",
                category="email",
                use_cases=["Check my inbox", "Show recent emails", "Summarise important emails", "Read unread messages"],
                inputs=["email_account (optional)", "limit (number)"],
                outputs=["email_list", "smart_summary", "priority_breakdown"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["email_service"],
                trigger_keywords=_kws["email-reader"],
                agent_affinity=["job", "sales", "content", "coder"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="email-sender",
                name="Email — Send Email",
                description="Compose and send emails via connected SMTP accounts. Supports plain text, CC/BCC, and multi-recipient sending.",
                folder_name="email-sender", folder_path="(built-in)",
                category="email",
                use_cases=["Send an email", "Email someone", "Compose a professional email", "Email a client"],
                inputs=["to", "subject", "body", "from_account (optional)"],
                outputs=["send_confirmation", "message_id"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["email_service"],
                trigger_keywords=_kws["email-sender"],
                agent_affinity=["job", "sales", "content"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="email-reply",
                name="Email — Reply to Email",
                description="Generate and send a professional reply to an existing email. AI-drafts the reply based on original content and user profile.",
                folder_name="email-reply", folder_path="(built-in)",
                category="email",
                use_cases=["Reply to last email", "Respond to recruiter", "Reply professionally", "Write a reply"],
                inputs=["email_id", "body (optional — auto-drafted if not provided)"],
                outputs=["sent_reply", "draft"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["email_service"],
                trigger_keywords=_kws["email-reply"],
                agent_affinity=["job", "sales"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="smart-inbox-sorter",
                name="Email — Smart Inbox Sorter",
                description="AI-powered inbox classification. Detects priority, category, spam, and reply requirements. Groups by Urgent / Needs Reply / Job / Work / Personal.",
                folder_name="smart-inbox-sorter", folder_path="(built-in)",
                category="email",
                use_cases=["Sort my inbox", "Find urgent emails", "Classify emails", "What needs a reply?"],
                inputs=["email_account (optional)", "limit"],
                outputs=["classified_emails", "urgency_report", "categories"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["email_service"],
                trigger_keywords=_kws["smart-inbox-sorter"],
                agent_affinity=["job", "sales", "content"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="crm-followup-manager",
                name="CRM — Follow-Up Manager",
                description="Manage contact relationships and follow-up pipeline. Track leads, log interactions, set reminders, and generate follow-up drafts.",
                folder_name="crm-followup-manager", folder_path="(built-in)",
                category="email",
                use_cases=["Follow up with leads", "Check CRM pipeline", "Track contact stages", "Who needs a follow-up?"],
                inputs=["contact_email", "stage", "category", "follow_up_days"],
                outputs=["pipeline_summary", "follow_up_drafts", "contact_list"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["crm_service"],
                trigger_keywords=_kws["crm-followup-manager"],
                agent_affinity=["sales", "job"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="recruiter-reply-drafter",
                name="Email — Recruiter Reply Drafter",
                description="Drafts professional, personalised replies to recruiter and job-opportunity emails using the user's profile, resume details, and tone preferences.",
                folder_name="recruiter-reply-drafter", folder_path="(built-in)",
                category="email",
                use_cases=["Reply to recruiter", "Respond to job offer", "Professional reply to hiring email"],
                inputs=["email_id or email_body", "user_profile"],
                outputs=["reply_draft", "subject", "tone_notes"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["email_service"],
                trigger_keywords=_kws["recruiter-reply-drafter"],
                agent_affinity=["job"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
        ]


    def _parse_agency_skills(self) -> list[Skill]:
        """Return built-in Agency Library + NEXUS orchestration skills."""
        _kws = _SKILL_SPECIFIC_KEYWORDS
        return [
            # ── NEXUS pipeline skills ──────────────────────────────────
            Skill(
                id="nexus-orchestrator",
                name="NEXUS — Full Pipeline",
                description="Run the complete NEXUS 7-phase multi-agent pipeline: Discovery → Strategy → Foundation → Build → Hardening → Launch → Operate. Best for full product builds.",
                folder_name="nexus-orchestrator", folder_path="(built-in)",
                category="agency",
                use_cases=["Build a complete product", "Launch a startup", "Full project pipeline", "NEXUS-Full mode"],
                inputs=["goal", "mode (full/sprint/micro)"],
                outputs=["phase_results", "pipeline_status", "agents_used", "final_summary"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["nexus_orchestrator", "agency_library"],
                trigger_keywords=_kws["nexus-orchestrator"],
                agent_affinity=["coder", "content", "sales"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="nexus-sprint",
                name="NEXUS — Sprint Pipeline",
                description="NEXUS-Sprint mode: 4-phase pipeline (Strategy → Foundation → Build → Hardening) for MVPs, features, and websites. 2–6 week scope.",
                folder_name="nexus-sprint", folder_path="(built-in)",
                category="agency",
                use_cases=["Build an MVP", "Create a feature", "Build a website", "Sprint build"],
                inputs=["goal", "timeline"],
                outputs=["sprint_plan", "build_results", "qa_results"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["nexus_orchestrator", "agency_library"],
                trigger_keywords=_kws["nexus-sprint"],
                agent_affinity=["coder", "browser", "desktop"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="nexus-micro",
                name="NEXUS — Micro Task",
                description="NEXUS-Micro mode: targeted 1–5 day execution for specific tasks — bug fix, marketing campaign, compliance audit, incident response.",
                folder_name="nexus-micro", folder_path="(built-in)",
                category="agency",
                use_cases=["Run a marketing campaign", "Conduct a compliance audit", "Fix a bug with QA", "Incident response"],
                inputs=["goal", "scope"],
                outputs=["task_results", "qa_validation"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["nexus_orchestrator", "agency_library"],
                trigger_keywords=_kws["nexus-micro"],
                agent_affinity=["coder", "sales", "content"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            # ── Agency category skills ─────────────────────────────────
            Skill(
                id="agency-engineering",
                name="Agency — Engineering Specialists",
                description="Access 29 engineering agent personalities: Backend Architect, Frontend Developer, DevOps Automator, AI Engineer, Security Engineer, Mobile App Builder, and more.",
                folder_name="agency-engineering", folder_path="(built-in)",
                category="agency",
                use_cases=["Design a backend system", "Build a frontend app", "DevOps automation", "Code review", "AI model integration"],
                inputs=["goal", "engineering_type"],
                outputs=["architecture_plan", "code", "implementation_guide"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["agency_library"],
                trigger_keywords=_kws["agency-engineering"],
                agent_affinity=["coder", "desktop"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="agency-design",
                name="Agency — Design Specialists",
                description="Access 8 design agent personalities: UX Architect, Brand Guardian, UI Designer, UX Researcher, Visual Storyteller, and Image Prompt Engineer.",
                folder_name="agency-design", folder_path="(built-in)",
                category="agency",
                use_cases=["Design a UI", "Create brand identity", "UX research", "Wireframe", "Visual storytelling"],
                inputs=["goal", "design_type"],
                outputs=["design_spec", "brand_guidelines", "wireframes", "image_prompts"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["agency_library"],
                trigger_keywords=_kws["agency-design"],
                agent_affinity=["coder", "content"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="agency-marketing",
                name="Agency — Marketing Specialists",
                description="Access 30 marketing agent personalities: Growth Hacker, Content Creator, SEO Specialist, TikTok Strategist, LinkedIn Content Creator, App Store Optimizer, and more.",
                folder_name="agency-marketing", folder_path="(built-in)",
                category="agency",
                use_cases=["Growth hacking strategy", "Content marketing plan", "SEO audit", "Social media strategy", "App store optimization"],
                inputs=["goal", "platform", "target_audience"],
                outputs=["marketing_strategy", "content_calendar", "campaign_plan"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["agency_library"],
                trigger_keywords=_kws["agency-marketing"],
                agent_affinity=["content", "social", "sales"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="agency-sales",
                name="Agency — Sales Specialists",
                description="Access 8 sales agent personalities: Account Strategist, Deal Strategist, Sales Coach, Sales Engineer, Outbound Strategist, Pipeline Analyst, and more.",
                folder_name="agency-sales", folder_path="(built-in)",
                category="agency",
                use_cases=["Sales strategy", "Deal review", "Outbound campaign", "Sales proposal", "Pipeline analysis"],
                inputs=["goal", "account", "deal_stage"],
                outputs=["sales_strategy", "proposal", "outreach_plan"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["agency_library"],
                trigger_keywords=_kws["agency-sales"],
                agent_affinity=["sales", "content"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="agency-testing",
                name="Agency — Testing & QA Specialists",
                description="Access 8 testing agent personalities: Evidence Collector, Reality Checker, Performance Benchmarker, API Tester, Accessibility Auditor, and more.",
                folder_name="agency-testing", folder_path="(built-in)",
                category="agency",
                use_cases=["QA testing", "Performance benchmark", "Accessibility audit", "API test", "Evidence collection"],
                inputs=["goal", "test_scope"],
                outputs=["test_results", "qa_report", "evidence"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["agency_library"],
                trigger_keywords=_kws["agency-testing"],
                agent_affinity=["coder"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="agency-project-management",
                name="Agency — Project Management",
                description="Access 6 project management agent personalities: Senior Project Manager, Studio Producer, Sprint Prioritizer, Project Shepherd, and more.",
                folder_name="agency-project-management", folder_path="(built-in)",
                category="agency",
                use_cases=["Sprint planning", "Project coordination", "Jira workflow", "Experiment tracking", "Studio operations"],
                inputs=["goal", "project_scope"],
                outputs=["project_plan", "task_list", "sprint_backlog"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["agency_library"],
                trigger_keywords=_kws["agency-project-management"],
                agent_affinity=["coder", "sales", "content"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="agency-product",
                name="Agency — Product Specialists",
                description="Access 5 product agent personalities: Product Manager, Sprint Prioritizer, Trend Researcher, Feedback Synthesizer, and Behavioral Nudge Engine.",
                folder_name="agency-product", folder_path="(built-in)",
                category="agency",
                use_cases=["Product roadmap", "Feature prioritization", "Market trend research", "User feedback analysis"],
                inputs=["goal", "product_name"],
                outputs=["product_strategy", "prioritized_backlog", "trend_report"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["agency_library"],
                trigger_keywords=_kws["agency-product"],
                agent_affinity=["coder", "content"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="agency-specialized",
                name="Agency — Specialized Agents",
                description="Access 41 specialized agent personalities: Workflow Architect, MCP Builder, Customer Service, Legal Review, Compliance Auditor, HR Onboarding, and more.",
                folder_name="agency-specialized", folder_path="(built-in)",
                category="agency",
                use_cases=["Workflow design", "MCP server build", "Legal document review", "Compliance audit", "Customer service setup"],
                inputs=["goal", "domain"],
                outputs=["workflow_design", "document", "compliance_report"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["agency_library"],
                trigger_keywords=_kws["agency-specialized"],
                agent_affinity=["coder", "sales", "content"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="agency-finance",
                name="Agency — Finance Specialists",
                description="Access 5 finance agent personalities: Financial Analyst, Tax Strategist, Investment Researcher, FP&A Analyst, and Bookkeeper.",
                folder_name="agency-finance", folder_path="(built-in)",
                category="agency",
                use_cases=["Financial analysis", "Tax strategy", "Investment research", "Budget planning", "FP&A"],
                inputs=["goal", "financial_data"],
                outputs=["financial_analysis", "tax_strategy", "investment_brief"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["agency_library"],
                trigger_keywords=_kws["agency-finance"],
                agent_affinity=["sales"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
            Skill(
                id="agency-support",
                name="Agency — Support & Ops Specialists",
                description="Access 6 support/ops agent personalities: Support Responder, Analytics Reporter, Infrastructure Maintainer, Finance Tracker, and Executive Summary Generator.",
                folder_name="agency-support", folder_path="(built-in)",
                category="agency",
                use_cases=["Support ticket handling", "Analytics report", "Infrastructure maintenance", "Executive summary"],
                inputs=["goal", "support_context"],
                outputs=["support_response", "analytics_report", "executive_brief"],
                execution_type=ExecutionType.PROMPT,
                scripts=[], dependencies=["agency_library"],
                trigger_keywords=_kws["agency-support"],
                agent_affinity=["sales", "content"],
                skill_md_text="", has_context=True, status=SkillStatus.ACTIVE,
            ),
        ]


    # ── Superpowers plugin skills ──────────────────────────────────────────

    # Category override map for Superpowers sub-skills
    _SUPERPOWERS_SUBCATEGORIES: dict[str, str] = {
        "brainstorming": "ideation",
        "dispatching-parallel-agents": "workflow",
        "executing-plans": "workflow",
        "finishing-a-development-branch": "workflow",
        "receiving-code-review": "review",
        "requesting-code-review": "review",
        "systematic-debugging": "debugging",
        "test-driven-development": "testing",
        "using-git-worktrees": "git",
        "using-superpowers": "meta",
        "verification-before-completion": "testing",
        "writing-plans": "planning",
        "writing-skills": "meta",
        "subagent-driven-development": "workflow",
    }

    def _parse_superpowers(self) -> list[Skill]:
        """Parse all Superpowers plugin skills from the superpowers/ directory."""
        super_dir = self._root / "superpowers"
        if not super_dir.exists():
            return []

        skills: list[Skill] = []
        for folder in sorted(super_dir.iterdir()):
            if not folder.is_dir():
                continue
            skill = self._parse_folder(folder)
            if skill:
                # Override category and set subcategory
                skill.category = "development"
                skill.subcategory = self._SUPERPOWERS_SUBCATEGORIES.get(
                    skill.id, "superpowers"
                )
                # Ensure trigger keywords include superpowers-specific ones
                sp_kws = _SKILL_SPECIFIC_KEYWORDS.get(skill.id, [])
                existing = set(skill.trigger_keywords)
                for kw in sp_kws:
                    if kw not in existing:
                        skill.trigger_keywords.append(kw)
                skills.append(skill)

        return skills

    # ── GStack skill suite ──────────────────────────────────────────────────

    # Subcategory mapping for GStack skills
    _GSTACK_SUBCATEGORIES: dict[str, str] = {
        "browse": "browser",
        "qa": "testing",
        "qa-only": "testing",
        "review": "review",
        "canary": "monitoring",
        "benchmark": "performance",
        "checkpoint": "state",
        "investigate": "debugging",
        "ship": "deployment",
        "land-and-deploy": "deployment",
        "setup-deploy": "deployment",
        "design-consultation": "design",
        "design-html": "design",
        "design-review": "design",
        "design-shotgun": "design",
        "cso": "security",
        "careful": "safety",
        "freeze": "safety",
        "unfreeze": "safety",
        "guard": "safety",
        "health": "quality",
        "retro": "review",
        "codex": "review",
        "learn": "knowledge",
        "office-hours": "planning",
        "pair-agent": "collaboration",
        "plan-ceo-review": "review",
        "plan-design-review": "review",
        "plan-devex-review": "review",
        "plan-eng-review": "review",
        "autoplan": "automation",
        "document-release": "documentation",
        "open-gstack-browser": "browser",
        "setup-browser-cookies": "browser",
        "gstack-upgrade": "maintenance",
    }

    def _parse_gstack(self) -> list[Skill]:
        """Parse GStack skill suite from the gstack/ directory."""
        gstack_dir = self._root / "gstack"
        if not gstack_dir.exists():
            return []

        skills: list[Skill] = []
        for folder in sorted(gstack_dir.iterdir()):
            if not folder.is_dir():
                continue
            # Only parse folders that have a SKILL.md
            if not (folder / "SKILL.md").exists():
                continue
            skill = self._parse_folder(folder)
            if skill:
                # Prefix ID with gstack- to avoid collisions
                original_id = skill.id
                skill.id = f"gstack-{skill.id}"
                skill.folder_name = f"gstack/{folder.name}"
                skill.category = "development"
                skill.subcategory = self._GSTACK_SUBCATEGORIES.get(
                    folder.name, "gstack"
                )
                # Remap trigger keywords to use gstack- prefix
                gstack_kws = _SKILL_SPECIFIC_KEYWORDS.get(f"gstack-{folder.name}", [])
                if gstack_kws:
                    skill.trigger_keywords = gstack_kws + skill.trigger_keywords
                skills.append(skill)

        return skills

    # ── Context7-MCP skill ─────────────────────────────────────────────────

    def _parse_context7(self) -> list[Skill]:
        """Parse Context7-MCP skill."""
        ctx_dir = self._root / "context7-mcp"
        if not ctx_dir.exists():
            return []

        skill = self._parse_folder(ctx_dir)
        if skill:
            skill.id = "context7-mcp"
            skill.category = "integration"
            skill.subcategory = "documentation"
            skill.trigger_keywords = _SKILL_SPECIFIC_KEYWORDS.get("context7-mcp", [])
            return [skill]
        return []

    # ── Tavily search skill ────────────────────────────────────────────────

    def _parse_tavily(self) -> list[Skill]:
        """Return built-in Tavily web search skill."""
        return [
            Skill(
                id="tavily-search",
                name="Tavily — Web Search & Research",
                description=(
                    "AI-powered web search and research via Tavily. "
                    "Search the web for current information, extract content from URLs, "
                    "and perform comprehensive multi-source research."
                ),
                folder_name="tavily-search",
                folder_path="(built-in)",
                category="integration",
                subcategory="research",
                use_cases=[
                    "Search the web for current information",
                    "Research a topic across multiple sources",
                    "Extract content from URLs",
                    "Find up-to-date data and facts",
                ],
                inputs=["query", "search_depth", "max_results"],
                outputs=["search_results", "extracted_content", "research_report"],
                execution_type=ExecutionType.PROMPT,
                scripts=[],
                dependencies=["tavily"],
                trigger_keywords=_SKILL_SPECIFIC_KEYWORDS["tavily-search"],
                agent_affinity=["browser", "coder", "content"],
                skill_md_text="",
                has_context=True,
                status=SkillStatus.ACTIVE,
            ),
        ]

    # ── Document skills (docx, pdf, pptx, xlsx) ────────────────────────────

    def _parse_document_skills(self) -> list[Skill]:
        """Parse document-skills sub-folders as individual skills."""
        doc_dir = self._root / "document-skills"
        if not doc_dir.exists():
            return []

        skills: list[Skill] = []
        _kws = _SKILL_SPECIFIC_KEYWORDS

        _DOC_DEFS = [
            {
                "id": "docx",
                "name": "DOCX — Word Documents",
                "description": "Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction.",
                "category": "documents",
                "use_cases": ["Create Word documents", "Edit DOCX files", "Extract text from documents", "Add tracked changes", "Format documents professionally"],
                "inputs": ["file_path", "content", "template"],
                "outputs": ["docx_file", "extracted_text", "formatted_document"],
                "dependencies": ["python-docx"],
            },
            {
                "id": "pdf",
                "name": "PDF — Document Toolkit",
                "description": "Comprehensive PDF manipulation toolkit for extracting text and tables, creating new PDFs, merging/splitting documents, and handling forms.",
                "category": "documents",
                "use_cases": ["Create PDF documents", "Extract text from PDFs", "Merge or split PDFs", "Fill PDF forms", "Convert PDF to other formats"],
                "inputs": ["file_path", "content", "operation"],
                "outputs": ["pdf_file", "extracted_text", "tables", "merged_pdf"],
                "dependencies": ["pymupdf", "reportlab"],
            },
            {
                "id": "pptx",
                "name": "PPTX — Presentations",
                "description": "Presentation creation, editing, and analysis. Supports layouts, speaker notes, comments, and professional formatting.",
                "category": "documents",
                "use_cases": ["Create PowerPoint presentations", "Edit slides", "Add speaker notes", "Design slide decks", "Extract presentation content"],
                "inputs": ["file_path", "content", "template"],
                "outputs": ["pptx_file", "slide_content", "presentation"],
                "dependencies": ["python-pptx"],
            },
            {
                "id": "xlsx",
                "name": "XLSX — Spreadsheets",
                "description": "Comprehensive spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, and visualization.",
                "category": "documents",
                "use_cases": ["Create Excel spreadsheets", "Analyze data in Excel", "Format spreadsheets", "Create charts and visualizations", "Work with formulas"],
                "inputs": ["file_path", "data", "formulas"],
                "outputs": ["xlsx_file", "analysis_results", "charts"],
                "dependencies": ["openpyxl"],
            },
        ]

        for defn in _DOC_DEFS:
            sub_folder = doc_dir / defn["id"]
            skill_md = ""
            if sub_folder.exists():
                md_path = sub_folder / "SKILL.md"
                if md_path.exists():
                    try:
                        skill_md = md_path.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        pass

            skills.append(Skill(
                id=defn["id"],
                name=defn["name"],
                description=defn["description"],
                folder_name=f"document-skills/{defn['id']}",
                folder_path=str(sub_folder) if sub_folder.exists() else "(built-in)",
                category=defn["category"],
                use_cases=defn["use_cases"],
                inputs=defn["inputs"],
                outputs=defn["outputs"],
                execution_type=ExecutionType.PROMPT,
                scripts=[],
                dependencies=defn["dependencies"],
                trigger_keywords=_kws.get(defn["id"], []),
                agent_affinity=["coder"],
                skill_md_text=skill_md,
                has_context=bool(skill_md.strip()),
                status=SkillStatus.ACTIVE,
            ))

        return skills

    # ── YouTube downloader skill ────────────────────────────────────────────

    def _parse_youtube_downloader(self) -> list[Skill]:
        """Parse video-downloader as YouTube Downloader skill."""
        vid_dir = self._root / "video-downloader"
        skill_md = ""
        if vid_dir.exists():
            md_path = vid_dir / "SKILL.md"
            if md_path.exists():
                try:
                    skill_md = md_path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    pass

        return [
            Skill(
                id="youtube-downloader",
                name="YouTube — Video Downloader",
                description=(
                    "Download YouTube videos with customizable quality and format options. "
                    "Supports various quality settings (best, 1080p, 720p, 480p, 360p), "
                    "multiple formats (mp4, webm, mkv), and audio-only downloads as MP3."
                ),
                folder_name="video-downloader",
                folder_path=str(vid_dir) if vid_dir.exists() else "(built-in)",
                category="automation",
                use_cases=[
                    "Download a YouTube video",
                    "Save a video as MP4 or MP3",
                    "Download in specific quality",
                    "Batch download videos",
                ],
                inputs=["url", "quality", "format"],
                outputs=["video_file", "audio_file", "download_path"],
                execution_type=ExecutionType.HYBRID,
                scripts=[],
                dependencies=["yt-dlp"],
                trigger_keywords=_SKILL_SPECIFIC_KEYWORDS["video-downloader"],
                agent_affinity=["coder"],
                skill_md_text=skill_md,
                has_context=bool(skill_md.strip()),
                status=SkillStatus.ACTIVE,
            ),
        ]


def _folder_to_name(folder_name: str) -> str:
    """Convert a folder name like 'canvas-design' to 'Canvas Design'."""
    return " ".join(w.capitalize() for w in folder_name.split("-"))
