"""
Skill Engine — production-grade skill management for MegaV.

Quick start::

    # In any agent:
    from skill_engine.orchestrator import run_task

    result = run_task("Design a modern dashboard UI and package it")
    if result.success:
        print(result.summary)

Initialisation (done once in main.py)::

    from skill_engine.orchestrator import init_engine
    init_engine(model_router=router)
"""

from .schemas     import Skill, SkillMatch, ExecutionResult, OrchestrationResult, ExecutionType
from .registry    import SkillRegistry
from .selector    import SkillSelector
from .executor    import SkillExecutor
from .orchestrator import SkillOrchestrator, init_engine, get_engine, run_task

__all__ = [
    "Skill",
    "SkillMatch",
    "ExecutionResult",
    "OrchestrationResult",
    "ExecutionType",
    "SkillRegistry",
    "SkillSelector",
    "SkillExecutor",
    "SkillOrchestrator",
    "init_engine",
    "get_engine",
    "run_task",
]
