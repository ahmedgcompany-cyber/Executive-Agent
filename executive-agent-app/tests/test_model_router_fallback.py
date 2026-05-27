"""Audit fix verification — model_router fallback (C-04)."""

from __future__ import annotations

import pytest


@pytest.fixture()
def isolated_router(tmp_path, monkeypatch):
    """Isolate router settings file so prefer_uncensored stays default."""
    from src.providers import model_router as mr
    monkeypatch.setattr(mr.ModelRouter, "_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(mr.ModelRouter, "_CONFIG_FILE", str(tmp_path / "settings.json"))
    # Bust singleton so a fresh instance picks up the patched paths
    mr._instance = None
    yield mr
    mr._instance = None


def test_route_generate_no_provider_no_nameerror(isolated_router):
    """When all providers fail, must NOT raise NameError on `result`."""
    router = isolated_router.get_model_router()
    router._claude = None
    router._deepseek = None
    router._openrouter = None
    router.ollama_status = lambda: {"running": False, "has_model": False, "models": []}

    result = router.route_generate("hello", task_type="general")
    assert isinstance(result, dict)
    assert result.get("success") is False
    assert "error" in result
    assert result.get("provider") in (None, "none")


def test_route_chat_no_provider_no_nameerror(isolated_router):
    router = isolated_router.get_model_router()
    router._claude = None
    router._deepseek = None
    router._openrouter = None
    router.ollama_status = lambda: {"running": False, "has_model": False, "models": []}

    result = router.route_chat([{"role": "user", "content": "x"}], task_type="general")
    assert isinstance(result, dict)
    assert result.get("success") is False
    assert "error" in result


def test_prefer_uncensored_default_false(isolated_router):
    assert isolated_router.ModelRouter.get_prefer_uncensored() is False


def test_auto_pull_default_false(isolated_router):
    assert isolated_router.ModelRouter.get_auto_pull_enabled() is False


def test_cache_ttl_short(isolated_router):
    assert isolated_router.ModelRouter._CACHE_TTL == 10.0
