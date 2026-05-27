"""
Payment Service — Stripe API wrapper.
All methods that move money MUST have ApprovalGate called BEFORE invocation.
The FinanceAgent handles this — never call PaymentService directly from agents.
"""

import time
from datetime import datetime


class PaymentService:

    def __init__(self, api_key: str):
        import stripe
        stripe.api_key = api_key
        self._s = stripe

    # ── Customers ────────────────────────────────────────────────────

    def get_or_create_customer(self, email: str, name: str = "") -> str:
        existing = self._s.Customer.list(email=email, limit=1)
        if existing.data:
            return existing.data[0].id
        return self._s.Customer.create(email=email, name=name).id

    # ── Invoices ─────────────────────────────────────────────────────

    def create_invoice(self, client_email: str, client_name: str,
                       amount_usd: float, description: str,
                       due_days: int = 7) -> dict:
        """Create and finalize a Stripe invoice. Returns hosted URL."""
        cid = self.get_or_create_customer(client_email, client_name)
        self._s.InvoiceItem.create(
            customer=cid,
            amount=int(amount_usd * 100),
            currency="usd",
            description=description,
        )
        inv = self._s.Invoice.create(
            customer=cid,
            collection_method="send_invoice",
            days_until_due=due_days,
            auto_advance=True,
        )
        inv = self._s.Invoice.finalize_invoice(inv.id)
        return {
            "invoice_id": inv.id,
            "url":        inv.hosted_invoice_url,
            "pdf":        inv.invoice_pdf,
            "amount":     amount_usd,
            "status":     inv.status,
            "due_days":   due_days,
        }

    def create_payment_link(self, amount_usd: float, description: str) -> dict:
        """Create a one-time Stripe payment link."""
        price = self._s.Price.create(
            unit_amount=int(amount_usd * 100),
            currency="usd",
            product_data={"name": description},
        )
        link = self._s.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}]
        )
        return {"url": link.url, "amount": amount_usd}

    # ── Status ───────────────────────────────────────────────────────

    def check_invoice_status(self, invoice_id: str) -> str:
        return self._s.Invoice.retrieve(invoice_id).status

    def list_recent_payments(self, days: int = 30) -> list:
        since = int(time.time()) - (days * 86400)
        charges = self._s.Charge.list(created={"gte": since}, limit=100)
        return [
            {
                "id":     c.id,
                "amount": c.amount / 100,
                "desc":   c.description,
                "status": c.status,
                "date":   datetime.fromtimestamp(c.created).strftime("%Y-%m-%d"),
                "email":  c.billing_details.email,
            }
            for c in charges.data if c.status == "succeeded"
        ]

    def get_revenue_summary(self) -> dict:
        now        = datetime.now()
        month_start = int(datetime(now.year, now.month, 1).timestamp())
        charges    = self._s.Charge.list(created={"gte": month_start}, limit=100)
        paid       = sum(c.amount for c in charges.data if c.status == "succeeded") / 100
        open_invs  = self._s.Invoice.list(status="open", limit=100)
        pending    = sum(i.amount_due for i in open_invs.data) / 100
        overdue    = sum(
            i.amount_due for i in open_invs.data
            if i.due_date and i.due_date < time.time()
        ) / 100
        return {
            "paid_this_month": paid,
            "pending":         pending,
            "overdue":         overdue,
            "currency":        "USD",
        }
