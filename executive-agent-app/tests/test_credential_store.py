"""Audit fix verification — credential_store (H-02 + cred-store path fix)."""

from __future__ import annotations

import pytest


def test_fernet_round_trip(sandbox_profiles):
    from src.integrations.credential_store import _encrypt, _decrypt
    ct = _encrypt("super-secret")
    assert ct.startswith("fernet:")
    assert _decrypt(ct) == "super-secret"


def test_xor_legacy_refused(sandbox_profiles):
    """Legacy XOR-encoded values must NOT decrypt — refusal is the security guarantee."""
    from src.integrations.credential_store import _decrypt
    # Real XOR ciphertext format: xor:<base64>
    out = _decrypt("xor:AAAAAA==")
    assert out == ""


def test_credentials_save_and_load(sandbox_profiles):
    from src.integrations.credential_store import CredentialStore
    store = CredentialStore()
    store.save("svc-a", "key1", "value1")
    assert store.load("svc-a", "key1") == "value1"


def test_save_many_round_trip(sandbox_profiles):
    from src.integrations.credential_store import CredentialStore
    store = CredentialStore()
    store.save_many("svc-b", {"token": "tok-X", "username": "alice"})
    assert store.load("svc-b", "token") == "tok-X"
    assert store.load("svc-b", "username") == "alice"


def test_default_dir_is_user_scoped(sandbox_profiles, tmp_path):
    """Default CredentialStore dir must resolve to user-scoped APPDATA, never repo."""
    from src.integrations.credential_store import CredentialStore
    store = CredentialStore()
    assert str(store._dir).startswith(str(sandbox_profiles))


def test_unknown_format_returns_as_is(sandbox_profiles):
    from src.integrations.credential_store import _decrypt
    assert _decrypt("plain-legacy-value") == "plain-legacy-value"
    assert _decrypt("") == ""
