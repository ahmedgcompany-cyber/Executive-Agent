"""Audit fix verification — permissions defaults + audit log (H-01)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def pm(tmp_path):
    from src.tool_system.permissions import PermissionManager
    repo_root = Path(__file__).resolve().parent.parent
    return PermissionManager(
        permissions_file=str(repo_root / "config" / "permissions.yaml"),
        audit_log=str(tmp_path / "audit_log.jsonl"),
    )


def test_browser_navigation_defaults_ask(pm):
    assert pm.permissions["permissions"]["browser_navigation"]["default"] == "ask"


def test_desktop_app_launch_defaults_ask(pm):
    assert pm.permissions["permissions"]["desktop_app_launch"]["default"] == "ask"


def test_desktop_screenshot_defaults_ask(pm):
    assert pm.permissions["permissions"]["desktop_screenshot"]["default"] == "ask"


def test_skill_auto_update_defaults_deny(pm):
    assert pm.permissions["permissions"]["skill_auto_update"]["default"] == "deny"


def test_unknown_action_defaults_to_safe(pm):
    """Unknown actions must fall through to SAFE_DEFAULT (= 'ask'), never 'allow'."""
    from src.tool_system.permissions import PermissionManager
    assert PermissionManager.SAFE_DEFAULT == "ask"


def test_audit_log_writes_per_check(pm, tmp_path):
    # Inject a 'deny' action so prompt_user is not invoked during the test
    pm.permissions["permissions"]["__test_deny"] = {"default": "deny"}
    outcome = pm.check_permission("__test_deny", {"reason": "unit test"})
    assert outcome is False

    audit_path = Path(pm.audit_log)
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines, "audit log should have at least one entry"
    entry = json.loads(lines[-1])
    assert entry["action"] == "__test_deny"
    assert entry["outcome"] == "deny"
    assert entry["context"] == {"reason": "unit test"}


def test_audit_log_records_allow_outcomes(pm):
    pm.permissions["permissions"]["__test_allow"] = {"default": "allow"}
    pm.check_permission("__test_allow")
    audit_path = Path(pm.audit_log)
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    last = json.loads(lines[-1])
    assert last["outcome"] == "allow"
