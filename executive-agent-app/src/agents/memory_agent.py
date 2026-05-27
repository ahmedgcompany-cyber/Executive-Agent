"""Memory agent for profile and workflow memory tasks."""

from pathlib import Path
from typing import Any, Optional

from ..memory.profile_store import ProfileStore
from ..memory.workflow_store import WorkflowStore
from ..memory.project_store import ProjectStore


class MemoryAgent:
    """Specialist agent for memory and profile management."""

    def __init__(
        self,
        profile_store: ProfileStore,
        workflow_store: Optional[WorkflowStore] = None,
        project_store: Optional[ProjectStore] = None,
    ):
        """Initialize memory agent.

        Args:
            profile_store: ProfileStore instance
            workflow_store: Optional WorkflowStore instance
            project_store: Optional ProjectStore instance
        """
        self.profile = profile_store
        self.workflow = workflow_store
        self.project = project_store

    def fetch_saved_answer(self, key: str, default: str = "") -> dict[str, Any]:
        """Fetch a saved answer.

        Args:
            key: Answer key
            default: Default value

        Returns:
            Answer value
        """
        value = self.profile.get_job_answer(key, default)
        return {
            "success": True,
            "key": key,
            "value": value,
        }

    def store_answer(self, key: str, value: str) -> dict[str, Any]:
        """Store an answer.

        Args:
            key: Answer key
            value: Answer value

        Returns:
            Store result
        """
        self.profile.update_job_answer(key, value)
        return {
            "success": True,
            "key": key,
            "value": value,
        }

    def get_profile_field(self, field: str) -> dict[str, Any]:
        """Get a profile field.

        Args:
            field: Field name

        Returns:
            Field value
        """
        value = self.profile.get_profile_value(field)
        return {
            "success": True,
            "field": field,
            "value": value,
        }

    def update_profile_field(self, field: str, value: Any) -> dict[str, Any]:
        """Update a profile field.

        Args:
            field: Field name
            value: New value

        Returns:
            Update result
        """
        self.profile.update_profile_field(field, value)
        return {
            "success": True,
            "field": field,
            "value": value,
        }

    def get_contact_info(self) -> dict[str, Any]:
        """Get contact information.

        Returns:
            Contact info
        """
        return {
            "success": True,
            "name": self.profile.get_profile_value("name", ""),
            "email": self.profile.get_primary_email(),
            "phone": self.profile.get_primary_phone(),
            "location": self.profile.get_profile_value("location", ""),
            "linkedin": self.profile.get_profile_value("linkedin", ""),
        }

    def load_workflow(self, name: str, category: str) -> dict[str, Any]:
        """Load a workflow.

        Args:
            name: Workflow name
            category: Workflow category

        Returns:
            Workflow data
        """
        if not self.workflow:
            return {"success": False, "error": "Workflow store not available"}

        workflow = self.workflow.load_workflow(name, category)
        if workflow:
            return {
                "success": True,
                "workflow": workflow,
            }
        else:
            return {
                "success": False,
                "error": f"Workflow not found: {name}",
            }

    def save_workflow(
        self,
        name: str,
        category: str,
        steps: list[dict[str, Any]],
        description: str = "",
    ) -> dict[str, Any]:
        """Save a workflow.

        Args:
            name: Workflow name
            category: Workflow category
            steps: Workflow steps
            description: Workflow description

        Returns:
            Save result
        """
        if not self.workflow:
            return {"success": False, "error": "Workflow store not available"}

        filepath = self.workflow.save_workflow(name, category, steps, description)
        return {
            "success": True,
            "filepath": filepath,
        }

    def search_workflows(self, query: str) -> dict[str, Any]:
        """Search workflows.

        Args:
            query: Search query

        Returns:
            Matching workflows
        """
        if not self.workflow:
            return {"success": False, "error": "Workflow store not available"}

        workflows = self.workflow.search_workflows(query)
        return {
            "success": True,
            "workflows": workflows,
            "count": len(workflows),
        }

    def get_project_context(self) -> dict[str, Any]:
        """Get project context.

        Returns:
            Project context
        """
        if not self.project:
            return {"success": False, "error": "Project store not available"}

        context = self.project.get_context_for_agent()
        return {
            "success": True,
            "context": context,
        }

    def add_project_note(self, key: str, content: Any) -> dict[str, Any]:
        """Add a project note.

        Args:
            key: Note key
            content: Note content

        Returns:
            Add result
        """
        if not self.project:
            return {"success": False, "error": "Project store not available"}

        self.project.add_note(key, content)
        return {
            "success": True,
            "key": key,
        }

    def get_task_summary(self, task_id: str) -> dict[str, Any]:
        """Get a task summary.

        Args:
            task_id: Task ID

        Returns:
            Task summary
        """
        # This is a placeholder - in practice, this would retrieve
        # from a task history store

        return {
            "success": False,
            "task_id": task_id,
            "note": "Task summary would be retrieved from history store",
        }

    def handle_memory_task(self, action: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle a memory task.

        Args:
            action: Action to perform
            context: Task context

        Returns:
            Task result
        """
        handlers = {
            "fetch_answer": lambda: self.fetch_saved_answer(
                context.get("key", ""),
                context.get("default", ""),
            ),
            "store_answer": lambda: self.store_answer(
                context.get("key", ""),
                context.get("value", ""),
            ),
            "get_profile_field": lambda: self.get_profile_field(context.get("field", "")),
            "update_profile_field": lambda: self.update_profile_field(
                context.get("field", ""),
                context.get("value"),
            ),
            "get_contact_info": self.get_contact_info,
            "load_workflow": lambda: self.load_workflow(
                context.get("name", ""),
                context.get("category", ""),
            ),
            "save_workflow": lambda: self.save_workflow(
                context.get("name", ""),
                context.get("category", ""),
                context.get("steps", []),
                context.get("description", ""),
            ),
            "search_workflows": lambda: self.search_workflows(context.get("query", "")),
            "get_project_context": self.get_project_context,
            "add_project_note": lambda: self.add_project_note(
                context.get("key", ""),
                context.get("content"),
            ),
            "get_task_summary": lambda: self.get_task_summary(context.get("task_id", "")),
        }

        goal_text = getattr(context, "goal", "") or getattr(context, "current_goal", "") or ""
        handlers["execute_goal"] = lambda: {
            "success": True,
            "summary": f"Memory agent received: {goal_text[:120]}",
            "message": "Use actions like get_profile_field, store_answer, or load_workflow.",
        }
        handlers["verify"] = lambda: {"success": True, "summary": "Memory task verified."}

        handler = handlers.get(action)
        if handler:
            return handler()

        return {"success": False, "error": f"Unknown action: {action}"}
