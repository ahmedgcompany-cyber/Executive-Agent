"""
Scans for available skills and MCP servers not yet used by MegaV.
"""

import json
from pathlib import Path


class SkillScanner:

    LOCAL_SKILLS_DIR = Path.home() / ".claude" / "skills"
    CLAUDE_SETTINGS  = Path.home() / ".claude" / "settings.json"

    def scan_local_skills(self) -> list:
        """Find skill .md files in ~/.claude/skills/"""
        if not self.LOCAL_SKILLS_DIR.exists():
            return []
        return [
            {
                "name":    p.stem,
                "path":    str(p),
                "size_kb": round(p.stat().st_size / 1024, 1),
            }
            for p in self.LOCAL_SKILLS_DIR.rglob("*.md")
        ]

    def scan_installed_mcps(self) -> list:
        """Return MCP server names from Claude Code settings."""
        if not self.CLAUDE_SETTINGS.exists():
            return []
        try:
            cfg = json.loads(self.CLAUDE_SETTINGS.read_text(encoding="utf-8"))
            return list(cfg.get("mcpServers", {}).keys())
        except Exception:
            return []

    def full_report(self) -> dict:
        skills = self.scan_local_skills()
        mcps   = self.scan_installed_mcps()
        return {
            "local_skills_count": len(skills),
            "local_skills":       skills,
            "installed_mcps":     mcps,
        }

    def print_report(self) -> None:
        r = self.full_report()
        print(f"\n-- Skill Scanner Report --")
        print(f"Local skills available: {r['local_skills_count']}")
        for s in r["local_skills"][:10]:
            print(f"  - {s['name']} ({s['size_kb']} KB)")
        if len(r["local_skills"]) > 10:
            print(f"  ... and {len(r['local_skills']) - 10} more")
        print(f"\nInstalled MCP servers: {', '.join(r['installed_mcps']) or 'none'}")
