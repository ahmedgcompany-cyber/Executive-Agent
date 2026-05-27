"""
MegaV CRM Service — lightweight local contact & lead management.

Stores contacts in profiles/contacts.json.
No external database — fully local and portable.

Pipeline stages: New Lead → Contacted → Replied → Follow-Up Needed → Waiting → Closed
Contact categories: Recruiter | Client | Lead | Employer | Vendor | Collaborator | Personal
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from ..providers.model_router import NoModelAvailableError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STAGES = [
    "New Lead",
    "Contacted",
    "Replied",
    "Follow-Up Needed",
    "Waiting",
    "Closed",
]

CATEGORIES = [
    "Recruiter",
    "Client",
    "Lead",
    "Employer",
    "Vendor",
    "Collaborator",
    "Personal",
    "Other",
]

STORE_PATH = Path("profiles") / "contacts.json"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Interaction:
    date:        str
    kind:        str   # email_received | email_sent | note | call | meeting
    notes:       str   = ""
    email_id:    str   = ""
    subject:     str   = ""


@dataclass
class Contact:
    email:         str
    name:          str          = ""
    category:      str          = "Other"
    stage:         str          = "New Lead"
    tags:          list[str]    = field(default_factory=list)
    company:       str          = ""
    phone:         str          = ""
    linkedin:      str          = ""
    notes:         str          = ""
    interactions:  list[dict]   = field(default_factory=list)
    created_at:    str          = ""
    last_interaction: str       = ""
    next_action:   str          = ""
    follow_up_date: str         = ""
    is_archived:   bool         = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Contact":
        return cls(
            email          = d.get("email", ""),
            name           = d.get("name", ""),
            category       = d.get("category", "Other"),
            stage          = d.get("stage", "New Lead"),
            tags           = d.get("tags", []),
            company        = d.get("company", ""),
            phone          = d.get("phone", ""),
            linkedin       = d.get("linkedin", ""),
            notes          = d.get("notes", ""),
            interactions   = d.get("interactions", []),
            created_at     = d.get("created_at", ""),
            last_interaction = d.get("last_interaction", ""),
            next_action    = d.get("next_action", ""),
            follow_up_date = d.get("follow_up_date", ""),
            is_archived    = d.get("is_archived", False),
        )


# ---------------------------------------------------------------------------
# CRM Service
# ---------------------------------------------------------------------------

class CRMService:
    """Local JSON-backed contact and lead management system."""

    def __init__(self, store_path: Optional[str] = None):
        self._path = Path(store_path) if store_path else STORE_PATH
        self._contacts: dict[str, Contact] = {}
        self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save_contact(
        self,
        email:      str,
        name:       str = "",
        category:   str = "",
        stage:      str = "",
        company:    str = "",
        tags:       list[str] = None,
        notes:      str = "",
    ) -> dict:
        """Create or update a contact. Email is the primary key."""
        email = email.strip().lower()
        if not email:
            return {"success": False, "error": "Email is required."}

        existing = self._contacts.get(email)
        if existing:
            if name:
                existing.name = name
            if category and category in CATEGORIES:
                existing.category = category
            if stage and stage in STAGES:
                existing.stage = stage
            if company:
                existing.company = company
            if tags:
                for t in tags:
                    if t not in existing.tags:
                        existing.tags.append(t)
            if notes:
                existing.notes = notes
        else:
            existing = Contact(
                email      = email,
                name       = name,
                category   = category if category in CATEGORIES else "Other",
                stage      = stage    if stage    in STAGES    else "New Lead",
                company    = company,
                tags       = tags or [],
                notes      = notes,
                created_at = _today(),
            )
            self._contacts[email] = existing

        self._save()
        return {"success": True, "contact": existing.to_dict()}

    def get_contact(self, email: str) -> dict:
        email = email.strip().lower()
        c = self._contacts.get(email)
        if c:
            return {"success": True, "contact": c.to_dict()}
        return {"success": False, "error": f"Contact not found: {email}"}

    def delete_contact(self, email: str) -> dict:
        email = email.strip().lower()
        if email in self._contacts:
            del self._contacts[email]
            self._save()
            return {"success": True, "message": f"Deleted {email}"}
        return {"success": False, "error": "Contact not found."}

    def archive_contact(self, email: str) -> dict:
        email = email.strip().lower()
        c = self._contacts.get(email)
        if c:
            c.is_archived = True
            self._save()
            return {"success": True, "message": f"Archived {email}"}
        return {"success": False, "error": "Contact not found."}

    # ------------------------------------------------------------------
    # Query / list
    # ------------------------------------------------------------------

    def list_contacts(
        self,
        category:    str = "",
        stage:       str = "",
        tag:         str = "",
        include_archived: bool = False,
        limit:       int = 100,
    ) -> list[dict]:
        results = []
        for c in self._contacts.values():
            if not include_archived and c.is_archived:
                continue
            if category and c.category != category:
                continue
            if stage and c.stage != stage:
                continue
            if tag and tag not in c.tags:
                continue
            results.append(c.to_dict())
        results.sort(key=lambda x: x.get("last_interaction", "") or x.get("created_at", ""), reverse=True)
        return results[:limit]

    def get_follow_ups(self) -> list[dict]:
        """Return contacts that need follow-up (overdue or flagged)."""
        today = _today()
        results = []
        for c in self._contacts.values():
            if c.is_archived:
                continue
            needs_fu = (
                c.stage == "Follow-Up Needed"
                or (c.follow_up_date and c.follow_up_date <= today)
            )
            if needs_fu:
                results.append(c.to_dict())
        results.sort(key=lambda x: x.get("follow_up_date", "") or "", reverse=False)
        return results

    def search_contacts(self, query: str) -> list[dict]:
        q = query.lower()
        results = []
        for c in self._contacts.values():
            text = f"{c.email} {c.name} {c.company} {' '.join(c.tags)} {c.notes}".lower()
            if q in text:
                results.append(c.to_dict())
        return results

    # ------------------------------------------------------------------
    # Stage / tag management
    # ------------------------------------------------------------------

    def update_stage(self, email: str, stage: str) -> dict:
        if stage not in STAGES:
            return {"success": False, "error": f"Invalid stage. Valid: {STAGES}"}
        email = email.lower()
        c = self._contacts.get(email)
        if not c:
            return {"success": False, "error": "Contact not found."}
        c.stage = stage
        self._save()
        return {"success": True, "contact": c.to_dict()}

    def tag_contact(self, email: str, tags: list[str]) -> dict:
        email = email.lower()
        c = self._contacts.get(email)
        if not c:
            # Auto-create on tag
            self.save_contact(email)
            c = self._contacts[email]
        for t in tags:
            if t not in c.tags:
                c.tags.append(t)
        self._save()
        return {"success": True, "contact": c.to_dict()}

    def set_next_action(self, email: str, action: str, follow_up_days: int = 0) -> dict:
        email = email.lower()
        c = self._contacts.get(email)
        if not c:
            return {"success": False, "error": "Contact not found."}
        c.next_action = action
        if follow_up_days > 0:
            fu_date = (datetime.today() + timedelta(days=follow_up_days)).strftime("%Y-%m-%d")
            c.follow_up_date = fu_date
        self._save()
        return {"success": True, "contact": c.to_dict()}

    # ------------------------------------------------------------------
    # Interaction logging
    # ------------------------------------------------------------------

    def log_interaction(
        self,
        email:        str,
        kind:         str,
        notes:        str  = "",
        email_id:     str  = "",
        subject:      str  = "",
        auto_advance: bool = True,
    ) -> dict:
        """Record an interaction and optionally advance the pipeline stage."""
        email = email.strip().lower()
        if email not in self._contacts:
            self.save_contact(email)
        c = self._contacts[email]

        interaction = {
            "date":     _today(),
            "time":     _now(),
            "kind":     kind,
            "notes":    notes,
            "email_id": email_id,
            "subject":  subject,
        }
        c.interactions.append(interaction)
        c.last_interaction = _today()

        if auto_advance:
            if kind == "email_sent" and c.stage == "New Lead":
                c.stage = "Contacted"
            elif kind == "email_received" and c.stage in ("Contacted", "Waiting"):
                c.stage = "Replied"

        self._save()
        return {"success": True, "contact": c.to_dict()}

    # ------------------------------------------------------------------
    # Auto-extract contacts from emails
    # ------------------------------------------------------------------

    def extract_contacts_from_emails(self, emails: list[dict]) -> list[dict]:
        """
        Parse email messages and auto-create/update contacts.
        Returns list of new or updated contact dicts.
        """
        updated = []
        for msg in emails:
            s_email = msg.get("sender_email", "")
            s_name  = msg.get("sender", "")
            subject = msg.get("subject", "")
            email_id = msg.get("email_id", "")
            if not s_email or "@" not in s_email:
                continue

            # Guess category from classification if present
            cls = msg.get("classification", {})
            if cls.get("is_job_related"):
                cat = "Recruiter"
            elif cls.get("is_client_related"):
                cat = "Client"
            else:
                cat = "Other"

            result = self.save_contact(
                email=s_email,
                name=s_name,
                category=cat,
            )
            if result.get("success"):
                self.log_interaction(
                    email=s_email,
                    kind="email_received",
                    subject=subject,
                    email_id=email_id,
                    notes=f"Auto-imported from inbox.",
                )
                updated.append(result["contact"])

        return updated

    # ------------------------------------------------------------------
    # Draft follow-up message generator
    # ------------------------------------------------------------------

    def generate_followup_draft(
        self,
        email:        str,
        tone:         str        = "professional",
        user_profile: dict       = None,
        model_router: object     = None,
    ) -> dict:
        """Generate a follow-up message draft for a contact."""
        email = email.lower()
        c = self._contacts.get(email)
        if not c:
            return {"success": False, "error": "Contact not found."}

        profile   = user_profile or {}
        user_name = profile.get("name", "")
        name      = c.name.split()[0] if c.name else "there"

        if c.category == "Recruiter":
            subject = "Re: Following up on our conversation"
            body = (
                f"Hi {name},\n\n"
                "I wanted to follow up on our recent conversation. "
                "I'm still very interested in the opportunity and would love to hear about any updates.\n\n"
                f"Best regards,\n{user_name or 'Me'}"
            )
        elif c.category in ("Client", "Lead"):
            subject = "Following up on our discussion"
            body = (
                f"Hi {name},\n\n"
                "I hope you're doing well. I wanted to follow up on our previous discussion "
                "and see if you had any questions or if there's anything I can help with.\n\n"
                f"Best regards,\n{user_name or 'Me'}"
            )
        else:
            subject = "Checking in"
            body = (
                f"Hi {name},\n\nJust wanted to check in. "
                "Let me know if there's anything I can assist with.\n\n"
                f"Best regards,\n{user_name or 'Me'}"
            )

        # Upgrade with LLM if available
        if model_router:
            try:
                context = (
                    f"Contact: {c.name} ({c.category}), Stage: {c.stage}\n"
                    f"Last interaction: {c.last_interaction}\n"
                    f"Notes: {c.notes}\n"
                    f"Recent interactions: {len(c.interactions)}"
                )
                resp = model_router.ask(
                    system=(
                        f"You are writing a {tone} follow-up email. "
                        f"User's name: {user_name}. "
                        "Be concise. Output ONLY the email body."
                    ),
                    user=f"Contact context:\n{context}\n\nWrite a follow-up email:",
                    task_type="email",
                )
                if resp and len(resp.strip()) > 20:
                    body = resp.strip()
            except NoModelAvailableError:
                pass
            except Exception:
                pass

        return {
            "success": True,
            "subject": subject,
            "body":    body,
            "to":      email,
            "contact": c.to_dict(),
        }

    # ------------------------------------------------------------------
    # CRM summary
    # ------------------------------------------------------------------

    def get_pipeline_summary(self) -> dict:
        """Return a structured overview of the CRM pipeline."""
        stage_counts: dict[str, int] = {s: 0 for s in STAGES}
        cat_counts:   dict[str, int] = {}
        for c in self._contacts.values():
            if c.is_archived:
                continue
            stage_counts[c.stage] = stage_counts.get(c.stage, 0) + 1
            cat_counts[c.category] = cat_counts.get(c.category, 0) + 1
        follow_ups = self.get_follow_ups()
        return {
            "total_contacts": len([c for c in self._contacts.values() if not c.is_archived]),
            "by_stage":       stage_counts,
            "by_category":    cat_counts,
            "follow_ups_due": len(follow_ups),
            "follow_ups":     follow_ups[:5],
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for email_addr, data in raw.items():
                self._contacts[email_addr] = Contact.from_dict(data)
        except Exception:
            pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {email: c.to_dict() for email, c in self._contacts.items()}
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return date.today().isoformat()

def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_crm: Optional[CRMService] = None


def get_crm_service() -> CRMService:
    """Return the shared CRMService singleton."""
    global _crm
    if _crm is None:
        _crm = CRMService()
    return _crm
