"""Audit fix verification — profile_paths (C-02)."""

from __future__ import annotations

import json
from pathlib import Path


def test_profiles_dir_uses_env_override(sandbox_profiles):
    from src.integrations.profile_paths import profiles_dir
    assert profiles_dir() == sandbox_profiles


def test_template_seeded_when_target_missing(sandbox_profiles):
    from src.integrations.profile_paths import profiles_dir
    target = profiles_dir() / "user_profile.json"
    # Should auto-seed from repo template on first call
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    # Repo template is sanitized
    assert data["name"] == "Your Name"
    assert data["emails"] == []


def test_existing_user_data_not_overwritten(sandbox_profiles):
    from src.integrations.profile_paths import profile_file, profiles_dir
    # Pre-populate
    user_file = profiles_dir() / "user_profile.json"
    user_file.write_text(json.dumps({"name": "Real User"}), encoding="utf-8")
    # Subsequent resolve must not overwrite
    profiles_dir()
    data = json.loads(user_file.read_text(encoding="utf-8"))
    assert data["name"] == "Real User"


def test_profile_file_returns_absolute(sandbox_profiles):
    from src.integrations.profile_paths import profile_file
    p = profile_file("user_profile.json")
    assert p.is_absolute()
    assert p.parent == sandbox_profiles
