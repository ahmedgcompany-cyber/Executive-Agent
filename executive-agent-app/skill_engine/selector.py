"""
Skill Engine — Selector.

Intelligent skill selection logic. Given a user prompt it returns:
  - The single best skill  (best_match)
  - A ranked shortlist     (select_top)
  - Multiple skills        (select_multi)  for compound tasks

Selection pipeline:
  1. Quick keyword scan via SkillRegistry
  2. Intent classification via multi-skill pattern matching
  3. Compound task detection (e.g. "build and package")
  4. Fallback handling when nothing matches
"""

from __future__ import annotations

import re
from typing import Optional

from .registry import SkillRegistry
from .schemas import Skill, SkillMatch


# ---------------------------------------------------------------------------
# Coding / development task patterns — DO NOT intercept these.
# These prompts should go to the coder agent, not a skill.
# ---------------------------------------------------------------------------

_SKIP_PATTERNS: list[re.Pattern] = [
    # General coding tasks
    re.compile(r"\b(write|create|build|make|develop|code|implement)\b.{0,30}\b(script|program|function|class|method|app|application|tool|bot|game|calculator|converter|parser|scraper|server|api|database|algorithm|widget|snippet|module|package|library)\b", re.I),
    # Language-specific coding
    re.compile(r"\b(write|create|build|make)\b.{0,15}\b(python|javascript|typescript|java|c\+\+|rust|go|ruby|html|css|sql|react|node|express|flask|django|fastapi)\b", re.I),
    # Debugging and fixing code
    re.compile(r"\b(fix|debug|solve|troubleshoot|repair|patch)\b.{0,20}\b(bug|error|issue|problem|code|script|program)\b", re.I),
    # Code explanation
    re.compile(r"\b(explain|understand|analyze|review|refactor)\b.{0,20}\b(code|function|class|method|script|program|algorithm)\b", re.I),
    # Data/file manipulation
    re.compile(r"\b(parse|convert|process|extract|transform|generate)\b.{0,20}\b(data|file|csv|json|xml|excel|text|report)\b", re.I),
    # Automation scripts
    re.compile(r"\b(automate|batch|schedule)\b.{0,20}\b(task|process|workflow|script|job)\b", re.I),
    # Web development
    re.compile(r"\b(build|create|make|design)\b.{0,20}\b(website|web.?app|webpage|landing.?page|frontend|backend|full.?stack|rest.?api|http)\b.{0,30}\b(with|using|in|from)\b", re.I),
]

# ---------------------------------------------------------------------------
# Compound task patterns
# ---------------------------------------------------------------------------
# Each entry: (compiled regex that fires on the prompt, [skill_ids to chain])

_MULTI_SKILL_PATTERNS: list[tuple[re.Pattern, list[str]]] = [
    # UI + packaging
    (re.compile(r"(build|create|make).*(dashboard|ui|app|interface).*(package|deploy|bundle|ship)", re.I),
     ["canvas-design", "artifacts-builder"]),
    (re.compile(r"(design|create).*(ui|interface|frontend).*(package|bundle|html)", re.I),
     ["artifacts-builder", "theme-factory"]),

    # Content + branding
    (re.compile(r"(write|create|draft).*(article|blog|post).*(brand|style|theme)", re.I),
     ["content-research-writer", "brand-guidelines"]),
    (re.compile(r"(design|create).*(poster|banner|flyer).*(brand|style)", re.I),
     ["canvas-design", "brand-guidelines"]),

    # Resume + cover letter
    (re.compile(r"(resume|cv).*(cover letter|apply|application)", re.I),
     ["tailored-resume-generator"]),

    # Lead research + outreach
    (re.compile(r"(find|research).*(lead|prospect|customer).*(email|outreach|contact)", re.I),
     ["lead-research-assistant"]),

    # Competitor analysis + strategy
    (re.compile(r"(competitor|rival).*(ads?|marketing|campaign|strategy)", re.I),
     ["competitive-ads-extractor", "lead-research-assistant"]),

    # Design + apply theme
    (re.compile(r"(build|create|design).*(presentation|slide|deck|report)", re.I),
     ["canvas-design", "theme-factory"]),

    # MCP + testing
    (re.compile(r"(build|create).*(mcp|claude plugin|tool server).*(test|verify)", re.I),
     ["mcp-builder", "webapp-testing"]),

    # App + test
    (re.compile(r"(build|create|make).*(app|application|website).*(test|verify|check)", re.I),
     ["artifacts-builder", "webapp-testing"]),

    # Email + CRM cross-system
    (re.compile(r"(check|read).*(email|inbox).*(reply|respond|answer)", re.I),
     ["email-reader", "email-reply"]),
    (re.compile(r"(check|read).*(email|inbox).*(important|urgent|priority)", re.I),
     ["smart-inbox-sorter", "email-reply"]),
    (re.compile(r"(email|inbox).*(recruiter|hiring|job)", re.I),
     ["smart-inbox-sorter", "recruiter-reply-drafter"]),
    (re.compile(r"(follow.?up|followup).*(lead|contact|recruiter|client)", re.I),
     ["crm-followup-manager", "email-reply"]),

    # Email + GitHub cross-system
    (re.compile(r"(create|build).*(repo|github).*(email|send).*(link|url|client)", re.I),
     ["github-repo-creator", "email-sender"]),

    # Email + Social cross-system
    (re.compile(r"(email|inbox).*(linkedin|social|post|update)", re.I),
     ["email-reader", "content-research-writer"]),

    # NEXUS + Engineering: "build and test" compound
    (re.compile(r"(build|create|develop).*(app|website|api|backend|frontend).*(test|verify|qa|quality)", re.I),
     ["nexus-sprint", "agency-engineering", "agency-testing"]),

    # NEXUS + Marketing: "launch product and run campaign"
    (re.compile(r"(launch|ship|release).*(product|app|feature).*(campaign|market|promote|announce)", re.I),
     ["nexus-sprint", "agency-marketing"]),

    # Marketing + Social multi-platform campaign
    (re.compile(r"(marketing|content).*(campaign|strategy).*(tiktok|instagram|linkedin|twitter|social)", re.I),
     ["agency-marketing", "content-research-writer"]),

    # Sales + CRM compound
    (re.compile(r"(sales|outbound|lead).*(strateg|pipeline|crm|follow.?up).*(email|outreach|contact)", re.I),
     ["agency-sales", "crm-followup-manager", "email-sender"]),

    # Design + Engineering: design then build
    (re.compile(r"(design|wireframe|mockup).*(then|and).*(build|develop|implement|code)", re.I),
     ["agency-design", "agency-engineering"]),

    # Project management + Build: plan then execute
    (re.compile(r"(plan|roadmap|sprint|backlog).*(then|and).*(build|develop|implement)", re.I),
     ["agency-project-management", "nexus-sprint"]),

    # Finance + Strategy
    (re.compile(r"(financial|budget|revenue|investment).*(plan|strategy|forecast|analysis)", re.I),
     ["agency-finance", "agency-product"]),

    # Full NEXUS: discovery through launch
    (re.compile(r"(discover|research).*(design|architect).*(build|develop).*(launch|deploy)", re.I),
     ["nexus-orchestrator"]),

    # Superpowers workflow patterns
    (re.compile(r"(brainstorm|ideate).*(plan|strategy|approach)", re.I),
     ["brainstorming", "writing-plans"]),
    (re.compile(r"(plan|spec|design).*(implement|build|execute|code)", re.I),
     ["writing-plans", "executing-plans"]),
    (re.compile(r"(implement|code|build).*(verify|test|check|done)", re.I),
     ["executing-plans", "verification-before-completion"]),
    (re.compile(r"(debug|fix|investigate).*(root cause|systematic)", re.I),
     ["systematic-debugging"]),
    (re.compile(r"(review|check).*(before|prior to).*(merge|land|ship)", re.I),
     ["requesting-code-review"]),
    # GStack patterns
    (re.compile(r"(test|qa|check).*(website|app|site|deployment)", re.I),
     ["gstack-qa"]),
    (re.compile(r"(browse|open|visit).*(site|page|url|website)", re.I),
     ["gstack-browse"]),
    (re.compile(r"(review|check).*(pr|pull request|code)", re.I),
     ["gstack-review"]),
    # Design patterns
    (re.compile(r"(design|create|build).*(frontend|interface|ui|component)", re.I),
     ["frontend-design"]),
    # Research patterns
    (re.compile(r"(research|search|find|look up).*(web|online|internet)", re.I),
     ["tavily-search"]),
    (re.compile(r"(library|sdk|api|framework).*(docs|documentation|reference)", re.I),
     ["context7-mcp"]),
]

# ---------------------------------------------------------------------------
# Intent → single skill mappings  (fast-path overrides)
# ---------------------------------------------------------------------------

_INTENT_OVERRIDES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(resume|cv)\b", re.I),                          "tailored-resume-generator"),
    (re.compile(r"\bgif\b.*anim|animated.*(gif|image)", re.I),      "slack-gif-creator"),
    (re.compile(r"\b(tweet|twitter|x\.com post)\b", re.I),          "twitter-algorithm-optimizer"),
    (re.compile(r"\b(changelog|release notes|what.?s new)\b", re.I),"changelog-generator"),
    (re.compile(r"\b(raffle|winner|giveaway|lottery)\b", re.I),     "raffle-winner-picker"),
    (re.compile(r"\b(mcp server|model context protocol)\b", re.I),  "mcp-builder"),
    (re.compile(r"\b(langsmith|langchain debug|langgraph trace)\b", re.I), "langsmith-fetch"),
    (re.compile(r"\b(download.*video|youtube.*download|yt-dlp|save.*youtube)\b", re.I), "youtube-downloader"),
    (re.compile(r"\b(organize.*(file|folder)|clean.*(download|desktop))\b", re.I), "file-organizer"),
    (re.compile(r"\b(invoice|receipt|expense)\b", re.I),            "invoice-organizer"),
    (re.compile(r"\b(enhance|upscale).*(image|photo)\b", re.I),     "image-enhancer"),
    (re.compile(r"\b(meeting|transcript).*(analy|insight|summary)\b", re.I), "meeting-insights-analyzer"),
    (re.compile(r"\b(internal.comm|team.update|newsletter|stakeholder.update)\b", re.I), "internal-comms"),
    (re.compile(r"\b(domain.name|check domain|website name)\b", re.I), "domain-name-brainstormer"),
    (re.compile(r"\b(shadcn|vite|artifacts.builder|react.artifact)\b", re.I), "artifacts-builder"),
    (re.compile(r"\b(word doc|docx|ooxml|office doc|create doc|edit doc)\b", re.I),     "docx"),
    (re.compile(r"\b(create pdf|edit pdf|merge pdf|split pdf|fill pdf|pdf form|pymupdf)\b", re.I),     "pdf"),
    (re.compile(r"\b(pptx|powerpoint|slide deck|presentation)\b", re.I),     "pptx"),
    (re.compile(r"\b(xlsx|spreadsheet|excel file|create excel|openpyxl)\b", re.I),     "xlsx"),
    (re.compile(r"\b(composio|third.party api)\b", re.I),           "composio-skills"),
    # GitHub built-in skills
    (re.compile(r"\b(create|new|make|init(ialize)?)\b.{0,20}\b(repo|repository|github.repo)\b", re.I), "github-repo-creator"),
    (re.compile(r"\b(github.issue|create.issue|open.issue|close.issue|list.issues|bug.report)\b", re.I), "github-issue-manager"),
    (re.compile(r"\b(push.to.github|commit.and.push|upload.to.github|push.files|github.commit|sync.to.github)\b", re.I), "github-commit-pusher"),
    # Email built-in skills
    (re.compile(r"\b(check|read|get|show|fetch|list|summarize?)\b.{0,20}\b(email|inbox|mail|messages?)\b", re.I), "email-reader"),
    (re.compile(r"\b(send|compose|write|draft)\b.{0,20}\b(email|mail|message)\b", re.I), "email-sender"),
    (re.compile(r"\b(reply|respond)\b.{0,25}\b(email|mail|message|recruiter|client)\b", re.I), "email-reply"),
    (re.compile(r"\b(sort|classify|organize|prioritize?|filter)\b.{0,15}\b(inbox|emails?)\b", re.I), "smart-inbox-sorter"),
    (re.compile(r"\b(follow.?up|followup|crm|lead.track|pipeline|contact.manag)\b", re.I), "crm-followup-manager"),
    (re.compile(r"\b(reply|respond|draft).{0,20}\b(recruiter|hiring|job.offer|interview)\b", re.I), "recruiter-reply-drafter"),
    # NEXUS pipeline skills — highest priority (before agency categories)
    (re.compile(r"\bnexus.?full\b|full.?product.?(build|lifecycle|pipeline)\b", re.I), "nexus-orchestrator"),
    (re.compile(r"\bnexus.?sprint\b|build.{0,20}(mvp|prototype|feature app|landing page)\b", re.I), "nexus-sprint"),
    (re.compile(r"\bnexus.?micro\b|nexus.?pipeline\b|\borchestrat.{0,20}agent\b|\bmulti.?agent.?task\b", re.I), "nexus-micro"),
    # Agency category overrides
    (re.compile(r"\b(backend architect|design.*backend|architect.*system|microservice|api.?design)\b", re.I), "agency-engineering"),
    (re.compile(r"\b(ux.?research|brand.?identity|ui.?design|design.?system|wireframe)\b", re.I), "agency-design"),
    (re.compile(r"\b(growth.?hack|seo.?strategy|tiktok.?strateg|instagram.?strateg|linkedin.?content|app.?store.?optim)\b", re.I), "agency-marketing"),
    (re.compile(r"\b(sales.?strateg|deal.?review|outbound.?campaign|sales.?proposal|sales.?coach)\b", re.I), "agency-sales"),
    (re.compile(r"\b(qa.?test|performance.?benchmark|accessibility.?audit|evidence.?collect|reality.?check)\b", re.I), "agency-testing"),
    (re.compile(r"\b(sprint.?plan|project.?shepherd|jira.?workflow|studio.?produc|experiment.?track)\b", re.I), "agency-project-management"),
    (re.compile(r"\b(product.?feedback|trend.?research|sprint.?prioriti|behavioral.?nudge)\b", re.I), "agency-product"),
    (re.compile(r"\b(workflow.?architect|mcp.?builder|legal.?review|compliance.?audit|hr.?onboard)\b", re.I), "agency-specialized"),
    (re.compile(r"\b(financial.?analy|tax.?strateg|investment.?research|bookkeep|fp.?a.?anal)\b", re.I), "agency-finance"),
    (re.compile(r"\b(support.?ticket|infrastructure.?maint|analytics.?report|executive.?summary.?gen)\b", re.I), "agency-support"),
]


class SkillSelector:
    """Selects the best skill(s) for a user prompt."""

    # Minimum score to accept a keyword-matched result
    MIN_SCORE = 2.0
    # Confidence threshold to avoid triggering a skill for borderline queries
    INTERCEPT_THRESHOLD = 3.5

    def __init__(self, registry: SkillRegistry):
        self._registry = registry

    # ------------------------------------------------------------------
    # Primary public API
    # ------------------------------------------------------------------

    def best_match(self, prompt: str, agent_hint: Optional[str] = None) -> Optional[SkillMatch]:
        """Return the single best skill for a prompt (or None)."""
        results = self._run_selection(prompt, agent_hint, max_skills=1)
        return results[0] if results else None

    def select_top(self, prompt: str, n: int = 3,
                   agent_hint: Optional[str] = None) -> list[SkillMatch]:
        """Return up to n best matching skills."""
        return self._run_selection(prompt, agent_hint, max_skills=n)

    def select_multi(self, prompt: str,
                     agent_hint: Optional[str] = None) -> list[SkillMatch]:
        """Detect and return multiple skills for compound tasks."""
        return self._run_selection(prompt, agent_hint, max_skills=5, allow_chain=True)

    def should_intercept(self, prompt: str, agent_hint: Optional[str] = None) -> bool:
        """Return True if a skill should handle this prompt.

        Checks: skip patterns → compound patterns → single-skill confidence.
        """
        # Coding/development tasks must go to the agent system, not skills
        if self._is_coding_task(prompt):
            return False
        # Multi-skill compound match always qualifies
        if self._check_multi_patterns(prompt):
            return True
        # Single skill above confidence threshold
        match = self.best_match(prompt, agent_hint)
        return match is not None and match.score >= self.INTERCEPT_THRESHOLD

    # ------------------------------------------------------------------
    # Core selection logic
    # ------------------------------------------------------------------

    def _run_selection(
        self,
        prompt: str,
        agent_hint: Optional[str],
        max_skills: int,
        allow_chain: bool = False,
    ) -> list[SkillMatch]:
        """Full selection pipeline."""

        # ── Step 0: Skip coding/development tasks ────────────────────────
        if self._is_coding_task(prompt):
            return []

        # ── Step 1: Fast-path intent overrides ─────────────────────────
        override_id = self._check_intent_overrides(prompt)
        if override_id:
            skill = self._registry.get_by_id(override_id)
            if skill:
                return [SkillMatch(
                    skill=skill,
                    score=9.0,
                    reason="intent_override",
                    matched=[override_id],
                )]

        # ── Step 2: Multi-skill compound detection ──────────────────────
        if allow_chain or max_skills > 1:
            chain = self._check_multi_patterns(prompt)
            if chain:
                return chain

        # ── Step 3: Keyword scoring via registry ────────────────────────
        candidates = self._registry._score_all(prompt)
        if not candidates:
            return []

        results: list[SkillMatch] = []
        for skill, score in candidates[:max_skills]:
            if score < self.MIN_SCORE:
                continue
            # Agent affinity boost
            boosted = score
            if agent_hint and agent_hint in skill.agent_affinity:
                boosted *= 1.25
            matched_kws = self._find_matched_keywords(skill, prompt)
            results.append(SkillMatch(
                skill=skill,
                score=round(boosted, 3),
                reason="keyword_score",
                matched=matched_kws,
            ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:max_skills]

    # ------------------------------------------------------------------
    # Intent override
    # ------------------------------------------------------------------

    def _check_intent_overrides(self, prompt: str) -> Optional[str]:
        for pattern, skill_id in _INTENT_OVERRIDES:
            if pattern.search(prompt):
                if self._registry.get_by_id(skill_id):
                    return skill_id
        return None

    # ------------------------------------------------------------------
    # Coding task detection
    # ------------------------------------------------------------------

    def _is_coding_task(self, prompt: str) -> bool:
        """Return True if this prompt is a coding/development task that
        should be handled by the agent system, not a skill."""
        for pattern in _SKIP_PATTERNS:
            if pattern.search(prompt):
                return True
        return False

    # ------------------------------------------------------------------
    # Multi-skill compound detection
    # ------------------------------------------------------------------

    def _check_multi_patterns(self, prompt: str) -> list[SkillMatch]:
        for pattern, skill_ids in _MULTI_SKILL_PATTERNS:
            if pattern.search(prompt):
                matches: list[SkillMatch] = []
                for sid in skill_ids:
                    skill = self._registry.get_by_id(sid)
                    if skill:
                        matches.append(SkillMatch(
                            skill=skill,
                            score=7.0,
                            reason="compound_pattern",
                            matched=[sid],
                        ))
                if matches:
                    return matches
        return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_matched_keywords(self, skill: Skill, prompt: str) -> list[str]:
        q = prompt.lower()
        return [kw for kw in skill.trigger_keywords if kw.lower() in q][:5]
