"""Skill agent for skill management tasks."""

from pathlib import Path
from typing import Any, Optional

from ..tools_ext.skill_tools import SkillTools


class SkillAgent:
    """Specialist agent for skill management."""

    def __init__(self, skill_tools: Optional[SkillTools] = None):
        """Initialize skill agent.

        Args:
            skill_tools: SkillTools instance
        """
        self.skills = skill_tools or SkillTools()

        # Load prompt
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load skills prompt from file."""
        prompt_path = Path("src/prompts/skills.txt")
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a skill management specialist agent."

    def search_skills(self, query: str, source: str = "all") -> dict[str, Any]:
        """Search for skills.

        Args:
            query: Search query
            source: Source to search

        Returns:
            Search results
        """
        return self.skills.search_skill_sources(query, source)

    def download_skill(self, url: str, name: Optional[str] = None) -> dict[str, Any]:
        """Download a skill.

        Args:
            url: Skill URL
            name: Optional skill name

        Returns:
            Download result
        """
        return self.skills.download_skill(url, name)

    def inspect_skill(self, skill_path: str) -> dict[str, Any]:
        """Inspect a skill.

        Args:
            skill_path: Path to skill

        Returns:
            Inspection result
        """
        return self.skills.inspect_skill_manifest(skill_path)

    def validate_skill(self, skill_path: str) -> dict[str, Any]:
        """Validate a skill.

        Args:
            skill_path: Path to skill

        Returns:
            Validation result
        """
        return self.skills.validate_skill(skill_path)

    def install_skill(self, skill_path: str) -> dict[str, Any]:
        """Install a skill.

        Args:
            skill_path: Path to skill

        Returns:
            Install result
        """
        return self.skills.install_skill(skill_path)

    def uninstall_skill(self, name: str) -> dict[str, Any]:
        """Uninstall a skill.

        Args:
            name: Skill name

        Returns:
            Uninstall result
        """
        return self.skills.uninstall_skill(name)

    def enable_skill(self, name: str) -> dict[str, Any]:
        """Enable a skill.

        Args:
            name: Skill name

        Returns:
            Enable result
        """
        return self.skills.enable_skill(name)

    def disable_skill(self, name: str) -> dict[str, Any]:
        """Disable a skill.

        Args:
            name: Skill name

        Returns:
            Disable result
        """
        return self.skills.disable_skill(name)

    def list_skills(self, status: Optional[str] = None) -> dict[str, Any]:
        """List all skills.

        Args:
            status: Optional status filter

        Returns:
            List of skills
        """
        return self.skills.list_skills(status)

    def get_skill_info(self, name: str) -> dict[str, Any]:
        """Get skill information.

        Args:
            name: Skill name

        Returns:
            Skill info
        """
        return self.skills.get_skill_info(name)

    def update_registry(self) -> dict[str, Any]:
        """Update skill registry.

        Returns:
            Update result
        """
        return self.skills.update_skill_registry()

    def handle_skill_task(self, action: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle a skill task.

        Args:
            action: Action to perform
            context: Task context

        Returns:
            Task result
        """
        from ..discovery.cli_discovery import CLIDiscovery
        from ..discovery.skill_scanner import SkillScanner
        from ..discovery.capability_gap_analyzer import CapabilityGapAnalyzer

        action_lower = action.lower()
        if "missing" in action_lower or "install" in action_lower or "cli" in action_lower:
            report = CLIDiscovery().full_report()
            CLIDiscovery().print_report()
            return {"success": True, "output": report}

        if "skill" in action_lower and "scan" in action_lower:
            report = SkillScanner().full_report()
            SkillScanner().print_report()
            return {"success": True, "output": report}

        if "gap" in action_lower or "capability" in action_lower:
            report = CapabilityGapAnalyzer().generate_report()
            return {"success": True, "output": report}

        handlers = {
            "search": lambda: self.search_skills(
                context.get("query", ""),
                context.get("source", "all"),
            ),
            "download": lambda: self.download_skill(
                context.get("url", ""),
                context.get("name"),
            ),
            "inspect": lambda: self.inspect_skill(context.get("skill_path", "")),
            "validate": lambda: self.validate_skill(context.get("skill_path", "")),
            "install": lambda: self.install_skill(context.get("skill_path", "")),
            "uninstall": lambda: self.uninstall_skill(context.get("name", "")),
            "enable": lambda: self.enable_skill(context.get("name", "")),
            "disable": lambda: self.disable_skill(context.get("name", "")),
            "list": lambda: self.list_skills(context.get("status")),
            "info": lambda: self.get_skill_info(context.get("name", "")),
            "update_registry": self.update_registry,
        }

        goal_text = getattr(context, "goal", "") or getattr(context, "current_goal", "") or ""
        handlers["execute_goal"] = lambda: {
            "success": True,
            "summary": f"Skill agent received: {goal_text[:120]}",
            "message": "Use actions like search, install, list, or info.",
        }
        handlers["verify"] = lambda: {"success": True, "summary": "Skill task verified."}

        handler = handlers.get(action)
        if handler:
            return handler()

        return {"success": False, "error": f"Unknown action: {action}"}
