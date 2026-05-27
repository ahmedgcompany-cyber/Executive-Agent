"""
Skill Engine — Utility helpers.

Provides:
  - YAML frontmatter parser (no PyYAML dependency)
  - Keyword extractor from raw text
  - Path resolver
  - Slug normaliser
  - Category classifier
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def find_skills_root() -> Path:
    """Locate the awesome-claude-skills-master folder.

    Checks several candidate locations relative to the app's CWD.
    """
    # CWD when app runs is executive-agent-app/
    candidates = [
        Path("../awesome-claude-skills-master"),
        Path("../../awesome-claude-skills-master"),
        Path("awesome-claude-skills-master"),
        # Absolute fallback: resolve from this file's location
        Path(__file__).parent.parent.parent / "awesome-claude-skills-master",
    ]
    for c in candidates:
        resolved = c.resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved
    # Last resort — return first candidate even if missing (error surfaced later)
    return candidates[0].resolve()


def app_root() -> Path:
    """Return the executive-agent-app/ directory."""
    return Path(__file__).parent.parent.resolve()


# ---------------------------------------------------------------------------
# YAML frontmatter parser  (no third-party deps)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-style frontmatter from a markdown string.

    Returns:
        (metadata_dict, body_text_without_frontmatter)
    """
    meta: dict = {}
    body = text

    # Frontmatter must start at line 0 with ---
    if not text.startswith("---"):
        return meta, body

    end = text.find("\n---", 3)
    if end == -1:
        return meta, body

    fm_block = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")

    for line in fm_block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"').strip("'")

    return meta, body


# ---------------------------------------------------------------------------
# Slug / id normalisation
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert a name/folder to a safe lowercase slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\-_]", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

# Common English stop-words to discard during keyword extraction
_STOP_WORDS = {
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "by","from","up","about","into","through","during","is","are","was","were",
    "be","been","being","have","has","had","do","does","did","will","would",
    "should","may","might","can","could","this","that","these","those","it",
    "its","if","as","so","than","then","not","all","any","each","every",
    "both","few","more","most","other","some","such","no","nor","only",
    "same","too","also","just","how","what","when","where","which","who",
    "your","you","their","they","them","we","us","our","my","i","use",
    "used","using","based","new","create","created","creating","provide",
    "provides","allow","allows","support","supports","generate","generates",
}

def extract_keywords(text: str, max_keywords: int = 20) -> list[str]:
    """Extract meaningful keyword phrases from raw markdown text.

    Returns a de-duplicated list of short phrases (1-3 words).
    """
    # Lower-case, remove markdown syntax
    clean = re.sub(r"[#*`>\[\]\(\)_~\-]+", " ", text.lower())
    clean = re.sub(r"https?://\S+", " ", clean)
    clean = re.sub(r"[^a-z0-9\s]", " ", clean)
    words = [w for w in clean.split() if len(w) > 2 and w not in _STOP_WORDS]

    # Frequency count
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    # Build bi-grams from original word sequence
    bigrams = []
    for i in range(len(words) - 1):
        bg = words[i] + " " + words[i + 1]
        bigrams.append(bg)

    # Score bigrams by combined frequency
    bg_score: dict[str, int] = {}
    for bg in bigrams:
        a, b = bg.split()
        bg_score[bg] = freq.get(a, 0) + freq.get(b, 0)

    # Top bigrams
    top_bigrams = sorted(bg_score.items(), key=lambda x: x[1], reverse=True)[:10]
    top_words   = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:15]

    combined: list[str] = [bg for bg, _ in top_bigrams] + [w for w, _ in top_words]
    seen: set[str] = set()
    result: list[str] = []
    for kw in combined:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
        if len(result) >= max_keywords:
            break

    return result


# ---------------------------------------------------------------------------
# Category classifier
# ---------------------------------------------------------------------------

_CATEGORY_SIGNALS: dict[str, list[str]] = {
    "content":       ["design","visual","art","poster","infographic","canvas",
                      "artifact","frontend","react","html","theme","brand",
                      "gif","animation","changelog","document","pdf"],
    "career":        ["resume","cv","job","career","interview","application",
                      "cover letter","ats","hiring"],
    "business":      ["sales","lead","prospect","competitor","domain","brand name",
                      "startup","marketing","ads","outreach","b2b","twitter","tweet"],
    "automation":    ["file","organize","invoice","receipt","video","download",
                      "image","enhance","upscale","automate","script","batch"],
    "integration":   ["api","composio","slack","github","notion","jira","email",
                      "connect","integrate","webhook","oauth","tavily","context7",
                      "library docs","documentation lookup"],
    "development":   ["mcp","langsmith","langchain","test","debug","webapp",
                      "playwright","skill","code","developer","build",
                      "brainstorm","plan","execute","review","verify","tdd",
                      "worktree","subagent","dispatch","qa","canary","benchmark",
                      "investigate","ship","deploy","health","retro"],
    "superpowers":   ["brainstorm","ideate","creative ideas","brainstorm session",
                      "plan","execute plan","implement plan","debug systematically",
                      "tdd","test driven","code review","verify completion",
                      "git worktree","subagent","dispatch agents","superpowers",
                      "development workflow","writing plans","writing skills"],
    "gstack":        ["browse","qa","canary","review","deploy","benchmark",
                      "checkpoint","freeze","guard","health","investigate",
                      "land and deploy","learn","office hours","pair agent",
                      "plan review","design consultation","design html",
                      "design shotgun","ship","retro","cso","devex review",
                      "document release","gstack","headless browser"],
    "communication": ["write","article","blog","meeting","transcript","newsletter",
                      "internal","communication","content","copywriting"],
    "documents":     ["word","excel","powerpoint","docx","xlsx","ooxml","office"],
    "utility":       ["raffle","winner","random","share","publish","package","zip"],
}

def classify_category(text: str, name: str = "") -> str:
    """Classify a skill into a category based on its description/name text."""
    combined = (text + " " + name).lower()
    scores: dict[str, int] = {cat: 0 for cat in _CATEGORY_SIGNALS}
    for cat, signals in _CATEGORY_SIGNALS.items():
        for sig in signals:
            if sig in combined:
                scores[cat] += 1
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "general"


# ---------------------------------------------------------------------------
# Agent affinity classifier
# ---------------------------------------------------------------------------

_AGENT_SIGNALS: dict[str, list[str]] = {
    "coder":   ["code","script","build","react","html","python","artifact",
                "mcp","langsmith","webapp","test","debug","github","frontend"],
    "content": ["write","design","art","visual","canvas","theme","brand",
                "blog","article","gif","animation","pdf","resume"],
    "browser": ["ads","competitor","domain","lead","composio","api","connect",
                "webapp","playwright","browser","scrape"],
    "desktop": ["file","organize","invoice","video","image","download","batch"],
    "sales":   ["lead","sales","prospect","outreach","b2b","competitor","domain"],
    "job":     ["resume","cv","job","career","cover letter","interview"],
    "memory":  ["growth","analysis","developer","patterns","history"],
}

def classify_agents(text: str) -> list[str]:
    """Return list of agent names that would likely use this skill."""
    combined = text.lower()
    scores: dict[str, int] = {}
    for agent, signals in _AGENT_SIGNALS.items():
        s = sum(1 for sig in signals if sig in combined)
        if s > 0:
            scores[agent] = s
    if not scores:
        return ["coder"]
    # Return agents with score >= max/2
    max_s = max(scores.values())
    return sorted([a for a, s in scores.items() if s >= max(1, max_s // 2)])


# ---------------------------------------------------------------------------
# Section extractor — pull structured sections from SKILL.md body
# ---------------------------------------------------------------------------

def extract_section(body: str, heading_pattern: str) -> str:
    """Extract the content under a markdown heading matching the pattern."""
    pattern = rf"##?\s+{re.escape(heading_pattern)}[^\n]*\n([\s\S]*?)(?=\n##|\Z)"
    m = re.search(pattern, body, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def extract_bullet_list(section_text: str) -> list[str]:
    """Turn a markdown bullet/numbered list section into a Python list."""
    items = []
    for line in section_text.splitlines():
        line = line.strip()
        line = re.sub(r"^[\-\*\•\d]+\.?\s*", "", line).strip()
        line = re.sub(r"\*+", "", line).strip()
        if line and len(line) > 3:
            items.append(line[:120])
    return items
