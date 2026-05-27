"""Project-specific memory storage for notes and instructions."""

import json
from pathlib import Path
from typing import Any, Optional


class ProjectStore:
    """Manages project-specific notes, instructions, and memory."""

    def __init__(self, project_dir: str = "."):
        """Initialize project store.

        Args:
            project_dir: Project directory path
        """
        self.project_dir = Path(project_dir)
        self.memory_dir = self.project_dir / ".executive-agent" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.notes: dict[str, Any] = {}
        self.instructions: str = ""
        self._load_memory()

    def _load_memory(self) -> None:
        """Load project memory from disk."""
        # Load notes
        notes_path = self.memory_dir / "notes.json"
        if notes_path.exists():
            with open(notes_path, "r", encoding="utf-8") as f:
                self.notes = json.load(f)

        # Load instructions
        instructions_path = self.memory_dir / "instructions.txt"
        if instructions_path.exists():
            with open(instructions_path, "r", encoding="utf-8") as f:
                self.instructions = f.read()

    def save_notes(self) -> None:
        """Save notes to disk."""
        notes_path = self.memory_dir / "notes.json"
        with open(notes_path, "w", encoding="utf-8") as f:
            json.dump(self.notes, f, indent=2, ensure_ascii=False)

    def save_instructions(self) -> None:
        """Save instructions to disk."""
        instructions_path = self.memory_dir / "instructions.txt"
        with open(instructions_path, "w", encoding="utf-8") as f:
            f.write(self.instructions)

    def add_note(self, key: str, content: Any) -> None:
        """Add a note to project memory.

        Args:
            key: Note key
            content: Note content
        """
        self.notes[key] = content
        self.save_notes()

    def get_note(self, key: str, default: Any = None) -> Any:
        """Get a note by key.

        Args:
            key: Note key
            default: Default value if not found

        Returns:
            Note content or default
        """
        return self.notes.get(key, default)

    def delete_note(self, key: str) -> bool:
        """Delete a note.

        Args:
            key: Note key

        Returns:
            True if deleted, False if not found
        """
        if key in self.notes:
            del self.notes[key]
            self.save_notes()
            return True
        return False

    def set_instructions(self, instructions: str) -> None:
        """Set project instructions.

        Args:
            instructions: Instructions text
        """
        self.instructions = instructions
        self.save_instructions()

    def get_instructions(self) -> str:
        """Get project instructions.

        Returns:
            Instructions text
        """
        return self.instructions

    def append_instructions(self, text: str) -> None:
        """Append to project instructions.

        Args:
            text: Text to append
        """
        if self.instructions:
            self.instructions += "\n\n" + text
        else:
            self.instructions = text
        self.save_instructions()

    def get_all_notes(self) -> dict[str, Any]:
        """Get all project notes.

        Returns:
            Dictionary of all notes
        """
        return self.notes.copy()

    def search_notes(self, query: str) -> dict[str, Any]:
        """Search notes by key or content.

        Args:
            query: Search query

        Returns:
            Matching notes
        """
        query_lower = query.lower()
        results = {}

        for key, content in self.notes.items():
            content_str = str(content).lower()
            if query_lower in key.lower() or query_lower in content_str:
                results[key] = content

        return results

    def clear_notes(self) -> None:
        """Clear all project notes."""
        self.notes = {}
        self.save_notes()

    def get_context_for_agent(self) -> str:
        """Get formatted context for agent consumption.

        Returns:
            Formatted context string
        """
        context_parts = []

        if self.instructions:
            context_parts.append("## Project Instructions\n" + self.instructions)

        if self.notes:
            context_parts.append("## Project Notes")
            for key, value in self.notes.items():
                context_parts.append(f"- **{key}**: {value}")

        return "\n\n".join(context_parts) if context_parts else ""
