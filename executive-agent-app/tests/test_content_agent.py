"""Tests for ContentAgent _try_llm helper and placeholder removal."""

import pytest
from unittest.mock import MagicMock, patch


class TestContentAgentTryLlm:
    """A4: ContentAgent._try_llm() returns None on failure, content on success."""

    def test_try_llm_returns_none_on_no_model(self):
        """When NoModelAvailableError is raised, _try_llm returns None."""
        from src.agents.content_agent import ContentAgent
        agent = ContentAgent()
        from src.providers.model_router import NoModelAvailableError
        mock_router = MagicMock()
        mock_router.ask.side_effect = NoModelAvailableError("no model")
        with patch("src.providers.model_router.ModelRouter", return_value=mock_router):
            result = agent._try_llm("system", "user")
            assert result is None

    def test_try_llm_returns_none_on_exception(self):
        """On any exception, _try_llm returns None (not crash)."""
        from src.agents.content_agent import ContentAgent
        agent = ContentAgent()
        mock_router = MagicMock()
        mock_router.ask.side_effect = RuntimeError("broken")
        with patch("src.providers.model_router.ModelRouter", return_value=mock_router):
            result = agent._try_llm("system", "user")
            assert result is None

    def test_try_llm_returns_content_on_success(self):
        """When LLM returns content, _try_llm returns it."""
        from src.agents.content_agent import ContentAgent
        agent = ContentAgent()
        mock_router = MagicMock()
        mock_router.ask.return_value = "Generated content here"
        with patch("src.providers.model_router.ModelRouter", return_value=mock_router):
            result = agent._try_llm("system", "user")
            assert result == "Generated content here"


class TestContentAgentHonestFailure:
    """A4: All ContentAgent methods return success=False when no LLM available."""

    def test_youtube_description_no_llm(self):
        """create_youtube_description returns success=False without LLM."""
        from src.agents.content_agent import ContentAgent
        agent = ContentAgent()
        with patch.object(agent, "_try_llm", return_value=None):
            result = agent.create_youtube_description("Test", "content")
            assert result["success"] is False
            assert "No LLM" in result["error"]

    def test_blog_post_no_llm(self):
        """create_blog_post returns success=False without LLM."""
        from src.agents.content_agent import ContentAgent
        agent = ContentAgent()
        with patch.object(agent, "_try_llm", return_value=None):
            result = agent.create_blog_post("Test", ["intro", "body"])
            assert result["success"] is False

    def test_social_post_no_llm(self):
        """create_social_post returns success=False without LLM."""
        from src.agents.content_agent import ContentAgent
        agent = ContentAgent()
        with patch.object(agent, "_try_llm", return_value=None):
            result = agent.create_social_post("twitter", "message")
            assert result["success"] is False