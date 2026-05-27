"""Tests for ModelRouter.ask() exception raising and role separation."""

import pytest
from unittest.mock import MagicMock, patch


class TestModelRouterAskRaises:
    """A2: ModelRouter.ask() raises NoModelAvailableError by default."""

    def test_no_model_available_error_exists(self):
        """NoModelAvailableError is importable from model_router."""
        from src.providers.model_router import NoModelAvailableError
        assert issubclass(NoModelAvailableError, Exception)

    def test_ask_default_raises(self):
        """When no providers available, ask() raises NoModelAvailableError."""
        from src.providers.model_router import ModelRouter, NoModelAvailableError
        router = ModelRouter()
        with patch.object(router, "_auto_pull_models"), \
             patch.object(router, "route_chat", return_value={"success": False, "fix_hint": "No LLM"}):
            with pytest.raises(NoModelAvailableError):
                router.ask(system="test", user="test", task_type="general")

    def test_ask_catchable_pattern(self):
        """Callers can catch NoModelAvailableError specifically."""
        from src.providers.model_router import ModelRouter, NoModelAvailableError
        router = ModelRouter()
        with patch.object(router, "_auto_pull_models"), \
             patch.object(router, "route_chat", return_value={"success": False, "fix_hint": "No LLM"}):
            caught = False
            try:
                router.ask(system="test", user="test")
            except NoModelAvailableError:
                caught = True
            assert caught

    def test_ask_returns_content_on_success(self):
        """When a provider returns content, ask() returns the text."""
        from src.providers.model_router import ModelRouter
        router = ModelRouter()
        with patch.object(router, "_auto_pull_models"), \
             patch.object(router, "route_chat", return_value={
                 "success": True,
                 "message": {"content": "Hello world"},
             }):
            result = router.ask(system="test", user="hello")
            assert result == "Hello world"


class TestRouteGenerateWithSystemPrompt:
    """A8: When system_prompt is provided, route_chat() is used for role separation."""

    def test_system_prompt_uses_chat_routing(self):
        """route_generate with system_prompt should call route_chat internally."""
        from src.providers.model_router import ModelRouter
        router = ModelRouter()
        with patch.object(router, "is_available", return_value=True), \
             patch.object(router, "route_chat", return_value={"success": True, "content": "hi", "provider": "test"}) as mock_chat:
            result = router.route_generate(
                prompt="hello",
                system_prompt="You are helpful",
                task_type="general",
            )
            assert mock_chat.called
            call_args = mock_chat.call_args
            messages = call_args[0][0] if call_args[0] else call_args.kwargs.get("messages", [])
            roles = [m["role"] for m in messages]
            assert "system" in roles
            assert "user" in roles