"""Command-line interface for MegaV."""

import argparse
import sys
from pathlib import Path

from .memory.profile_store import ProfileStore


def print_banner():
    """Print the CLI banner."""
    banner = """
--------------------------------------------------------------
                MegaV CLI v1.0.0                   
--------------------------------------------------------------
    """
    try:
        print(banner)
    except UnicodeEncodeError:
        print("MegaV CLI v1.0.0")


def print_status(profile_store: ProfileStore):
    """Print current status.

    Args:
        profile_store: Profile store instance
    """
    print(f"\n{'─' * 60}")
    print(f"  Profile: {profile_store.get_profile_value('name', 'Not loaded')}")
    print(f"  Location: {profile_store.get_profile_value('location', 'Unknown')}")
    print(f"  Email: {profile_store.get_primary_email() or 'Not set'}")
    print(f"{'─' * 60}\n")


def process_command(command: str, profile_store: ProfileStore, runtime: dict = None) -> bool:
    """Process a CLI command.

    Args:
        command: User command
        profile_store: Profile store instance

    Returns:
        True to continue, False to exit
    """
    command = command.strip()

    if not command:
        return True

    # Exit commands
    if command.lower() in ["exit", "quit", "/exit", "/quit"]:
        print("Goodbye!")
        return False

    # Help
    if command.lower() in ["help", "/help", "?"]:
        print_help()
        return True

    # Status
    if command.lower() in ["status", "/status"]:
        print_status(profile_store)
        return True

    # Profile commands
    if command.lower().startswith("/profile"):
        parts = command.split(maxsplit=1)
        if len(parts) > 1:
            print(f"Profile field: {parts[1]} = {profile_store.get_profile_value(parts[1], 'Not set')}")
        else:
            print("Usage: /profile <field_name>")
        return True

    # Agent commands
    if command.lower().startswith("/agent "):
        parts = command.split(maxsplit=2)
        if len(parts) >= 2:
            agent = parts[1]
            goal = parts[2] if len(parts) > 2 else ""
            print(f"Routing to {agent} agent: {goal}")
            print(f"  [This would execute via the {agent} agent]")
        else:
            print("Usage: /agent <agent_name> <goal>")
        return True

    # Browser commands
    if command.lower().startswith("/browse "):
        url = command[8:].strip()
        print(f"Opening browser: {url}")
        print("  [This would open the browser agent]")
        return True

    # Desktop commands
    if command.lower().startswith("/app "):
        app_name = command[5:].strip()
        print(f"Launching application: {app_name}")
        print("  [This would open the desktop agent]")
        return True

    # Workflow commands
    if command.lower().startswith("/workflow "):
        workflow_name = command[10:].strip()
        print(f"Running workflow: {workflow_name}")
        print("  [This would execute the workflow]")
        return True

    # Skill commands
    if command.lower().startswith("/skill "):
        skill_name = command[7:].strip()
        print(f"Using skill: {skill_name}")
        print("  [This would execute the skill]")
        return True

    # Default: treat as goal for commander
    if runtime:
        import asyncio
        from src.tool_system.agent_loop import AgentLoop
        loop = AgentLoop(runtime=runtime, progress_cb=lambda msg: print(f"  ↳ {msg}"))
        try:
            result = asyncio.run(loop.run(command))
            output = result.get("summary") or result.get("output") or str(result)
            print(f"\n✓ {output}\n")
        except Exception as e:
            print(f"\n✗ Error: {e}\n")
    else:
        print(f"Processing goal: {command}")
        print("  [Runtime not available — commander agent offline]")
    return True


def print_help():
    """Print help information."""
    help_text = """
Available Commands:
  help, /help          Show this help message
  status, /status      Show current status
  exit, quit           Exit the CLI

Profile Commands:
  /profile <field>     Get a profile field value

Agent Commands:
  /agent <name> <goal> Route goal to specific agent
                       Agents: coder, browser, desktop, job, sales, content

Tool Commands:
  /browse <url>        Open URL in browser
  /app <name>          Launch desktop application
  /workflow <name>     Run a saved workflow
  /skill <name>        Use an installed skill

Any other text will be treated as a goal and routed to the commander agent.
    """
    print(help_text)


def main(runtime: dict = None):
    """Main CLI entry point."""
    print_banner()

    # Initialize profile store
    profile_store = ProfileStore("profiles")

    # Print status
    print_status(profile_store)

    print("Type 'help' for available commands or enter a goal to get started.\n")

    # Main loop
    while True:
        try:
            # Get input
            command = input(">>> ").strip()

            # Process command
            if not process_command(command, profile_store, runtime):
                break

        except KeyboardInterrupt:
            print("\nUse 'exit' to quit.")
        except EOFError:
            print("\nGoodbye!")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
