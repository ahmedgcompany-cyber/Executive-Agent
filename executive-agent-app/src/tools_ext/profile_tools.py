"""Profile tools for accessing user data."""

from typing import Any, Optional

from ..memory.profile_store import ProfileStore


class ProfileTools:
    """Tools for accessing profile data."""

    def __init__(self, profile_store: ProfileStore):
        """Initialize profile tools.

        Args:
            profile_store: ProfileStore instance
        """
        self.store = profile_store

    def load_user_profile(self) -> dict[str, Any]:
        """Load the complete user profile.

        Returns:
            User profile data
        """
        return {
            "success": True,
            "profile": self.store.user_profile,
        }

    def get_profile_field(self, field: str, default: Any = None) -> dict[str, Any]:
        """Get a specific profile field.

        Args:
            field: Field name
            default: Default value if not found

        Returns:
            Field value
        """
        value = self.store.get_profile_value(field, default)
        return {
            "success": True,
            "field": field,
            "value": value,
        }

    def get_job_answer(self, question_key: str, default: str = "") -> dict[str, Any]:
        """Get a job answer by key.

        Args:
            question_key: Question identifier
            default: Default value if not found

        Returns:
            Answer value
        """
        value = self.store.get_job_answer(question_key, default)
        return {
            "success": True,
            "key": question_key,
            "answer": value,
        }

    def get_default_resume(self) -> dict[str, Any]:
        """Get the default resume path.

        Returns:
            Resume path info
        """
        path = self.store.get_default_resume()
        return {
            "success": True,
            "path": path,
            "found": path is not None,
        }

    def get_content_profile(self) -> dict[str, Any]:
        """Get content creation profile.

        Returns:
            Content profile
        """
        profile = self.store.get_content_profile()
        return {
            "success": True,
            "profile": profile,
        }

    def get_contact_info(self) -> dict[str, Any]:
        """Get contact information.

        Returns:
            Contact info
        """
        return {
            "success": True,
            "name": self.store.get_profile_value("name", ""),
            "email": self.store.get_primary_email(),
            "phone": self.store.get_primary_phone(),
            "linkedin": self.store.get_profile_value("linkedin", ""),
            "portfolio": self.store.get_profile_value("portfolio", ""),
            "location": self.store.get_profile_value("location", ""),
        }

    def get_job_preferences(self) -> dict[str, Any]:
        """Get job preferences.

        Returns:
            Job preferences
        """
        prefs = self.store.get_profile_value("preferences", {})
        return {
            "success": True,
            "job_titles": self.store.get_profile_value("job_titles", []),
            "job_types": prefs.get("job_type", []),
            "work_modes": prefs.get("work_mode", []),
            "industries": prefs.get("industries", []),
            "salary_currency": prefs.get("salary_currency", ""),
            "notice_period_days": prefs.get("notice_period_days", 30),
        }

    def update_profile_field(self, field: str, value: Any) -> dict[str, Any]:
        """Update a profile field.

        Args:
            field: Field name
            value: New value

        Returns:
            Update result
        """
        try:
            self.store.update_profile_field(field, value)
            return {
                "success": True,
                "field": field,
                "value": value,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def update_job_answer(self, key: str, answer: str) -> dict[str, Any]:
        """Update a job answer.

        Args:
            key: Answer key
            answer: Answer value

        Returns:
            Update result
        """
        try:
            self.store.update_job_answer(key, answer)
            return {
                "success": True,
                "key": key,
                "answer": answer,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_all_job_answers(self) -> dict[str, Any]:
        """Get all job answers.

        Returns:
            All job answers
        """
        return {
            "success": True,
            "answers": self.store.job_answers,
        }

    def search_job_answers(self, query: str) -> dict[str, Any]:
        """Search job answers by key or content.

        Args:
            query: Search query

        Returns:
            Matching answers
        """
        query_lower = query.lower()
        matches = {}

        for key, value in self.store.job_answers.items():
            if query_lower in key.lower() or query_lower in str(value).lower():
                matches[key] = value

        return {
            "success": True,
            "matches": matches,
            "count": len(matches),
        }
