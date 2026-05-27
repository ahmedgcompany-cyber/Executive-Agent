"""
Finance Agent — invoicing, payment links, revenue tracking.
Every financial action goes through ApprovalGate. No exceptions.
"""

import asyncio
from ..tool_system.approval_gate import ApprovalGate
from ..integrations.payment_service import PaymentService


class FinanceAgent:

    def __init__(self, payment_service: PaymentService,
                 email_service=None, crm_service=None):
        self.payments = payment_service
        self.email    = email_service
        self.crm      = crm_service
        self.gate     = ApprovalGate()

    async def handle_finance_task(self, action: str, context: dict) -> dict:
        a = action.lower()
        if "invoice" in a or "bill" in a:
            return await self._invoice_flow(context)
        if "payment link" in a or "pay link" in a:
            return await self._payment_link_flow(context)
        if "revenue" in a or "summary" in a or "report" in a:
            return self._revenue_summary()
        if "status" in a or "paid" in a or "check" in a:
            return self._check_payments(context)
        return {"success": False, "error": f"Unknown finance action: {action}"}

    # ── Invoice flow ─────────────────────────────────────────────────

    async def _invoice_flow(self, context: dict) -> dict:
        email  = context.get("client_email") or context.get("email", "")
        name   = context.get("client_name")  or context.get("client", "Client")
        amount = context.get("amount")
        desc   = context.get("description", "Services rendered")

        if not email or not amount:
            return {"success": False, "error": "Need client_email and amount"}

        # ← HARD GATE — nothing executes without user click
        approved = self.gate.request_approval(
            action="create_invoice",
            details={"recipient": email, "amount": amount, "description": desc},
            risk_level="high",
        )
        if not approved:
            return {"success": False, "reason": "Rejected by user"}

        invoice = self.payments.create_invoice(email, name, float(amount), desc)

        if self.email:
            body = (
                f"Dear {name},\n\n"
                f"Please find your invoice here:\n{invoice['url']}\n\n"
                f"Amount due: ${float(amount):,.2f} USD\n"
                f"Due in {invoice['due_days']} days.\n\n"
                f"Thank you for your business."
            )
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.email.send(
                    to=email,
                    subject=f"Invoice — {desc}",
                    body=body,
                )
            )

        if self.crm:
            self.crm.log_activity(
                email=email,
                activity_type="invoice_sent",
                notes=f"Invoice {invoice['invoice_id']} for ${amount}",
            )

        return {
            "success":    True,
            "invoice_id": invoice["invoice_id"],
            "url":        invoice["url"],
            "amount":     amount,
            "sent_to":    email,
        }

    # ── Payment link flow ────────────────────────────────────────────

    async def _payment_link_flow(self, context: dict) -> dict:
        amount = context.get("amount")
        desc   = context.get("description", "Payment")
        approved = self.gate.request_approval(
            action="create_payment_link",
            details={"amount": amount, "description": desc},
            risk_level="medium",
        )
        if not approved:
            return {"success": False, "reason": "Rejected by user"}
        link = self.payments.create_payment_link(float(amount), desc)
        return {"success": True, "url": link["url"], "amount": amount}

    # ── Revenue / status ─────────────────────────────────────────────

    def _revenue_summary(self) -> dict:
        return {"success": True, "output": self.payments.get_revenue_summary()}

    def _check_payments(self, context: dict) -> dict:
        inv_id = context.get("invoice_id")
        if inv_id:
            status = self.payments.check_invoice_status(inv_id)
            return {"success": True, "invoice_id": inv_id, "status": status}
        return {"success": True, "payments": self.payments.list_recent_payments()}
