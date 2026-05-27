"""
Approval Gate — hard block on all financial actions.
NOTHING involving money executes without explicit user approval.
Every decision is logged to ~/.megav/audit_log.jsonl.
"""

import json
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from pathlib import Path

AUDIT_LOG = Path.home() / ".megav" / "audit_log.jsonl"

FINANCIAL_KEYWORDS = [
    "payment", "invoice", "transfer", "deposit", "withdraw",
    "stripe", "paypal", "send_money", "charge", "bill",
    "bank", "wire", "subscription", "refund", "payout",
]


class ApprovalGate:
    """Blocks financial actions until user clicks Approve in a popup."""

    def is_financial(self, action: str) -> bool:
        return any(kw in action.lower() for kw in FINANCIAL_KEYWORDS)

    def request_approval(self, action: str, details: dict,
                         risk_level: str = "high") -> bool:
        """
        Show blocking popup. Returns True if approved, False if rejected.
        ALWAYS logs the decision regardless of outcome.
        """
        amount    = details.get("amount", "")
        recipient = details.get("recipient") or details.get("client_email", "")
        desc      = details.get("description", "")

        lines = ["⚠  FINANCIAL ACTION — APPROVAL REQUIRED\n"]
        lines.append(f"Action:      {action}")
        if amount:
            amt_str = f"${amount:,.2f} USD" if isinstance(amount, (int, float)) else str(amount)
            lines.append(f"Amount:      {amt_str}")
        if recipient:
            lines.append(f"Recipient:   {recipient}")
        if desc:
            lines.append(f"Description: {desc}")
        lines.append(f"\nRisk level:  {risk_level.upper()}")
        lines.append("\nApprove this action?")

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        approved = messagebox.askyesno(
            "MegaV — Approval Required",
            "\n".join(lines),
            icon="warning",
        )
        root.destroy()
        self._log(action, details, approved)
        return approved

    def _log(self, action: str, details: dict, approved: bool) -> None:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action":    action,
            "details":   details,
            "approved":  approved,
        }
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_audit_log(self, last_n: int = 100) -> list:
        if not AUDIT_LOG.exists():
            return []
        lines = AUDIT_LOG.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(ln) for ln in lines[-last_n:] if ln.strip()]
