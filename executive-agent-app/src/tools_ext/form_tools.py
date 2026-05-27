"""Form-specific tools for intelligent form filling."""

import re
from typing import Any, Optional

from .browser_tools import BrowserTools


class FormTools:
    """Intelligent form filling tools."""

    def __init__(self, browser_tools: BrowserTools):
        """Initialize form tools.

        Args:
            browser_tools: BrowserTools instance
        """
        self.browser = browser_tools

        # Common field mappings
        self.field_mappings = {
            # Name fields
            "name": ["name", "full_name", "fullname", "your_name"],
            "first_name": ["first_name", "firstname", "firstName", "fname"],
            "last_name": ["last_name", "lastname", "lastName", "lname"],

            # Contact fields
            "email": ["email", "e-mail", "email_address", "emailAddress"],
            "phone": ["phone", "phone_number", "phonenumber", "tel", "telephone", "mobile"],

            # Location fields
            "location": ["location", "city", "address", "current_location"],
            "country": ["country", "country_code"],

            # Job-related fields
            "notice_period": ["notice_period", "notice", "noticeperiod", "availability"],
            "salary_expectation": ["salary", "expected_salary", "salary_expectation", "compensation"],
            "years_experience": ["years_experience", "experience", "years_of_experience", "yoe"],
            "work_authorization": ["work_authorization", "work_status", "authorization", "visa_status"],

            # Links
            "linkedin": ["linkedin", "linkedin_url", "linked_in"],
            "portfolio": ["portfolio", "portfolio_url", "website", "personal_website"],
            "github": ["github", "github_url", "git_hub"],
        }

    async def analyze_form_fields(self) -> dict[str, Any]:
        """Analyze and categorize form fields on the current page.

        Returns:
            Categorized form fields
        """
        result = await self.browser.browser_extract_fields()
        if not result.get("success"):
            return result

        fields = result.get("fields", [])
        categorized = {
            "text_inputs": [],
            "selects": [],
            "textareas": [],
            "file_inputs": [],
            "checkboxes": [],
            "radios": [],
            "unknown": [],
        }

        for field in fields:
            field_type = field.get("type", "text")
            tag = field.get("tag", "input")

            if tag == "select":
                categorized["selects"].append(field)
            elif tag == "textarea":
                categorized["textareas"].append(field)
            elif field_type == "file":
                categorized["file_inputs"].append(field)
            elif field_type == "checkbox":
                categorized["checkboxes"].append(field)
            elif field_type == "radio":
                categorized["radios"].append(field)
            elif field_type in ["text", "email", "tel", "url", "number"]:
                categorized["text_inputs"].append(field)
            else:
                categorized["unknown"].append(field)

        # Try to identify field purposes
        for category in categorized.values():
            for field in category:
                field["purpose"] = self._identify_field_purpose(field)

        return {
            "success": True,
            "categorized": categorized,
            "all_fields": fields,
        }

    def _identify_field_purpose(self, field: dict[str, Any]) -> Optional[str]:
        """Identify the purpose of a form field.

        Args:
            field: Field data

        Returns:
            Identified purpose or None
        """
        # Check various field attributes
        check_values = [
            field.get("name", "").lower(),
            field.get("id", "").lower(),
            field.get("placeholder", "").lower(),
            field.get("label", "").lower(),
        ]

        for purpose, patterns in self.field_mappings.items():
            for pattern in patterns:
                for value in check_values:
                    if pattern in value:
                        return purpose

        return None

    def map_fields_to_profile(
        self,
        fields: list[dict[str, Any]],
        profile: dict[str, Any],
        job_answers: dict[str, Any],
    ) -> dict[str, str]:
        """Map form fields to profile values.

        Args:
            fields: Form fields to map
            profile: User profile data
            job_answers: Job answers data

        Returns:
            Field to value mappings
        """
        mappings = {}

        for field in fields:
            purpose = field.get("purpose")
            selector = field.get("selector")

            if not purpose or not selector:
                continue

            # Try profile first
            if purpose in profile:
                value = profile[purpose]
                if isinstance(value, list):
                    value = value[0] if value else ""
                mappings[selector] = str(value)
            # Then try job answers
            elif purpose in job_answers:
                mappings[selector] = str(job_answers[purpose])
            # Handle composite fields
            elif purpose == "name":
                first = profile.get("first_name", "")
                last = profile.get("last_name", "")
                if first and last:
                    mappings[selector] = f"{first} {last}"

        return mappings

    async def fill_form_from_profile(
        self,
        profile: dict[str, Any],
        job_answers: dict[str, Any],
    ) -> dict[str, Any]:
        """Fill the current form using profile data.

        Args:
            profile: User profile data
            job_answers: Job answers data

        Returns:
            Fill results
        """
        # Analyze form
        analysis = await self.analyze_form_fields()
        if not analysis.get("success"):
            return analysis

        results = []
        categorized = analysis.get("categorized", {})

        # Collect all fields
        all_fields = []
        for category_fields in categorized.values():
            all_fields.extend(category_fields)

        # Map fields to values
        mappings = self.map_fields_to_profile(all_fields, profile, job_answers)

        # Fill text inputs
        for field in categorized.get("text_inputs", []):
            selector = field.get("selector")
            purpose = field.get("purpose")

            if selector and selector in mappings:
                result = await self.browser.browser_type(selector, mappings[selector])
                results.append({
                    "field": selector,
                    "purpose": purpose,
                    "result": result,
                })

        # Fill textareas
        for field in categorized.get("textareas", []):
            selector = field.get("selector")
            purpose = field.get("purpose")

            if selector and selector in mappings:
                result = await self.browser.browser_type(selector, mappings[selector])
                results.append({
                    "field": selector,
                    "purpose": purpose,
                    "result": result,
                })

        return {
            "success": True,
            "filled_count": len([r for r in results if r["result"].get("success")]),
            "results": results,
        }

    async def fill_detected_form(
        self,
        field_values: dict[str, str],
    ) -> dict[str, Any]:
        """Fill form fields with provided values.

        Args:
            field_values: Dictionary of selector -> value

        Returns:
            Fill results
        """
        results = []

        for selector, value in field_values.items():
            result = await self.browser.browser_type(selector, value)
            results.append({
                "selector": selector,
                "value": value,
                "result": result,
            })

        return {
            "success": True,
            "filled_count": len([r for r in results if r["result"].get("success")]),
            "results": results,
        }

    async def select_dropdowns(
        self,
        selections: dict[str, str],
    ) -> dict[str, Any]:
        """Select dropdown options.

        Args:
            selections: Dictionary of selector -> value

        Returns:
            Selection results
        """
        results = []

        for selector, value in selections.items():
            result = await self.browser.browser_select(selector, value)
            results.append({
                "selector": selector,
                "value": value,
                "result": result,
            })

        return {
            "success": True,
            "selected_count": len([r for r in results if r["result"].get("success")]),
            "results": results,
        }

    async def upload_files(
        self,
        uploads: dict[str, str],
    ) -> dict[str, Any]:
        """Upload files to file inputs.

        Args:
            uploads: Dictionary of selector -> file path

        Returns:
            Upload results
        """
        results = []

        for selector, file_path in uploads.items():
            result = await self.browser.browser_upload(selector, file_path)
            results.append({
                "selector": selector,
                "file_path": file_path,
                "result": result,
            })

        return {
            "success": True,
            "uploaded_count": len([r for r in results if r["result"].get("success")]),
            "results": results,
        }

    async def retry_invalid_fields(
        self,
        invalid_fields: list[str],
        profile: dict[str, Any],
        job_answers: dict[str, Any],
    ) -> dict[str, Any]:
        """Retry filling fields that failed validation.

        Args:
            invalid_fields: List of selectors that failed
            profile: User profile data
            job_answers: Job answers data

        Returns:
            Retry results
        """
        results = []

        for selector in invalid_fields:
            # Try to find alternative value
            value = self._find_alternative_value(selector, profile, job_answers)
            if value:
                result = await self.browser.browser_type(selector, value)
                results.append({
                    "selector": selector,
                    "value": value,
                    "result": result,
                })

        return {
            "success": True,
            "retried_count": len(results),
            "results": results,
        }

    def _find_alternative_value(
        self,
        selector: str,
        profile: dict[str, Any],
        job_answers: dict[str, Any],
    ) -> Optional[str]:
        """Find an alternative value for a field.

        Args:
            selector: Field selector
            profile: User profile
            job_answers: Job answers

        Returns:
            Alternative value or None
        """
        # This is a simplified implementation
        # In practice, you might want more sophisticated matching
        selector_lower = selector.lower()

        for key, value in {**profile, **job_answers}.items():
            if key in selector_lower:
                if isinstance(value, list):
                    return value[0] if value else None
                return str(value)

        return None
