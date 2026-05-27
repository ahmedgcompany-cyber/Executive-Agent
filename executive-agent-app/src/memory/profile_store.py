"""Profile storage for user data, job answers, and preferences.

Profile files live in the user-scoped data directory (see profile_paths).
The repo-tracked `profiles/` is template-only and never written to at runtime.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

from src.integrations.profile_paths import profiles_dir as _user_profiles_dir


class ProfileStore:
    """Manages user profile, job answers, and related data."""

    def __init__(self, profiles_dir: Optional[str] = None):
        """Initialize profile store.

        Args:
            profiles_dir: Optional override (defaults to user-scoped data dir)
        """
        if profiles_dir is None:
            self.profiles_dir = _user_profiles_dir()
        else:
            self.profiles_dir = Path(profiles_dir)
        self.user_profile: dict[str, Any] = {}
        self.job_answers: dict[str, Any] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load all profile data from disk."""
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        # Load user profile
        user_profile_path = self.profiles_dir / "user_profile.json"
        if user_profile_path.exists():
            with open(user_profile_path, "r", encoding="utf-8") as f:
                self.user_profile = json.load(f)

        # Load job answers
        job_answers_path = self.profiles_dir / "job_answers.json"
        if job_answers_path.exists():
            with open(job_answers_path, "r", encoding="utf-8") as f:
                self.job_answers = json.load(f)

    def save_user_profile(self, profile: dict[str, Any]) -> None:
        """Save user profile to disk.

        Args:
            profile: User profile data
        """
        self.user_profile = profile
        user_profile_path = self.profiles_dir / "user_profile.json"
        with open(user_profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)

    def save_job_answers(self, answers: dict[str, Any]) -> None:
        """Save job answers to disk.

        Args:
            answers: Job answers data
        """
        self.job_answers = answers
        job_answers_path = self.profiles_dir / "job_answers.json"
        with open(job_answers_path, "w", encoding="utf-8") as f:
            json.dump(answers, f, indent=2, ensure_ascii=False)

    def get_profile_value(self, key: str, default: Any = None) -> Any:
        """Get a value from user profile.

        Args:
            key: Profile key to retrieve
            default: Default value if key not found

        Returns:
            Profile value or default
        """
        return self.user_profile.get(key, default)

    def get_job_answer(self, key: str, default: str = "") -> str:
        """Get a job answer by key.

        Args:
            key: Answer key to retrieve
            default: Default value if key not found

        Returns:
            Answer value or default
        """
        return self.job_answers.get(key, default)

    def get_default_resume(self) -> Optional[str]:
        """Get path to default resume.

        Returns:
            Path to default resume or None
        """
        resume_path = self.user_profile.get("resume_default")
        if resume_path and os.path.exists(resume_path):
            return resume_path
        return None

    def get_content_profile(self) -> dict[str, Any]:
        """Get content creation profile.

        Returns:
            Content profile with writing style and preferences
        """
        return {
            "name": self.user_profile.get("name", ""),
            "writing_style": self.user_profile.get("writing_style", "professional"),
            "job_titles": self.user_profile.get("job_titles", []),
            "skills": self.user_profile.get("skills", []),
        }

    def update_profile_field(self, key: str, value: Any) -> None:
        """Update a single profile field.

        Args:
            key: Field key to update
            value: New value
        """
        self.user_profile[key] = value
        self.save_user_profile(self.user_profile)

    def update_job_answer(self, key: str, value: str) -> None:
        """Update a single job answer.

        Args:
            key: Answer key to update
            value: New value
        """
        self.job_answers[key] = value
        self.save_job_answers(self.job_answers)

    def get_all_emails(self) -> list[str]:
        """Get all user emails.

        Returns:
            List of email addresses
        """
        return self.user_profile.get("emails", [])

    def get_primary_email(self) -> str:
        """Get primary email address.

        Returns:
            Primary email or empty string
        """
        emails = self.get_all_emails()
        return emails[0] if emails else ""

    def get_all_phones(self) -> list[str]:
        """Get all phone numbers.

        Returns:
            List of phone numbers
        """
        return self.user_profile.get("phones", [])

    def get_primary_phone(self) -> str:
        """Get primary phone number.

        Returns:
            Primary phone or empty string
        """
        phones = self.get_all_phones()
        return phones[0] if phones else ""
