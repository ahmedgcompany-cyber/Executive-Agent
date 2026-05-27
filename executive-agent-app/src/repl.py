"""Interactive REPL for MegaV."""

import sys
from pathlib import Path

# Try to import prompt_toolkit for enhanced REPL
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

from .memory.profile_store import ProfileStore


class ExecutiveREPL:
    """Interactive REPL for MegaV."""

    def __init__(self, runtime: dict = None):
        """Initialize the REPL."""
        self.runtime = runtime
        self.profile_store = ProfileStore("profiles")
        self.history_file = Path.home() / ".executive-agent" / "history"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Commands for auto-completion
        self.commands = [
            "help", "exit", "quit", "status",
            "/profile", "/agent", "/browse", "/app",
            "/workflow", "/skill", "/memory",
        ]

        self.session = None
        if PROMPT_TOOLKIT_AVAILABLE:
            self._setup_prompt_toolkit()

    def _setup_prompt_toolkit(self):
        """Set up prompt_toolkit session."""
        completer = WordCompleter(self.commands, ignore_case=True)

        bindings = KeyBindings()

        @bindings.add("c-c")
        def _(event):
            """Handle Ctrl+C."""
            event.app.exit(exception=KeyboardInterrupt)

        self.session = PromptSession(
            history=FileHistory(str(self.history_file)),
            completer=completer,
            key_bindings=bindings,
        )

    def print_banner(self):
        """Print the REPL banner."""
        banner = """
╔══════════════════════════════════════════════════════════════╗
║           MegaV Interactive REPL v1.0.0           ║
╚══════════════════════════════════════════════════════════════╝

Type 'help' for commands or enter a goal to begin.
        """
        print(banner)

    def get_prompt(self) -> str:
        """Get the prompt string.

        Returns:
            Prompt string
        """
        return ">>> "

    def get_input(self) -> str:
        """Get user input.

        Returns:
            User input
        """
        if PROMPT_TOOLKIT_AVAILABLE and self.session:
            return self.session.prompt(self.get_prompt())
        else:
            return input(self.get_prompt())

    def handle_command(self, command: str) -> bool:
        """Handle a REPL command.

        Args:
            command: User command

        Returns:
            True to continue, False to exit
        """
        command = command.strip()

        if not command:
            return True

        # Exit commands
        if command.lower() in ["exit", "quit"]:
            print("Goodbye!")
            return False

        # Help
        if command.lower() in ["help", "?"]:
            self.print_help()
            return True

        # Status
        if command.lower() == "status":
            self.print_status()
            return True

        # Profile
        if command.lower().startswith("/profile"):
            self.handle_profile_command(command)
            return True

        # Agent
        if command.lower().startswith("/agent"):
            self.handle_agent_command(command)
            return True

        # Browser
        if command.lower().startswith("/browse"):
            self.handle_browse_command(command)
            return True

        # Desktop
        if command.lower().startswith("/app"):
            self.handle_app_command(command)
            return True

        # Workflow
        if command.lower().startswith("/workflow"):
            self.handle_workflow_command(command)
            return True

        # Skill
        if command.lower().startswith("/skill"):
            self.handle_skill_command(command)
            return True

        # Default: treat as goal
        self.handle_goal(command)
        return True

    def print_help(self):
        """Print help text."""
        help_text = """
Commands:
  help              Show this help
  status            Show current status
  exit, quit        Exit the REPL

Slash Commands:
  /profile <field>  Get profile field
  /agent <name>     Route to agent (coder, browser, desktop, job, sales, content)
  /browse <url>     Open URL in browser
  /app <name>       Launch application
  /workflow <name>  Run workflow
  /skill <name>     Use skill

Any other input is treated as a goal and routed to the commander agent.
        """
        print(help_text)

    def print_status(self):
        """Print current status."""
        print(f"\nProfile: {self.profile_store.get_profile_value('name', 'Not loaded')}")
        print(f"Email: {self.profile_store.get_primary_email() or 'Not set'}")
        print(f"Location: {self.profile_store.get_profile_value('location', 'Unknown')}\n")

    def handle_profile_command(self, command: str):
        """Handle profile command.

        Args:
            command: Full command string
        """
        parts = command.split(maxsplit=1)
        if len(parts) > 1:
            field = parts[1]
            value = self.profile_store.get_profile_value(field, "Not set")
            print(f"{field}: {value}")
        else:
            print("Usage: /profile <field_name>")

    def handle_agent_command(self, command: str):
        """Handle agent command.

        Args:
            command: Full command string
        """
        parts = command.split(maxsplit=2)
        if len(parts) >= 2:
            agent = parts[1]
            goal = parts[2] if len(parts) > 2 else ""
            print(f"[Routing to {agent} agent: {goal}]")
        else:
            print("Usage: /agent <agent_name> [goal]")

    def handle_browse_command(self, command: str):
        """Handle browse command.

        Args:
            command: Full command string
        """
        parts = command.split(maxsplit=1)
        if len(parts) > 1:
            url = parts[1]
            print(f"[Opening browser: {url}]")
        else:
            print("Usage: /browse <url>")

    def handle_app_command(self, command: str):
        """Handle app command.

        Args:
            command: Full command string
        """
        parts = command.split(maxsplit=1)
        if len(parts) > 1:
            app = parts[1]
            print(f"[Launching: {app}]")
        else:
            print("Usage: /app <application_name>")

    def handle_workflow_command(self, command: str):
        """Handle workflow command.

        Args:
            command: Full command string
        """
        parts = command.split(maxsplit=1)
        if len(parts) > 1:
            workflow = parts[1]
            print(f"[Running workflow: {workflow}]")
        else:
            print("Usage: /workflow <workflow_name>")

    def handle_skill_command(self, command: str):
        """Handle skill command.

        Args:
            command: Full command string
        """
        parts = command.split(maxsplit=1)
        if len(parts) > 1:
            skill = parts[1]
            print(f"[Using skill: {skill}]")
        else:
            print("Usage: /skill <skill_name>")

    def handle_goal(self, goal: str):
        """Execute a goal through the real agent loop."""
        import asyncio
        from src.tool_system.agent_loop import AgentLoop

        loop = AgentLoop(runtime=self.runtime, progress_cb=lambda msg: print(f"  ↳ {msg}"))
        try:
            result = asyncio.run(loop.run(goal))
            output = result.get("summary") or result.get("output") or str(result)
            print(f"\n✓ {output}\n")
        except Exception as e:
            print(f"\n✗ Error: {e}\n")

    def run(self):
        """Run the REPL."""
        self.print_banner()
        self.print_status()

        while True:
            try:
                command = self.get_input()
                if not self.handle_command(command):
                    break
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit.")
            except EOFError:
                print("\nGoodbye!")
                break


def main():
    """Main entry point for REPL."""
    repl = ExecutiveREPL()
    repl.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
