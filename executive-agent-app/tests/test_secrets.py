"""Audit fix verification — secrets module (C-01)."""

from __future__ import annotations

import os


def test_env_var_beats_credential_store(sandbox_profiles, monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_env_value")
    from src.integrations.secrets import get_stripe_key, set_stripe_key
    set_stripe_key("sk_keystore_value")
    assert get_stripe_key() == "sk_env_value"


def test_credential_store_when_env_empty(sandbox_profiles, monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    from src.integrations.secrets import get_stripe_key, set_stripe_key
    set_stripe_key("sk_keystore_only")
    assert get_stripe_key() == "sk_keystore_only"


def test_returns_empty_when_unset(sandbox_profiles, monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    from src.integrations.secrets import get_stripe_key
    # Fresh sandbox: no stored key
    assert get_stripe_key() == ""


def test_get_secret_strips_whitespace(sandbox_profiles, monkeypatch):
    monkeypatch.setenv("FOO_KEY", "  spaced-value  ")
    from src.integrations.secrets import get_secret
    assert get_secret("FOO_KEY", "foo") == "spaced-value"
