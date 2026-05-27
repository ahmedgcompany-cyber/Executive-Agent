"""Permission gating with audit logging.

Every check writes to logs/audit_log.jsonl regardless of outcome.
Default for unknown actions is 'ask' (deny silently is unsafe; allow silently
is also unsafe). All side-effecting actions default to 'ask' or 'deny'.
"""

from __future__ import annotations

import datetime
import json
import os
import threading
from pathlib import Path

import yaml


_AUDIT_LOCK = threading.Lock()


class PermissionManager:
    SAFE_DEFAULT = "ask"

    def __init__(self, permissions_file: str = "config/permissions.yaml",
                 audit_log: str = "logs/audit_log.jsonl"):
        self.permissions_file = Path(permissions_file)
        self.audit_log = Path(audit_log)
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
        self.permissions = {"permissions": {}}
        if self.permissions_file.exists():
            try:
                with open(self.permissions_file, "r", encoding="utf-8") as f:
                    self.permissions = yaml.safe_load(f) or {"permissions": {}}
            except Exception:
                self.permissions = {"permissions": {}}

    def check_permission(self, action: str, context: dict | None = None) -> bool:
        action_config = self.permissions.get("permissions", {}).get(action, {})
        setting = action_config.get("default", self.SAFE_DEFAULT)

        if setting == "allow":
            outcome = True
        elif setting == "deny":
            outcome = False
        elif setting == "ask":
            outcome = self.prompt_user(action, context)
        else:
            outcome = self.prompt_user(action, context)

        self._audit(action, setting, outcome, context)
        return outcome

    def prompt_user(self, action: str, context: dict | None) -> bool:
        # GUI override hook — main_window may patch this method.
        try:
            response = input(f"Allow {action}? (y/N): ")
        except EOFError:
            return False
        return response.strip().lower() == "y"

    def _audit(self, action: str, setting: str, outcome: bool,
               context: dict | None) -> None:
        entry = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "action": action,
            "setting": setting,
            "outcome": "allow" if outcome else "deny",
            "pid": os.getpid(),
            "context": context or {},
        }
        line = json.dumps(entry, default=str) + "\n"
        try:
            with _AUDIT_LOCK:
                with open(self.audit_log, "a", encoding="utf-8") as f:
                    f.write(line)
        except Exception:
            pass
