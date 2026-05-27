"""Shared pytest fixtures for the new audit-fix test suite."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture()
def sandbox_profiles(monkeypatch, tmp_path: Path):
    """Sandbox MEGAV_PROFILES_DIR + reset CredentialStore singleton."""
    sandbox = tmp_path / "megav_profiles"
    sandbox.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MEGAV_PROFILES_DIR", str(sandbox))

    # Reset CredentialStore singleton so it picks up the new dir
    from src.integrations import credential_store as cs
    cs._store = None
    yield sandbox
    cs._store = None
