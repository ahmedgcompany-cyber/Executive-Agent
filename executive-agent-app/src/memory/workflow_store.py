"""Workflow storage for saving and replaying successful procedures."""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Any, Optional


class WorkflowStore:
    """Manages workflow recording, storage, and replay."""

    def __init__(self, workflows_dir: str = "workflows"):
        """Initialize workflow store.

        Args:
            workflows_dir: Directory containing workflow files
        """
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        for subdir in ["browser", "desktop", "jobs", "content", "creative_apps"]:
            (self.workflows_dir / subdir).mkdir(exist_ok=True)

    def save_workflow(
        self,
        name: str,
        category: str,
        steps: list[dict[str, Any]],
        description: str = "",
        tags: Optional[list[str]] = None,
    ) -> str:
        """Save a workflow to disk.

        Args:
            name: Workflow name
            category: Workflow category (browser, desktop, jobs, content, creative_apps)
            steps: List of workflow steps
            description: Workflow description
            tags: Optional tags for the workflow

        Returns:
            Path to saved workflow file
        """
        workflow = {
            "name": name,
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "description": description,
            "category": category,
            "tags": tags or [],
            "steps": steps,
        }

        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in "_-").lower()
        filename = f"{safe_name}.yaml"

        category_dir = self.workflows_dir / category
        category_dir.mkdir(exist_ok=True)

        filepath = category_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(workflow, f, default_flow_style=False, allow_unicode=True)

        return str(filepath)

    def load_workflow(self, name: str, category: str) -> Optional[dict[str, Any]]:
        """Load a workflow by name and category.

        Args:
            name: Workflow name
            category: Workflow category

        Returns:
            Workflow data or None if not found
        """
        safe_name = "".join(c for c in name if c.isalnum() or c in "_-").lower()
        filepath = self.workflows_dir / category / f"{safe_name}.yaml"

        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def list_workflows(self, category: Optional[str] = None) -> list[dict[str, Any]]:
        """List all workflows, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of workflow summaries
        """
        workflows = []

        categories = [category] if category else ["browser", "desktop", "jobs", "content", "creative_apps"]

        for cat in categories:
            cat_dir = self.workflows_dir / cat
            if not cat_dir.exists():
                continue

            for filepath in cat_dir.glob("*.yaml"):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        workflow = yaml.safe_load(f)
                        workflows.append({
                            "name": workflow.get("name", filepath.stem),
                            "category": cat,
                            "description": workflow.get("description", ""),
                            "tags": workflow.get("tags", []),
                            "created_at": workflow.get("created_at", ""),
                            "filepath": str(filepath),
                        })
                except Exception:
                    continue

        return workflows

    def search_workflows(self, query: str) -> list[dict[str, Any]]:
        """Search workflows by name, description, or tags.

        Args:
            query: Search query

        Returns:
            List of matching workflows
        """
        query_lower = query.lower()
        all_workflows = self.list_workflows()

        matches = []
        for workflow in all_workflows:
            if (query_lower in workflow["name"].lower() or
                query_lower in workflow["description"].lower() or
                any(query_lower in tag.lower() for tag in workflow["tags"])):
                matches.append(workflow)

        return matches

    def delete_workflow(self, name: str, category: str) -> bool:
        """Delete a workflow.

        Args:
            name: Workflow name
            category: Workflow category

        Returns:
            True if deleted, False if not found
        """
        safe_name = "".join(c for c in name if c.isalnum() or c in "_-").lower()
        filepath = self.workflows_dir / category / f"{safe_name}.yaml"

        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def convert_to_skill(self, name: str, category: str) -> Optional[str]:
        """Convert a workflow to a skill manifest.

        Args:
            name: Workflow name
            category: Workflow category

        Returns:
            Path to created skill manifest or None
        """
        workflow = self.load_workflow(name, category)
        if not workflow:
            return None

        skill_manifest = {
            "name": workflow["name"],
            "version": "1.0.0",
            "description": workflow.get("description", ""),
            "category": category,
            "tags": workflow.get("tags", []),
            "entry_point": f"workflows/{category}/{name}.yaml",
            "type": "workflow",
            "created_at": datetime.now().isoformat(),
        }

        # Save to skills manifests
        skills_dir = Path("skills/manifests")
        skills_dir.mkdir(parents=True, exist_ok=True)

        safe_name = "".join(c for c in name if c.isalnum() or c in "_-").lower()
        manifest_path = skills_dir / f"{safe_name}.json"

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(skill_manifest, f, indent=2, ensure_ascii=False)

        return str(manifest_path)
