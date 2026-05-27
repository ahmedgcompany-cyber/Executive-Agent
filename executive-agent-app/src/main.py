"""Main entry point for MegaV."""

import argparse
import asyncio
import sys
from pathlib import Path

from .memory.profile_store import ProfileStore
from .memory.workflow_store import WorkflowStore
from .tools_ext.browser_tools import BrowserTools
from .tools_ext.desktop_tools import DesktopTools
from .tools_ext.vision_tools import VisionTools
from .tools_ext.profile_tools import ProfileTools
from .tools_ext.workflow_tools import WorkflowTools
from .tools_ext.skill_tools import SkillTools
from .tools_ext.app_control_tools import AppControlTools
from .agents.commander_agent import CommanderAgent
from .agents.coder_agent import CoderAgent
from .agents.browser_agent import BrowserAgent
from .agents.desktop_agent import DesktopAgent
from .agents.job_agent import JobAgent
from .agents.sales_agent import SalesAgent
from .agents.content_agent import ContentAgent
from .agents.skill_agent import SkillAgent
from .agents.memory_agent import MemoryAgent
from .agents.social_agent import SocialAgent
from .tools_ext.social_tools import SocialTools
from .tool_system.defaults import ToolRegistry, register_extended_tools
from .tool_system.context import ToolContext


def load_app_config() -> dict:
    """Load application configuration.

    Returns:
        Configuration dictionary
    """
    import yaml

    config_path = Path("config/settings.yaml")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def build_runtime() -> dict:
    """Build the runtime context with all components.

    Returns:
        Runtime context dictionary
    """
    # Initialize memory stores
    profile_store = ProfileStore("profiles")
    workflow_store = WorkflowStore("workflows")

    # Initialize tools
    browser_tools = BrowserTools()
    desktop_tools = DesktopTools()
    vision_tools = VisionTools()
    profile_tools = ProfileTools(profile_store)
    workflow_tools = WorkflowTools(workflow_store)
    skill_tools = SkillTools("skills")
    app_control_tools = AppControlTools(desktop_tools)

    # Initialize agents
    coder_agent = CoderAgent()
    browser_agent = BrowserAgent(browser_tools, profile_store)
    desktop_agent = DesktopAgent(desktop_tools, vision_tools)
    job_agent = JobAgent(profile_store, browser_tools)
    sales_agent = SalesAgent()
    content_agent = ContentAgent(profile_store)
    skill_agent = SkillAgent(skill_tools)
    memory_agent = MemoryAgent(profile_store, workflow_store)
    social_tools = SocialTools()
    social_agent = SocialAgent(social_tools)

    # Initialize commander
    commander = CommanderAgent(
        coder_agent=coder_agent,
        browser_agent=browser_agent,
        desktop_agent=desktop_agent,
        job_agent=job_agent,
        sales_agent=sales_agent,
        content_agent=content_agent,
        skill_agent=skill_agent,
        memory_agent=memory_agent,
        social_agent=social_agent,
    )

    runtime = {
        "profile_store": profile_store,
        "workflow_store": workflow_store,
        "browser_tools": browser_tools,
        "desktop_tools": desktop_tools,
        "vision_tools": vision_tools,
        "profile_tools": profile_tools,
        "workflow_tools": workflow_tools,
        "skill_tools": skill_tools,
        "app_control_tools": app_control_tools,
        "commander": commander,
        "coder_agent": coder_agent,
        "browser_agent": browser_agent,
        "desktop_agent": desktop_agent,
        "job_agent": job_agent,
        "sales_agent": sales_agent,
        "content_agent": content_agent,
        "skill_agent": skill_agent,
        "memory_agent": memory_agent,
        "social_tools": social_tools,
        "social_agent": social_agent,
    }

    # Initialize Context and Registry
    context = ToolContext()
    context.load_profile(profile_store)
    runtime["context"] = context

    registry = ToolRegistry()
    register_extended_tools(registry, runtime)
    runtime["registry"] = registry

    # Initialize Skill Engine (new production system)
    try:
        import sys as _sys
        import os as _os
        # Ensure skill_engine package is importable (it lives in executive-agent-app/)
        _app_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        if _app_root not in _sys.path:
            _sys.path.insert(0, _app_root)
        from skill_engine.orchestrator import init_engine
        model_router = getattr(commander, "router", None)
        skill_orchestrator = init_engine(model_router=model_router)
        runtime["skill_orchestrator"] = skill_orchestrator
        runtime["skill_registry"] = skill_orchestrator._registry
        commander.set_skill_orchestrator(skill_orchestrator)
    except Exception as _e:
        import logging as _logging
        _logging.getLogger("megav").warning("Skill Engine unavailable: %s", _e)
        runtime["skill_orchestrator"] = None
        runtime["skill_registry"] = None

    # Register Agency Library — loaded lazily on first use, not at startup
    try:
        from .agents.agency_library import get_agency_library
        runtime["agency_library"] = get_agency_library()
    except Exception as _e:
        import logging as _logging
        _logging.getLogger("megav").warning("Agency Library unavailable: %s", _e)
        runtime["agency_library"] = None

    # Make NexusOrchestrator available in runtime
    try:
        from .agents.nexus_orchestrator import get_nexus_orchestrator
        runtime["nexus_orchestrator"] = get_nexus_orchestrator()
    except Exception as _e:
        import logging as _logging
        _logging.getLogger("megav").warning("NexusOrchestrator unavailable: %s", _e)
        runtime["nexus_orchestrator"] = None

    # Finance Agent (only if Stripe API key is configured)
    from .integrations.secrets import get_stripe_key
    config = load_app_config()
    _stripe_key = get_stripe_key()
    if _stripe_key:
        from .integrations.payment_service import PaymentService
        from .agents.finance_agent import FinanceAgent
        _payment_svc = PaymentService(_stripe_key)
        runtime["finance"] = FinanceAgent(
            payment_service=_payment_svc,
            email_service=runtime.get("email_service"),
            crm_service=runtime.get("crm_service"),
        )
    else:
        print("[MegaV] Stripe key not set — finance agent disabled. Add stripe_api_key to config.")

    return runtime


def print_banner():
    """Print the application banner."""
    banner = """
==============================================================

         MegaV  -  Local AI Operator  v2.0

   Code  |  Browse  |  Email  |  GitHub  |  Social  |  NEXUS
   31 Native Skills  |  190+ Agency Specialists  |  OutputEngine
   Real code. Real output. No fakes.

==============================================================
    """
    try:
        print(banner)
    except UnicodeEncodeError:
        print("MegaV v2.0 - Local AI Operator")


def start_cli_session(runtime: dict = None):
    """Start an interactive CLI session."""
    from .cli import main as cli_main
    cli_main(runtime=runtime)


def start_gui():
    """Start the GUI application."""
    try:
        from .gui.app import main as gui_main
        return gui_main()
    except ImportError as e:
        print(f"Error starting GUI: {e}")
        print("Make sure PySide6 is installed: pip install pyside6")
        return 1


async def execute_single_goal(goal: str, runtime: dict) -> dict:
    """Execute a single goal and return the result.

    Args:
        goal: User's goal
        runtime: Runtime context

    Returns:
        Execution result
    """
    commander = runtime.get("commander")
    if not commander:
        return {"success": False, "error": "Commander not initialized"}

    from .tool_system.agent_loop import AgentLoop
    loop = AgentLoop(runtime)
    result = await loop.run(goal)
    return result



def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MegaV - Local AI Operator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main                          # Start interactive CLI
  python -m src.main --gui                    # Start GUI
  python -m src.main --goal "Create a Python script"  # Execute single goal
  python -m src.main --version                # Show version
        """,
    )

    parser.add_argument(
        "--gui",
        action="store_true",
        help="Start the GUI application",
    )

    parser.add_argument(
        "--goal",
        type=str,
        help="Execute a single goal and exit",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="MegaV 2.6.0",
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/settings.yaml",
        help="Path to configuration file",
    )

    parser.add_argument(
        "--profile",
        type=str,
        default="profiles",
        help="Path to profiles directory",
    )

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Load configuration
    load_app_config()

    # Build runtime
    print("Initializing components...")
    runtime = build_runtime()
    print("Ready!\n")

    # Execute based on arguments
    if args.gui:
        return start_gui()
    elif args.goal:
        result = asyncio.run(execute_single_goal(args.goal, runtime))
        print(f"\nResult: {result}")
        return 0 if result.get("success") else 1
    else:
        # Start interactive CLI
        start_cli_session(runtime=runtime)
        return 0


if __name__ == "__main__":
    sys.exit(main())
