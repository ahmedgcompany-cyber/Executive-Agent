"""
Skill Engine — Data schemas.

All data structures used throughout the skill engine are defined here.
Using dataclasses so there are zero third-party dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ExecutionType(str, Enum):
    """How a skill is executed."""
    PROMPT  = "prompt"   # LLM call with SKILL.md as system context
    SCRIPT  = "script"   # Run local script(s)
    HYBRID  = "hybrid"   # Scripts first, then LLM


class SkillStatus(str, Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"
    ERROR    = "error"


@dataclass
class Skill:
    """Normalised representation of one parsed skill."""

    # Identity
    id:               str            # slug derived from folder name
    name:             str            # human-readable name from SKILL.md frontmatter
    description:      str            # one-line description
    folder_name:      str            # subfolder inside awesome-claude-skills-master
    folder_path:      str            # absolute path to skill folder

    # Classification
    category:         str  = "general"
    subcategory:      str  = ""
    use_cases:        list[str] = field(default_factory=list)   # extracted from SKILL.md

    # I/O
    inputs:           list[str] = field(default_factory=list)
    outputs:          list[str] = field(default_factory=list)

    # Execution
    execution_type:   ExecutionType = ExecutionType.PROMPT
    scripts:          list[str] = field(default_factory=list)   # relative paths
    dependencies:     list[str] = field(default_factory=list)

    # Matching
    trigger_keywords: list[str] = field(default_factory=list)
    agent_affinity:   list[str] = field(default_factory=list)   # ["coder","content",…]

    # Content
    skill_md_text:    str  = ""    # full SKILL.md content for LLM context
    has_context:      bool = True

    # State
    status:           SkillStatus = SkillStatus.ACTIVE
    load_error:       str  = ""

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "name":             self.name,
            "description":      self.description,
            "category":         self.category,
            "subcategory":      self.subcategory,
            "use_cases":        self.use_cases,
            "inputs":           self.inputs,
            "outputs":          self.outputs,
            "execution_type":   self.execution_type.value,
            "scripts":          self.scripts,
            "dependencies":     self.dependencies,
            "trigger_keywords": self.trigger_keywords,
            "agent_affinity":   self.agent_affinity,
            "has_context":      self.has_context,
            "status":           self.status.value,
            "folder_path":      self.folder_path,
            "load_error":       self.load_error,
        }

    @property
    def is_active(self) -> bool:
        return self.status == SkillStatus.ACTIVE


@dataclass
class SkillMatch:
    """A scored skill candidate returned by the selector."""
    skill:   Skill
    score:   float
    reason:  str  = ""          # human-readable explanation
    matched: list[str] = field(default_factory=list)  # keywords that fired

    def to_dict(self) -> dict:
        return {
            "skill_id":  self.skill.id,
            "name":      self.skill.name,
            "score":     round(self.score, 3),
            "reason":    self.reason,
            "matched":   self.matched,
        }


@dataclass
class ExecutionResult:
    """Result from executing one skill."""
    skill_id:       str
    skill_name:     str
    success:        bool
    result:         str  = ""       # main output text
    summary:        str  = ""       # ≤300 char digest
    mode:           str  = ""       # "prompt" | "script" | "hybrid"
    elapsed_s:      float = 0.0
    error:          str  = ""
    script_outputs: list[dict] = field(default_factory=list)
    system_prompt:  str  = ""       # LLM system prompt used (for debug)

    def to_dict(self) -> dict:
        return {
            "skill_id":    self.skill_id,
            "skill_name":  self.skill_name,
            "success":     self.success,
            "result":      self.result,
            "summary":     self.summary,
            "mode":        self.mode,
            "elapsed_s":   self.elapsed_s,
            "error":       self.error,
        }


@dataclass
class OrchestrationResult:
    """Aggregated result from the orchestrator (may cover multiple skills)."""
    success:         bool
    summary:         str
    full_result:     str  = ""
    skills_used:     list[str] = field(default_factory=list)
    step_results:    list[ExecutionResult] = field(default_factory=list)
    total_elapsed_s: float = 0.0
    chained:         bool  = False

    def to_dict(self) -> dict:
        return {
            "success":         self.success,
            "summary":         self.summary,
            "full_result":     self.full_result,
            "skills_used":     self.skills_used,
            "step_results":    [r.to_dict() for r in self.step_results],
            "total_elapsed_s": self.total_elapsed_s,
            "chained":         self.chained,
        }
