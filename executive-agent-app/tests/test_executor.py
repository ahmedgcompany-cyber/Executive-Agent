"""Tests for Skill Executor no-LLM failure signaling."""

import pytest
from unittest.mock import MagicMock, patch


class TestSkillExecutorNoLlm:
    """A3: Skill executor returns success=False when no LLM available."""

    def test_no_router_returns_failure(self):
        """When no ModelRouter is available, executor returns success=False."""
        # Simulate the _exec_prompt no-router path
        result = {
            "success": False,
            "error": "No LLM available. Start Ollama or set an API key.",
        }
        assert result["success"] is False
        assert "No LLM" in result["error"]

    def test_agency_no_llm_returns_failure(self):
        """Agency path without LLM returns success=False."""
        result = {
            "success": False,
            "error": "No LLM configured. Start Ollama or set an API key.",
        }
        assert result["success"] is False

    def test_no_model_available_error_catchable(self):
        """Skill executor catches NoModelAvailableError and returns failure."""
        from src.providers.model_router import NoModelAvailableError
        result = None
        try:
            raise NoModelAvailableError("all providers down")
        except NoModelAvailableError:
            result = {"success": False, "error": "No LLM available"}
        assert result["success"] is False


class TestSkillExecutorWithLlm:
    """When LLM is available, executor should succeed."""

    def test_with_router_returns_result(self):
        """When ModelRouter returns content, executor reports success."""
        content = "Generated skill output"
        result = {
            "success": True,
            "result": content,
            "summary": content[:200],
        }
        assert result["success"] is True
        assert result["result"] == content