"""Workflow recording and replay tools."""

import json
from datetime import datetime
from typing import Any, Optional

from ..memory.workflow_store import WorkflowStore


class WorkflowTools:
    """Tools for recording, saving, and replaying workflows."""

    def __init__(self, workflow_store: WorkflowStore):
        """Initialize workflow tools.

        Args:
            workflow_store: WorkflowStore instance
        """
        self.store = workflow_store
        self.recording = False
        self.current_workflow: list[dict[str, Any]] = []
        self.workflow_name: str = ""
        self.workflow_category: str = ""

    def start_workflow_recording(
        self,
        name: str,
        category: str = "general",
        description: str = "",
    ) -> dict[str, Any]:
        """Start recording a new workflow.

        Args:
            name: Workflow name
            category: Workflow category
            description: Workflow description

        Returns:
            Start result
        """
        if self.recording:
            return {
                "success": False,
                "error": "Already recording a workflow. Stop current recording first.",
            }

        self.recording = True
        self.current_workflow = []
        self.workflow_name = name
        self.workflow_category = category

        # Add metadata as first step
        self.current_workflow.append({
            "type": "metadata",
            "name": name,
            "category": category,
            "description": description,
            "started_at": datetime.now().isoformat(),
        })

        return {
            "success": True,
            "name": name,
            "category": category,
            "message": "Workflow recording started",
        }

    def record_workflow_step(
        self,
        action: str,
        params: dict[str, Any],
        result: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Record a step in the current workflow.

        Args:
            action: Action name
            params: Action parameters
            result: Optional action result

        Returns:
            Record result
        """
        if not self.recording:
            return {
                "success": False,
                "error": "No active workflow recording",
            }

        step = {
            "type": "action",
            "action": action,
            "params": params,
            "timestamp": datetime.now().isoformat(),
        }

        if result:
            step["result"] = result

        self.current_workflow.append(step)

        return {
            "success": True,
            "step_number": len(self.current_workflow) - 1,
        }

    def save_workflow(self, tags: Optional[list[str]] = None) -> dict[str, Any]:
        """Save the current workflow.

        Args:
            tags: Optional tags for the workflow

        Returns:
            Save result
        """
        if not self.recording:
            return {
                "success": False,
                "error": "No active workflow recording",
            }

        if len(self.current_workflow) <= 1:
            return {
                "success": False,
                "error": "Workflow has no actions to save",
            }

        # Add completion timestamp
        self.current_workflow.append({
            "type": "completion",
            "timestamp": datetime.now().isoformat(),
        })

        # Extract metadata
        metadata = self.current_workflow[0]
        steps = self.current_workflow[1:]

        # Save to store
        filepath = self.store.save_workflow(
            name=metadata.get("name", self.workflow_name),
            category=metadata.get("category", self.workflow_category),
            steps=steps,
            description=metadata.get("description", ""),
            tags=tags,
        )

        # Reset recording state
        self.recording = False
        self.current_workflow = []

        return {
            "success": True,
            "filepath": filepath,
            "name": self.workflow_name,
            "category": self.workflow_category,
        }

    def cancel_recording(self) -> dict[str, Any]:
        """Cancel the current workflow recording.

        Returns:
            Cancel result
        """
        if not self.recording:
            return {
                "success": False,
                "error": "No active workflow recording",
            }

        self.recording = False
        self.current_workflow = []

        return {
            "success": True,
            "message": "Workflow recording cancelled",
        }

    def load_workflow(self, name: str, category: str) -> dict[str, Any]:
        """Load a workflow by name and category.

        Args:
            name: Workflow name
            category: Workflow category

        Returns:
            Workflow data
        """
        workflow = self.store.load_workflow(name, category)

        if workflow:
            return {
                "success": True,
                "workflow": workflow,
            }
        else:
            return {
                "success": False,
                "error": f"Workflow not found: {name} in {category}",
            }

    def list_workflows(self, category: Optional[str] = None) -> dict[str, Any]:
        """List all workflows.

        Args:
            category: Optional category filter

        Returns:
            List of workflows
        """
        workflows = self.store.list_workflows(category)

        return {
            "success": True,
            "workflows": workflows,
            "count": len(workflows),
        }

    def search_workflows(self, query: str) -> dict[str, Any]:
        """Search workflows.

        Args:
            query: Search query

        Returns:
            Matching workflows
        """
        workflows = self.store.search_workflows(query)

        return {
            "success": True,
            "workflows": workflows,
            "count": len(workflows),
        }

    def delete_workflow(self, name: str, category: str) -> dict[str, Any]:
        """Delete a workflow.

        Args:
            name: Workflow name
            category: Workflow category

        Returns:
            Delete result
        """
        deleted = self.store.delete_workflow(name, category)

        if deleted:
            return {
                "success": True,
                "message": f"Workflow deleted: {name}",
            }
        else:
            return {
                "success": False,
                "error": f"Workflow not found: {name}",
            }

    def convert_workflow_to_skill(self, name: str, category: str) -> dict[str, Any]:
        """Convert a workflow to a skill.

        Args:
            name: Workflow name
            category: Workflow category

        Returns:
            Conversion result
        """
        manifest_path = self.store.convert_to_skill(name, category)

        if manifest_path:
            return {
                "success": True,
                "manifest_path": manifest_path,
                "message": f"Workflow converted to skill: {name}",
            }
        else:
            return {
                "success": False,
                "error": f"Could not convert workflow: {name}",
            }

    def get_recording_status(self) -> dict[str, Any]:
        """Get current recording status.

        Returns:
            Recording status
        """
        return {
            "success": True,
            "recording": self.recording,
            "name": self.workflow_name if self.recording else None,
            "category": self.workflow_category if self.recording else None,
            "steps_recorded": len(self.current_workflow) if self.recording else 0,
        }

    async def replay_workflow(
        self,
        name: str,
        category: str,
        param_overrides: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Replay a workflow.

        Args:
            name: Workflow name
            category: Workflow category
            param_overrides: Optional parameter overrides

        Returns:
            Replay result
        """
        workflow_data = self.store.load_workflow(name, category)

        if not workflow_data:
            return {
                "success": False,
                "error": f"Workflow not found: {name}",
            }

        steps = workflow_data.get("steps", [])
        results = []

        for step in steps:
            if step.get("type") != "action":
                continue

            action = step.get("action", "")
            params = step.get("params", {})

            # Apply overrides
            if param_overrides:
                params.update(param_overrides)

            # Execute step (this would integrate with the tool system)
            results.append({
                "action": action,
                "params": params,
                "status": "executed",  # Placeholder
            })

        return {
            "success": True,
            "workflow": name,
            "steps_executed": len(results),
            "results": results,
        }
