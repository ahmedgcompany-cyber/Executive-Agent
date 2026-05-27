"""Social media agent for connecting platforms and posting content."""

from pathlib import Path
from typing import Any, Optional

from ..tools_ext.social_tools import SocialTools, PLATFORMS


class SocialAgent:
    """Specialist agent for social media posting and management."""

    def __init__(self, social_tools: Optional[SocialTools] = None):
        self.social = social_tools or SocialTools()
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        p = Path("src/prompts/social.txt")
        if p.exists():
            return p.read_text(encoding="utf-8")
        return (
            "You are a social media specialist. Post content, read feeds, "
            "and manage connections for LinkedIn, Facebook, Instagram, "
            "Google Business Profile, and TikTok."
        )

    # ── Main entry point for AgentLoop ───────────────────────────────

    def handle_social_task(self, action: str, context) -> dict[str, Any]:
        """Route a social task from the AgentLoop.

        Args:
            action: Action name from the plan
            context: ToolContext with goal, platform, text etc.

        Returns:
            Task result dict
        """
        goal = getattr(context, "goal", "") or getattr(context, "current_goal", "") or ""

        handlers = {
            "post":           lambda: self._post_from_goal(goal),
            "publish":        lambda: self._post_from_goal(goal),
            "share":          lambda: self._post_from_goal(goal),
            "post_to_all":    lambda: self._post_from_goal(goal),
            "get_status":     self._get_status,
            "status":         self._get_status,
            "connect":        lambda: self._guide_connect(goal),
            "disconnect":     lambda: self._disconnect_from_goal(goal),
            "read_posts":     lambda: self._read_posts_from_goal(goal),
            "get_posts":      lambda: self._read_posts_from_goal(goal),
            "execute_goal":   lambda: self._execute_from_goal(goal),
            "execute_task":   lambda: self._execute_from_goal(goal),
            "analyze":        lambda: self._execute_from_goal(goal),
            "create":         lambda: self._post_from_goal(goal),
            "verify":         lambda: self._verify_connections(),
        }

        handler = handlers.get(action)
        if handler:
            return handler()

        # Default: execute from goal
        return self._execute_from_goal(goal)

    # ── Goal-driven execution ─────────────────────────────────────────

    def _execute_from_goal(self, goal: str) -> dict[str, Any]:
        """Parse the goal and determine the right social action."""
        if not goal:
            return {"success": False, "error": "No goal provided to social agent."}

        g = goal.lower()

        if any(x in g for x in ["connect", "link", "authoris", "authoriz", "login", "log in"]):
            return self._guide_connect(goal)
        elif any(x in g for x in ["read", "show", "get", "fetch", "my posts", "recent"]):
            return self._read_posts_from_goal(goal)
        elif any(x in g for x in ["disconnect", "unlink", "remove account"]):
            return self._disconnect_from_goal(goal)
        elif any(x in g for x in ["status", "connected", "accounts"]):
            return self._get_status()
        else:
            # Default: post content
            return self._post_from_goal(goal)

    def _post_from_goal(self, goal: str) -> dict[str, Any]:
        """Extract post text and target platforms from goal, then post."""
        import re

        # Extract target platforms
        target_platforms = []
        for pid, pinfo in PLATFORMS.items():
            pname = pinfo["name"].lower().split()[0]
            if pname in goal.lower() or pid in goal.lower():
                target_platforms.append(pid)

        # Extract post text
        quoted = re.findall(r'"([^"]{4,500})"', goal)
        post_text = quoted[0] if quoted else ""

        if not post_text:
            m = re.search(
                r'(?:post|write|share|publish|say|caption|about|content)\s+["\']?(.{10,500}?)["\']?'
                r'(?:$|on\s|to\s|for\s)',
                goal, re.IGNORECASE
            )
            post_text = m.group(1).strip() if m else goal

        if not post_text or len(post_text) < 5:
            post_text = goal

        # Try to get connected platforms
        connected = [p for p in PLATFORMS if self.social.is_connected(p)]
        if not connected:
            return {
                "success": False,
                "error": "No social media accounts connected.",
                "summary": (
                    "No social media accounts are connected yet.\n\n"
                    "To connect:\n"
                    "  1. Click the 'Social Accounts' tab in the app\n"
                    "  2. Click 'Connect' next to the platform you want\n"
                    "  3. Complete the login in your browser\n\n"
                    "Once connected, I can post, read, and manage your accounts."
                ),
            }

        if not target_platforms:
            target_platforms = connected

        result = self.social.post_to_all(post_text, platforms=target_platforms)
        return result

    def _get_status(self) -> dict[str, Any]:
        """Return a readable summary of connected accounts."""
        status = self.social.get_connection_status()
        lines = ["Social Media Accounts Status:\n"]
        for pid, info in status.items():
            icon = "✓ Connected" if info["connected"] else "  Not connected"
            name_part = f" ({info['account_name']})" if info["account_name"] else ""
            lines.append(f"  {icon}  {info['platform_name']}{name_part}")

        connected_count = sum(1 for v in status.values() if v["connected"])
        lines.append(f"\n{connected_count} of {len(PLATFORMS)} platforms connected.")

        if connected_count == 0:
            lines.append(
                "\nTo connect a platform, open the Social Accounts tab\n"
                "and click Connect next to the platform."
            )

        return {
            "success": True,
            "summary": "\n".join(lines),
            "status": status,
            "connected_count": connected_count,
        }

    def _guide_connect(self, goal: str) -> dict[str, Any]:
        """Guide user to connect a specific platform."""
        import re
        target = None
        for pid, pinfo in PLATFORMS.items():
            if pinfo["name"].lower().split()[0] in goal.lower() or pid in goal.lower():
                target = pinfo["name"]
                break

        platform_str = f"'{target}'" if target else "your social media platforms"
        return {
            "success": True,
            "summary": (
                f"To connect {platform_str}:\n\n"
                "  1. Click the 'Social Accounts' tab (right panel)\n"
                "  2. Find the platform and click 'Connect'\n"
                "  3. Enter your App Client ID and Secret (from the developer portal)\n"
                "  4. Complete the login in your browser\n\n"
                "If you already have an access token, click 'Use Token' to paste it directly.\n\n"
                "Need help getting API credentials?\n"
                "  - LinkedIn: developers.linkedin.com/apps\n"
                "  - Facebook/Instagram: developers.facebook.com\n"
                "  - Google Business: console.cloud.google.com\n"
                "  - TikTok: developers.tiktok.com"
            ),
        }

    def _disconnect_from_goal(self, goal: str) -> dict[str, Any]:
        """Disconnect a platform mentioned in the goal."""
        for pid, pinfo in PLATFORMS.items():
            if pinfo["name"].lower().split()[0] in goal.lower() or pid in goal.lower():
                return self.social.disconnect(pid)
        return {
            "success": False,
            "error": "Please specify which platform to disconnect (e.g. 'disconnect LinkedIn')",
        }

    def _verify_connections(self) -> dict[str, Any]:
        """Verify that social connections actually exist."""
        connected = [p for p in PLATFORMS if self.social.is_connected(p)]
        if connected:
            names = ", ".join(PLATFORMS[p]["name"] for p in connected)
            return {"success": True, "summary": f"Social accounts verified: {names}"}
        return {"success": False, "error": "No social media accounts connected."}

    def _read_posts_from_goal(self, goal: str) -> dict[str, Any]:
        """Read recent posts from platforms mentioned in the goal."""
        target = None
        for pid, pinfo in PLATFORMS.items():
            if pinfo["name"].lower().split()[0] in goal.lower() or pid in goal.lower():
                target = pid
                break

        if not target:
            connected = [p for p in PLATFORMS if self.social.is_connected(p)]
            target = connected[0] if connected else None

        if not target:
            return {"success": False, "error": "No connected platform to read from."}

        return self.social.get_recent_posts(target)
