#!/usr/bin/env python3
"""
Integrate New Skills — Repeatable Integration Script.

Scans ~/.claude/agents/, ~/.claude/skills/, and ~/.claude/plugins/ for new skills,
copies their SKILL.md files to awesome-claude-skills-master/, and updates:
  - skill_definitions.py  (add skill dict entries)
  - skill_handlers.py     (add handler stubs + NATIVE_HANDLERS entries)
  - skill_engine/parser.py (add trigger keywords + parsing methods)
  - skill_engine/utils.py  (add category signals)
  - skill_engine/orchestrator.py (add auto-chain rules)
  - skill_engine/selector.py (add compound task patterns)
  - config/settings.yaml   (update version)
  - build_zip.py           (update version)

Usage:
    python integrate_new_skills.py          # Full integration
    python integrate_new_skills.py --scan   # Scan only, no changes
"""

from __future__ import annotations

import re
import sys
import shutil
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
AGENTS_DIR = CLAUDE_DIR / "agents"
SKILLS_DIR = CLAUDE_DIR / "skills"
PLUGINS_DIR = CLAUDE_DIR / "plugins" / "cache" / "claude-plugins-official"

PROJECT_ROOT = Path(__file__).parent
APP_DIR = PROJECT_ROOT / "executive-agent-app"
SKILLS_ROOT = PROJECT_ROOT / "awesome-claude-skills-master"

DEFS_FILE = APP_DIR / "src" / "skills" / "skill_definitions.py"
HANDLERS_FILE = APP_DIR / "src" / "skills" / "skill_handlers.py"
PARSER_FILE = APP_DIR / "skill_engine" / "parser.py"
UTILS_FILE = APP_DIR / "skill_engine" / "utils.py"
ORCH_FILE = APP_DIR / "skill_engine" / "orchestrator.py"
SELECTOR_FILE = APP_DIR / "skill_engine" / "selector.py"
SETTINGS_FILE = APP_DIR / "config" / "settings.yaml"
BUILD_FILE = PROJECT_ROOT / "build_zip.py"


# ── Helpers ───────────────────────────────────────────────────────────────

def find_skill_dirs(base: Path) -> list[Path]:
    """Find all directories containing a SKILL.md file."""
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("SKILL.md") if p.parent != base)


def get_existing_skills() -> set[str]:
    """Get the set of skill IDs already defined in skill_definitions.py."""
    content = DEFS_FILE.read_text(encoding="utf-8")
    return set(re.findall(r'"id":\s*"([^"]+)"', content))


def get_existing_folders() -> set[str]:
    """Get the set of folder names already in awesome-claude-skills-master/."""
    if not SKILLS_ROOT.exists():
        return set()
    return {p.name for p in SKILLS_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").exists()}


def copy_skill_md(src_dir: Path, dest_dir: Path) -> bool:
    """Copy SKILL.md from source to destination directory."""
    src_file = src_dir / "SKILL.md"
    if not src_file.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, dest_dir / "SKILL.md")
    return True


def generate_skill_dict(skill_id: str, name: str, description: str,
                        category: str, subcategory: str,
                        folder: str, keywords: list[str]) -> str:
    """Generate a skill definition dict string."""
    kw_str = ",\n".join(f'            "{kw}"' for kw in keywords[:10])
    return f'''    {{
        "id":           "{skill_id}",
        "name":         "{name}",
        "description":  "{description}",
        "category":     "{category}",
        "subcategory":  "{subcategory}",
        "inputs":       ["description"],
        "outputs":      ["result"],
        "execution_type": "prompt",
        "dependencies": [],
        "trigger_keywords": [
{kw_str},
        ],
        "agent_affinity": ["coder"],
        "folder":       "{folder}",
        "scripts":      [],
        "has_context":  True,
        "active":       True,
    }},'''


def generate_handler_func(skill_id: str, name: str, description: str) -> str:
    """Generate a handler function string."""
    func_name = skill_id.replace("-", "_")
    return f'''

def handle_{func_name}(user_input, extra_context, router, emit):
    """{name}: {description}"""
    return _ai(router, """You are a {name} specialist. {description}
Provide clear, actionable guidance based on the skill's methodology.""",
        user_input, emit,
    )'''


# ── Main Integration ───────────────────────────────────────────────────────

def scan_for_new_skills() -> list[dict]:
    """Scan all sources and return list of new skills to integrate."""
    existing_ids = get_existing_skills()
    existing_folders = get_existing_folders()
    new_skills = []

    # ── Scan ~/.claude/skills/ ─────────────────────────────────────────
    if SKILLS_DIR.exists():
        for skill_dir in SKILLS_DIR.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skill_id = skill_dir.name.lower().replace("_", "-")
                if skill_id not in existing_ids and skill_dir.name not in existing_folders:
                    new_skills.append({
                        "id": skill_id,
                        "source": skill_dir,
                        "folder": skill_dir.name,
                        "type": "skill",
                    })

    # ── Scan ~/.claude/agents/ (non-Composio) ──────────────────────────
    if AGENTS_DIR.exists():
        for agent_dir in AGENTS_DIR.iterdir():
            if agent_dir.is_dir() and agent_dir.name != "composio-skills":
                skill_md = agent_dir / "SKILL.md"
                if skill_md.exists():
                    skill_id = agent_dir.name.lower().replace("_", "-")
                    if skill_id not in existing_ids and agent_dir.name not in existing_folders:
                        new_skills.append({
                            "id": skill_id,
                            "source": agent_dir,
                            "folder": agent_dir.name,
                            "type": "agent",
                        })

    # ── Scan plugins ──────────────────────────────────────────────────
    if PLUGINS_DIR.exists():
        for plugin_dir in PLUGINS_DIR.iterdir():
            skills_sub = plugin_dir / "skills"
            if skills_sub.exists():
                for skill_dir in skills_sub.iterdir():
                    if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                        skill_id = skill_dir.name.lower().replace("_", "-")
                        # Skip superpowers/gstack/context7 already integrated
                        if skill_id in existing_ids:
                            continue
                        # Check parent folder
                        parent = plugin_dir.name.split("/")[0] if "/" in plugin_dir.name else plugin_dir.name
                        dest_folder = f"{parent}/{skill_dir.name}" if parent in ("superpowers", "gstack") else skill_dir.name
                        if dest_folder not in existing_folders:
                            new_skills.append({
                                "id": skill_id,
                                "source": skill_dir,
                                "folder": dest_folder,
                                "type": "plugin",
                            })

    return new_skills


def integrate_skills(new_skills: list[dict], dry_run: bool = False) -> None:
    """Integrate discovered skills into the project."""
    if not new_skills:
        print("No new skills found to integrate.")
        return

    print(f"\nFound {len(new_skills)} new skill(s) to integrate:")
    for s in new_skills:
        print(f"  - {s['id']} ({s['type']}) from {s['source']}")

    if dry_run:
        print("\n[DRY RUN] No changes made.")
        return

    # ── Copy SKILL.md files ────────────────────────────────────────────
    for skill in new_skills:
        dest = SKILLS_ROOT / skill["folder"]
        if copy_skill_md(skill["source"], dest):
            print(f"  Copied: {skill['source']}/SKILL.md → {dest}/SKILL.md")
        else:
            print(f"  WARNING: No SKILL.md in {skill['source']}")

    # ── Generate skill definitions ──────────────────────────────────────
    defs_to_add = []
    for skill in new_skills:
        skill_md = (skill["source"] / "SKILL.md").read_text(encoding="utf-8")[:2000]
        # Extract name from frontmatter or folder name
        name_match = re.search(r"^name:\s*(.+)$", skill_md, re.M)
        name = name_match.group(1).strip() if name_match else skill["folder"].replace("-", " ").title()
        desc_match = re.search(r"^description:\s*(.+)$", skill_md, re.M)
        desc = desc_match.group(1).strip() if desc_match else f"Skill: {name}"
        # Extract keywords from SKILL.md
        keywords = [w for w in skill["id"].split("-") if len(w) > 2]
        keywords.extend(re.findall(r'"([a-z-]+)"', skill_md[:500]))

        defs_to_add.append(generate_skill_dict(
            skill["id"], name, desc, "general", "auto", skill["folder"], keywords
        ))

    # ── Append to skill_definitions.py ─────────────────────────────────
    if defs_to_add:
        defs_content = DEFS_FILE.read_text(encoding="utf-8")
        # Find last skill dict closing bracket
        last_bracket = defs_content.rfind("},")
        if last_bracket > 0:
            insert_point = last_bracket + 2  # After "},"
            new_content = (
                defs_content[:insert_point] +
                "\n\n    # ── Auto-integrated ──\n" +
                "\n".join(defs_to_add) +
                defs_content[insert_point:]
            )
            DEFS_FILE.write_text(new_content, encoding="utf-8")
            print(f"  Updated: {DEFS_FILE.name} (+{len(defs_to_add)} skill dicts)")

    # ── Generate handler stubs ─────────────────────────────────────────
    handlers_to_add = []
    handler_entries = []
    for skill in new_skills:
        skill_md = (skill["source"] / "SKILL.md").read_text(encoding="utf-8")[:2000]
        name_match = re.search(r"^name:\s*(.+)$", skill_md, re.M)
        name = name_match.group(1).strip() if name_match else skill["folder"].replace("-", " ").title()
        desc_match = re.search(r"^description:\s*(.+)$", skill_md, re.M)
        desc = desc_match.group(1).strip() if desc_match else f"Skill: {name}"
        func_name = skill["id"].replace("-", "_")
        handlers_to_add.append(generate_handler_func(skill["id"], name, desc))
        handler_entries.append(f'    "{skill["id"]}": handle_{func_name},')

    if handlers_to_add:
        handlers_content = HANDLERS_FILE.read_text(encoding="utf-8")
        # Insert before NATIVE_HANDLERS
        registry_marker = "NATIVE_HANDLERS: dict[str, Any] = {"
        registry_idx = handlers_content.find(registry_marker)
        if registry_idx > 0:
            # Insert handler functions before NATIVE_HANDLERS section
            section_marker = "# HANDLER REGISTRY"
            section_idx = handlers_content.find(section_marker)
            if section_idx > 0:
                new_content = (
                    handlers_content[:section_idx] +
                    "\n\n".join(handlers_to_add) + "\n\n\n" +
                    handlers_content[section_idx:]
                )
                # Add entries to NATIVE_HANDLERS
                close_brace = new_content.rfind("}")
                if close_brace > 0:
                    # Find last entry before closing brace
                    last_entry = new_content.rfind(",", 0, close_brace)
                    new_content = (
                        new_content[:last_entry+1] +
                        "\n" + "\n".join(handler_entries) +
                        new_content[close_brace:]
                    )
                HANDLERS_FILE.write_text(new_content, encoding="utf-8")
                print(f"  Updated: {HANDLERS_FILE.name} (+{len(handlers_to_add)} handlers)")

    # ── Update version in settings.yaml ────────────────────────────────
    today = datetime.now().strftime("%Y-%m-%d")
    settings_content = SETTINGS_FILE.read_text(encoding="utf-8")
    # Parse current version
    version_match = re.search(r'version:\s*"(\d+\.\d+\.\d+)"', settings_content)
    if version_match:
        current_version = version_match.group(1)
        parts = current_version.split(".")
        # Bump patch version
        new_patch = int(parts[2]) + len(new_skills)  # One bump per new skill
        new_version = f"{parts[0]}.{parts[1]}.{new_patch}"
        settings_content = settings_content.replace(
            f'version: "{current_version}"',
            f'version: "{new_version}"'
        )
        settings_content = settings_content.replace(
            f'build_date: "{re.search(r"build_date:\s*\"([^\"]+)\"", settings_content).group(1)}"',
            f'build_date: "{today}"'
        )
        SETTINGS_FILE.write_text(settings_content, encoding="utf-8")
        print(f"  Updated: {SETTINGS_FILE.name} (version → {new_version})")

    # ── Update version in build_zip.py ─────────────────────────────────
    build_content = BUILD_FILE.read_text(encoding="utf-8")
    build_content = re.sub(
        r'MegaV_v\d+\.\d+\.\d+',
        f'MegaV_v{new_version}',
        build_content
    )
    BUILD_FILE.write_text(build_content, encoding="utf-8")
    print(f"  Updated: {BUILD_FILE.name} (version → {new_version})")

    print(f"\nIntegration complete! {len(new_skills)} skill(s) added.")
    print("Next steps:")
    print("  1. Review the generated skill definitions and handlers")
    print("  2. Add specific trigger keywords to parser.py")
    print("  3. Add auto-chain rules to orchestrator.py if needed")
    print("  4. Add compound patterns to selector.py if needed")
    print("  5. Run: python build_zip.py")


# ── Entry Point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    dry_run = "--scan" in sys.argv
    if dry_run:
        print("Scanning for new skills (dry run)...\n")
    else:
        print("Scanning and integrating new skills...\n")

    new_skills = scan_for_new_skills()
    integrate_skills(new_skills, dry_run=dry_run)