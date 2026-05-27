"""
MegaV Email Service — full IMAP/SMTP multi-account email automation.

Supports Gmail, Outlook/Hotmail, Yahoo, and any custom IMAP/SMTP provider.
Uses only Python stdlib (imaplib, smtplib, email) — zero extra dependencies.

Security:
  - Passwords are NEVER stored in plain text.
  - All credentials delegated to CredentialStore (encrypted on disk).
  - Passwords masked in all log output and error messages.
  - App Passwords recommended for Gmail / Outlook with 2FA.

Email ID format:  "{account_email}::{uid}"  — routes actions to the right account.
"""

from __future__ import annotations

import email as _email_pkg
import email.header
import email.mime.multipart
import email.mime.text
import imaplib
import logging
import re
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path
from typing import Optional

from ..providers.model_router import NoModelAvailableError

_log = logging.getLogger("megav.email")


# ---------------------------------------------------------------------------
# Provider configs
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict] = {
    "gmail": {
        "name":       "Gmail",
        "imap_host":  "imap.gmail.com",
        "imap_port":  993,
        "smtp_host":  "smtp.gmail.com",
        "smtp_port":  587,
        "note":       "Use an App Password. Enable IMAP in Gmail settings.",
    },
    "outlook": {
        "name":       "Outlook / Hotmail",
        "imap_host":  "outlook.office365.com",
        "imap_port":  993,
        "smtp_host":  "smtp.office365.com",
        "smtp_port":  587,
        "note":       "Use an App Password if MFA is enabled.",
    },
    "yahoo": {
        "name":       "Yahoo Mail",
        "imap_host":  "imap.mail.yahoo.com",
        "imap_port":  993,
        "smtp_host":  "smtp.mail.yahoo.com",
        "smtp_port":  587,
        "note":       "Enable 'Less secure app access' or use an App Password.",
    },
    "custom": {
        "name":       "Custom IMAP / SMTP",
        "imap_host":  "",
        "imap_port":  993,
        "smtp_host":  "",
        "smtp_port":  587,
        "note":       "Enter your server details manually.",
    },
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EmailAccount:
    account_id:  str         # unique key — typically the email address
    email:       str
    provider:    str         # gmail | outlook | yahoo | custom
    imap_host:   str
    imap_port:   int
    smtp_host:   str
    smtp_port:   int
    display_name: str = ""
    connected:   bool = False
    last_error:  str  = ""
    inbox_count: int  = 0


@dataclass
class EmailMessage:
    uid:         str
    account:     str
    subject:     str
    sender:      str
    sender_email: str
    recipients:  list[str]
    date:        str
    body_plain:  str
    body_html:   str = ""
    is_read:     bool = False
    has_attachments: bool = False
    attachments: list[dict] = field(default_factory=list)
    raw_headers: dict = field(default_factory=dict)

    @property
    def email_id(self) -> str:
        return f"{self.account}::{self.uid}"

    def to_dict(self) -> dict:
        return {
            "email_id":    self.email_id,
            "uid":         self.uid,
            "account":     self.account,
            "subject":     self.subject,
            "sender":      self.sender,
            "sender_email": self.sender_email,
            "recipients":  self.recipients,
            "date":        self.date,
            "body_plain":  self.body_plain[:2000],
            "body_html":   self.body_html[:2000],
            "is_read":     self.is_read,
            "has_attachments": self.has_attachments,
        }


# ---------------------------------------------------------------------------
# IMAP helpers
# ---------------------------------------------------------------------------

def _decode_header(value: str) -> str:
    """Decode RFC2047 encoded email header."""
    if not value:
        return ""
    try:
        parts = email.header.decode_header(value)
        decoded = []
        for raw, charset in parts:
            if isinstance(raw, bytes):
                decoded.append(raw.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(str(raw))
        return " ".join(decoded)
    except Exception:
        return str(value)


def _extract_body(msg) -> tuple[str, str]:
    """Extract plain text and HTML body from a parsed email message."""
    plain = ""
    html  = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if ct == "text/plain" and not plain:
                    plain = text
                elif ct == "text/html" and not html:
                    html = text
            except Exception:
                continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    html = text
                else:
                    plain = text
        except Exception:
            pass
    return plain, html


def _extract_attachments(msg) -> tuple[bool, list[dict]]:
    """Extract attachment metadata from a parsed email."""
    attachments = []
    if not msg.is_multipart():
        return False, []
    for part in msg.walk():
        cd = str(part.get("Content-Disposition", ""))
        if "attachment" in cd:
            filename = part.get_filename() or "attachment"
            filename = _decode_header(filename)
            attachments.append({
                "filename":     filename,
                "content_type": part.get_content_type(),
                "size":         len(part.get_payload(decode=True) or b""),
            })
    return bool(attachments), attachments


def _parse_raw_email(uid: str, account_email: str, raw_bytes: bytes) -> EmailMessage:
    """Parse raw RFC822 bytes into an EmailMessage object."""
    msg = _email_pkg.message_from_bytes(raw_bytes)

    subject       = _decode_header(msg.get("Subject", "(no subject)"))
    from_raw      = _decode_header(msg.get("From", ""))
    display_name, sender_email = parseaddr(from_raw)
    date_str      = msg.get("Date", "")
    to_raw        = msg.get("To", "")
    recipients    = [a.strip() for a in to_raw.split(",") if a.strip()]
    plain, html   = _extract_body(msg)
    has_att, atts = _extract_attachments(msg)

    return EmailMessage(
        uid           = uid,
        account       = account_email,
        subject       = subject,
        sender        = display_name or sender_email,
        sender_email  = sender_email,
        recipients    = recipients,
        date          = date_str,
        body_plain    = plain.strip(),
        body_html     = html.strip(),
        is_read       = False,  # caller fills this from flags
        has_attachments = has_att,
        attachments   = atts,
        raw_headers   = {k: v for k, v in msg.items()},
    )


# ---------------------------------------------------------------------------
# EmailService
# ---------------------------------------------------------------------------

class EmailService:
    """
    Multi-account email manager using IMAP (read) and SMTP (send).

    All public methods return::

        {"success": True/False, "error": "...", ...payload...}
    """

    def __init__(self):
        self._accounts: dict[str, EmailAccount] = {}  # email -> EmailAccount
        self._imap_conns: dict[str, imaplib.IMAP4_SSL] = {}
        self._cred_store = None   # lazy-loaded

        # Load persisted account configs (no passwords — just metadata)
        self._load_account_metadata()

    # ------------------------------------------------------------------
    # Credential store (lazy)
    # ------------------------------------------------------------------

    def _creds(self):
        if self._cred_store is None:
            from .credential_store import get_credential_store
            self._cred_store = get_credential_store()
        return self._cred_store

    def _service_key(self, email_addr: str) -> str:
        return f"email_{email_addr.replace('@', '_at_').replace('.', '_')}"

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------

    def add_account(
        self,
        email_addr:   str,
        password:     str,
        provider:     str = "gmail",
        display_name: str = "",
        imap_host:    str = "",
        imap_port:    int = 0,
        smtp_host:    str = "",
        smtp_port:    int = 0,
    ) -> dict:
        """Add and verify a new email account. Password stored encrypted."""
        email_addr = email_addr.strip().lower()
        if not email_addr or not password:
            return {"success": False, "error": "Email and password are required."}

        # Resolve provider defaults
        pconf = PROVIDERS.get(provider, PROVIDERS["custom"])
        resolved_imap_host = imap_host or pconf["imap_host"]
        resolved_imap_port = imap_port or pconf["imap_port"]
        resolved_smtp_host = smtp_host or pconf["smtp_host"]
        resolved_smtp_port = smtp_port or pconf["smtp_port"]

        if not resolved_imap_host:
            return {"success": False, "error": "IMAP host is required for custom provider."}

        # Test IMAP connection first
        test = self._test_imap(email_addr, password, resolved_imap_host, resolved_imap_port)
        if not test["success"]:
            return test

        # Save encrypted password
        svc_key = self._service_key(email_addr)
        self._creds().save_many(svc_key, {
            "password":  password,
            "imap_host": resolved_imap_host,
            "imap_port": str(resolved_imap_port),
            "smtp_host": resolved_smtp_host,
            "smtp_port": str(resolved_smtp_port),
            "provider":  provider,
            "display_name": display_name or email_addr.split("@")[0],
        })

        account = EmailAccount(
            account_id   = email_addr,
            email        = email_addr,
            provider     = provider,
            imap_host    = resolved_imap_host,
            imap_port    = resolved_imap_port,
            smtp_host    = resolved_smtp_host,
            smtp_port    = resolved_smtp_port,
            display_name = display_name or email_addr.split("@")[0],
            connected    = True,
        )
        self._accounts[email_addr] = account
        self._save_account_metadata()

        return {"success": True, "message": f"Connected {email_addr} successfully.", "email": email_addr}

    def remove_account(self, email_addr: str) -> dict:
        """Disconnect and remove an account."""
        email_addr = email_addr.lower()
        self._close_imap(email_addr)
        self._creds().delete(self._service_key(email_addr))
        self._accounts.pop(email_addr, None)
        self._save_account_metadata()
        return {"success": True, "message": f"Removed {email_addr}."}

    def get_accounts(self) -> list[dict]:
        """Return all registered account summaries."""
        return [
            {
                "email":        a.email,
                "provider":     a.provider,
                "display_name": a.display_name,
                "connected":    a.connected,
                "inbox_count":  a.inbox_count,
                "last_error":   a.last_error,
            }
            for a in self._accounts.values()
        ]

    def is_connected(self, email_addr: str = "") -> bool:
        """Return True if at least one (or the specified) account is connected."""
        if email_addr:
            acc = self._accounts.get(email_addr.lower())
            return acc is not None and acc.connected
        return any(a.connected for a in self._accounts.values())

    def connection_status(self) -> dict:
        """Return full connection status for all accounts."""
        return {
            "accounts":  self.get_accounts(),
            "connected": self.is_connected(),
            "count":     len(self._accounts),
        }

    # ------------------------------------------------------------------
    # Read emails
    # ------------------------------------------------------------------

    def get_inbox(self, email_addr: str = "", limit: int = 20, folder: str = "INBOX") -> dict:
        """Fetch the most recent emails from INBOX."""
        account = self._resolve_account(email_addr)
        if not account:
            return self._no_account_err()

        try:
            conn = self._get_imap(account)
            conn.select(folder, readonly=True)
            _, data = conn.search(None, "ALL")
            uids = (data[0].split() if data[0] else [])
            # Most recent first
            uids = uids[-limit:][::-1]

            messages = []
            for uid in uids:
                try:
                    _, raw = conn.fetch(uid, "(RFC822 FLAGS)")
                    if not raw or not raw[0]:
                        continue
                    raw_bytes = raw[0][1] if isinstance(raw[0], tuple) else raw[0]
                    msg = _parse_raw_email(uid.decode(), account.email, raw_bytes)
                    # Determine read status from FLAGS
                    flags_str = str(raw[0][0] if isinstance(raw[0], tuple) else b"")
                    msg.is_read = "\\Seen" in flags_str
                    messages.append(msg.to_dict())
                except Exception:
                    continue

            account.inbox_count = len(messages)
            return {"success": True, "messages": messages, "count": len(messages), "account": account.email}

        except Exception as exc:
            account.connected = False
            account.last_error = str(exc)
            return {"success": False, "error": f"IMAP error: {exc}"}

    def read_email(self, email_id: str) -> dict:
        """Fetch and return the full content of a single email."""
        account_email, uid = self._parse_email_id(email_id)
        if not account_email:
            return {"success": False, "error": f"Invalid email_id format: {email_id}"}
        account = self._accounts.get(account_email)
        if not account:
            return {"success": False, "error": f"No account for {account_email}"}
        try:
            conn = self._get_imap(account)
            conn.select("INBOX", readonly=False)
            _, raw = conn.fetch(uid.encode(), "(RFC822 FLAGS)")
            if not raw or not raw[0]:
                return {"success": False, "error": "Email not found."}
            raw_bytes = raw[0][1] if isinstance(raw[0], tuple) else raw[0]
            msg = _parse_raw_email(uid, account.email, raw_bytes)
            # Mark as read
            conn.store(uid.encode(), "+FLAGS", "\\Seen")
            msg.is_read = True
            return {"success": True, "email": msg.to_dict()}
        except Exception as exc:
            return {"success": False, "error": f"Read error: {exc}"}

    def search_emails(self, query: str, email_addr: str = "", limit: int = 20) -> dict:
        """Search emails by IMAP SEARCH criteria or plain-text subject/from."""
        account = self._resolve_account(email_addr)
        if not account:
            return self._no_account_err()
        try:
            conn = self._get_imap(account)
            conn.select("INBOX", readonly=True)
            # Build IMAP search criteria
            criteria = self._build_search_criteria(query)
            _, data  = conn.search(None, criteria)
            uids = data[0].split() if data[0] else []
            uids = uids[-limit:][::-1]
            messages = []
            for uid in uids:
                try:
                    _, raw = conn.fetch(uid, "(RFC822)")
                    raw_bytes = raw[0][1] if isinstance(raw[0], tuple) else raw[0]
                    msg = _parse_raw_email(uid.decode(), account.email, raw_bytes)
                    messages.append(msg.to_dict())
                except Exception:
                    continue
            return {"success": True, "messages": messages, "count": len(messages), "query": query}
        except Exception as exc:
            return {"success": False, "error": f"Search error: {exc}"}

    def get_email_thread(self, email_id: str) -> dict:
        """Retrieve all messages in the same thread (by subject)."""
        result = self.read_email(email_id)
        if not result.get("success"):
            return result
        subject = result["email"].get("subject", "")
        # Strip Re: / Fwd: prefixes
        clean = re.sub(r"^(Re:|Fwd?:)\s*", "", subject, flags=re.IGNORECASE).strip()
        return self.search_emails(f"SUBJECT \"{clean}\"")

    # ------------------------------------------------------------------
    # Send / Reply
    # ------------------------------------------------------------------

    def send_email(
        self,
        to:           str | list[str],
        subject:      str,
        body:         str,
        from_account: str = "",
        html_body:    str = "",
        cc:           str | list[str] = "",
        bcc:          str | list[str] = "",
    ) -> dict:
        """Compose and send an email via SMTP."""
        account = self._resolve_account(from_account)
        if not account:
            return self._no_account_err()

        password = self._creds().load(self._service_key(account.email), "password")
        if not password:
            return {"success": False, "error": "No stored password for this account."}

        to_list  = [to]  if isinstance(to, str)  else to
        cc_list  = [cc]  if isinstance(cc, str) and cc  else (cc or [])
        bcc_list = [bcc] if isinstance(bcc, str) and bcc else (bcc or [])

        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["From"]    = f"{account.display_name} <{account.email}>"
        msg["To"]      = ", ".join(to_list)
        msg["Date"]    = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=account.email.split("@")[-1])
        msg["Subject"] = subject
        if cc_list:
            msg["Cc"]  = ", ".join(cc_list)

        msg.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))
        if html_body:
            msg.attach(email.mime.text.MIMEText(html_body, "html", "utf-8"))

        all_recipients = to_list + cc_list + bcc_list

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(account.smtp_host, account.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(account.email, password)
                server.sendmail(account.email, all_recipients, msg.as_bytes())
            return {
                "success": True,
                "message": f"Email sent to {', '.join(to_list)} from {account.email}.",
                "to":      to_list,
                "subject": subject,
            }
        except smtplib.SMTPAuthenticationError:
            return {"success": False, "error": "Authentication failed. Check your app password."}
        except Exception as exc:
            return {"success": False, "error": f"SMTP error: {exc}"}

    def reply_email(self, email_id: str, body: str, from_account: str = "") -> dict:
        """Reply to an existing email thread."""
        result = self.read_email(email_id)
        if not result.get("success"):
            return {"success": False, "error": "Could not read original email to reply."}

        orig = result["email"]
        reply_to = orig["sender_email"] or orig["sender"]
        subject  = orig["subject"]
        if not subject.lower().startswith("re:"):
            subject = "Re: " + subject

        # Quote original body
        quoted = "\n".join(f"> {line}" for line in orig["body_plain"].splitlines()[:20])
        full_body = f"{body}\n\n---\nOriginal message:\n{quoted}"

        # Add In-Reply-To / References headers if possible
        return self.send_email(
            to           = reply_to,
            subject      = subject,
            body         = full_body,
            from_account = from_account or orig["account"],
        )

    # ------------------------------------------------------------------
    # Manage emails
    # ------------------------------------------------------------------

    def mark_as_read(self, email_id: str) -> dict:
        return self._set_flag(email_id, "+FLAGS", "\\Seen", "Marked as read.")

    def mark_as_unread(self, email_id: str) -> dict:
        return self._set_flag(email_id, "-FLAGS", "\\Seen", "Marked as unread.")

    def archive_email(self, email_id: str) -> dict:
        """Move email to [Gmail]/All Mail or Archive folder."""
        account_email, uid = self._parse_email_id(email_id)
        account = self._accounts.get(account_email)
        if not account:
            return {"success": False, "error": "Account not found."}
        try:
            conn = self._get_imap(account)
            conn.select("INBOX")
            # Try Gmail archive label first, fall back to flag
            if account.provider == "gmail":
                conn.copy(uid.encode(), "[Gmail]/All Mail")
                conn.store(uid.encode(), "+FLAGS", "\\Deleted")
                conn.expunge()
            else:
                conn.store(uid.encode(), "+FLAGS", "\\Deleted")
                conn.expunge()
            return {"success": True, "message": "Email archived."}
        except Exception as exc:
            return {"success": False, "error": f"Archive error: {exc}"}

    def delete_email(self, email_id: str) -> dict:
        return self._set_flag(email_id, "+FLAGS", "\\Deleted", "Email deleted.",
                              expunge=True)

    def download_attachment(self, email_id: str, filename: str, save_dir: str = "") -> dict:
        """Download a named attachment from an email to disk."""
        result = self.read_email(email_id)
        if not result.get("success"):
            return result
        account_email, uid = self._parse_email_id(email_id)
        account = self._accounts.get(account_email)
        if not account:
            return {"success": False, "error": "Account not found."}
        try:
            conn = self._get_imap(account)
            conn.select("INBOX", readonly=True)
            _, raw = conn.fetch(uid.encode(), "(RFC822)")
            raw_bytes = raw[0][1] if isinstance(raw[0], tuple) else raw[0]
            msg = _email_pkg.message_from_bytes(raw_bytes)

            target_dir = Path(save_dir) if save_dir else Path.home() / "Downloads"
            target_dir.mkdir(parents=True, exist_ok=True)

            for part in msg.walk():
                cd = str(part.get("Content-Disposition", ""))
                if "attachment" not in cd:
                    continue
                part_name = _decode_header(part.get_filename() or "")
                if filename.lower() in part_name.lower():
                    data = part.get_payload(decode=True)
                    out  = target_dir / part_name
                    out.write_bytes(data)
                    return {"success": True, "path": str(out), "filename": part_name}
            return {"success": False, "error": f"Attachment '{filename}' not found."}
        except Exception as exc:
            return {"success": False, "error": f"Download error: {exc}"}

    # ------------------------------------------------------------------
    # Smart Inbox — AI classification
    # ------------------------------------------------------------------

    def classify_email(self, email_dict: dict) -> dict:
        """
        Heuristic classification of an email.

        Returns a dict with:
          category, priority, needs_reply, suggested_action, is_spam
        """
        subject  = (email_dict.get("subject") or "").lower()
        sender   = (email_dict.get("sender")  or "").lower()
        s_email  = (email_dict.get("sender_email") or "").lower()
        body     = (email_dict.get("body_plain") or "").lower()[:1000]
        combined = subject + " " + body

        # Spam / notification signals
        spam_signals = [
            "unsubscribe", "no-reply", "noreply", "donotreply",
            "newsletter", "offer", "deal", "discount", "sale",
            "congratulations you", "you have won", "click here",
        ]
        notification_signals = [
            "notification", "alert", "reminder", "automated message",
            "do not reply", "github.com", "gitlab.com", "jira",
        ]
        job_signals  = [
            "recruiter", "hiring", "position", "role", "opportunity",
            "job offer", "interview", "application", "cv", "resume",
            "linkedin recruiter",
        ]
        client_signals = [
            "invoice", "proposal", "contract", "payment", "project",
            "deliverable", "milestone", "client", "quote", "rate",
        ]
        urgent_signals = [
            "urgent", "asap", "immediately", "deadline",
            "action required", "important", "critical",
        ]

        is_spam = any(s in combined for s in spam_signals)
        is_notification = any(s in combined for s in notification_signals)
        is_job    = any(s in combined for s in job_signals)
        is_client = any(s in combined for s in client_signals)
        is_urgent = any(s in combined for s in urgent_signals)

        # Category
        if is_job:
            category = "Job Applications"
        elif is_client:
            category = "Work"
        elif is_spam:
            category = "Spam / Low Value"
        elif is_notification:
            category = "Notifications"
        elif "personal" in combined or any(x in s_email for x in ["gmail.com", "hotmail.com", "yahoo.com", "icloud.com"]):
            category = "Personal"
        else:
            category = "Work"

        # Priority
        if is_urgent:
            priority = "Urgent"
        elif is_job:
            priority = "High"
        elif is_client:
            priority = "High"
        elif is_spam:
            priority = "Low"
        elif is_notification:
            priority = "Low"
        else:
            priority = "Normal"

        # Needs reply?
        question_patterns = [r"\?", "please reply", "please confirm", "let me know",
                             "get back to me", "your thoughts", "feedback"]
        needs_reply = any(p in combined for p in question_patterns) and not is_spam

        # Suggested action
        if is_job and needs_reply:
            action = "Draft a professional recruiter reply"
        elif is_client and needs_reply:
            action = "Draft a client response"
        elif is_urgent:
            action = "Reply immediately — marked urgent"
        elif is_spam:
            action = "Archive or unsubscribe"
        elif is_notification:
            action = "Review notification — no reply needed"
        else:
            action = "Review email"

        return {
            "category":         category,
            "priority":         priority,
            "needs_reply":      needs_reply,
            "is_spam":          is_spam,
            "is_notification":  is_notification,
            "is_job_related":   is_job,
            "is_client_related": is_client,
            "is_urgent":        is_urgent,
            "suggested_action": action,
        }

    def classify_inbox(self, email_addr: str = "", limit: int = 30) -> dict:
        """Fetch inbox and return all emails with AI classification."""
        result = self.get_inbox(email_addr, limit=limit)
        if not result.get("success"):
            return result
        classified = []
        for msg in result["messages"]:
            cls = self.classify_email(msg)
            classified.append({**msg, "classification": cls})
        return {
            "success":  True,
            "messages": classified,
            "count":    len(classified),
            "urgent_count":    sum(1 for m in classified if m["classification"]["priority"] == "Urgent"),
            "needs_reply_count": sum(1 for m in classified if m["classification"]["needs_reply"]),
        }

    def get_smart_summary(self, email_addr: str = "", limit: int = 20) -> dict:
        """Return a plain-language summary of the inbox state."""
        result = self.classify_inbox(email_addr, limit=limit)
        if not result.get("success"):
            return result
        msgs = result["messages"]
        urgent = [m for m in msgs if m["classification"]["priority"] == "Urgent"]
        replies_needed = [m for m in msgs if m["classification"]["needs_reply"]]
        jobs = [m for m in msgs if m["classification"]["is_job_related"]]
        lines = [
            f"Inbox: {result['count']} email(s) checked.",
        ]
        if urgent:
            lines.append(f"  {len(urgent)} URGENT — {', '.join(m['subject'][:40] for m in urgent[:3])}")
        if replies_needed:
            lines.append(f"  {len(replies_needed)} need a reply.")
        if jobs:
            lines.append(f"  {len(jobs)} job / recruiter related.")
        summary = "\n".join(lines)
        return {
            "success":       True,
            "summary":       summary,
            "messages":      msgs,
            "urgent":        [m.get("subject") for m in urgent],
            "needs_reply":   [m.get("subject") for m in replies_needed],
            "jobs":          [m.get("subject") for m in jobs],
        }

    # ------------------------------------------------------------------
    # Natural-language dispatcher
    # ------------------------------------------------------------------

    _NLP_PATTERNS = [
        (re.compile(r"\b(check|read|get|show|fetch|list)\b.{0,25}\b(email|inbox|mail|messages?)\b", re.I), "get_inbox"),
        (re.compile(r"\b(search|find|look for)\b.{0,20}\b(email|mail)\b", re.I), "search"),
        (re.compile(r"\b(send|compose|write|draft)\b.{0,20}\b(email|mail|message)\b", re.I), "send"),
        (re.compile(r"\b(reply|respond)\b.{0,20}\b(email|mail|message)\b", re.I), "reply"),
        (re.compile(r"\b(delete|remove|trash)\b.{0,20}\b(email|mail)\b", re.I), "delete"),
        (re.compile(r"\b(archive)\b.{0,20}\b(email|mail)\b", re.I), "archive"),
        (re.compile(r"\b(mark|flag).{0,15}(read|unread)\b", re.I), "mark"),
        (re.compile(r"\b(summarize?|summary|overview)\b.{0,20}\b(inbox|emails?|mail)\b", re.I), "summarize"),
        (re.compile(r"\b(important|urgent|priority)\b.{0,20}\b(email|mail|inbox)\b", re.I), "summarize"),
    ]

    def handle_prompt(self, prompt: str, default_account: str = "") -> dict:
        """Route a natural-language prompt to the appropriate email action."""
        for pattern, action in self._NLP_PATTERNS:
            if pattern.search(prompt):
                return self._dispatch_nlp(action, prompt, default_account)
        # Default: smart summary
        return self._dispatch_nlp("summarize", prompt, default_account)

    def _dispatch_nlp(self, action: str, prompt: str, account: str) -> dict:
        if action == "get_inbox":
            limit = self._extract_number(prompt, default=20)
            return self.get_inbox(account, limit=limit)
        elif action == "search":
            q = self._extract_quoted_or_last_words(prompt)
            return self.search_emails(q, account)
        elif action == "send":
            return {"success": False, "error": "To send an email please provide: recipient, subject, and body.",
                    "needs_input": True, "action": "send"}
        elif action == "reply":
            return {"success": False, "error": "To reply, please specify which email_id to reply to.",
                    "needs_input": True, "action": "reply"}
        elif action == "delete":
            return {"success": False, "error": "To delete, please specify an email_id.",
                    "needs_input": True, "action": "delete"}
        elif action == "archive":
            return {"success": False, "error": "To archive, please specify an email_id.",
                    "needs_input": True, "action": "archive"}
        elif action == "mark":
            return {"success": False, "error": "To mark, please specify an email_id.",
                    "needs_input": True, "action": "mark"}
        elif action == "summarize":
            return self.get_smart_summary(account)
        return self.get_inbox(account)

    # ------------------------------------------------------------------
    # Draft generator (LLM-enhanced when router available)
    # ------------------------------------------------------------------

    def generate_reply_draft(
        self,
        email_id:      str,
        tone:          str = "professional",
        model_router: object = None,
        user_profile:  dict = None,
    ) -> dict:
        """Generate a suggested reply draft for an email."""
        result = self.read_email(email_id)
        if not result.get("success"):
            return result
        orig = result["email"]
        subject    = orig["subject"]
        sender     = orig["sender"]
        body       = orig["body_plain"][:600]
        profile    = user_profile or {}
        user_name  = profile.get("name", "")
        user_title = profile.get("title", "")

        # Rule-based fallback draft
        cls = self.classify_email(orig)
        if cls["is_job_related"]:
            draft = (
                f"Hi {sender.split()[0] if sender else 'there'},\n\n"
                "Thank you for reaching out! I'd love to learn more about this opportunity. "
                "Could you share more details about the role and next steps?\n\n"
                f"Best regards,\n{user_name or 'Me'}"
            )
        elif cls["is_client_related"]:
            draft = (
                f"Hi {sender.split()[0] if sender else 'there'},\n\n"
                "Thank you for your message. I'll review the details and get back to you shortly.\n\n"
                f"Best regards,\n{user_name or 'Me'}"
            )
        else:
            draft = (
                f"Hi {sender.split()[0] if sender else 'there'},\n\n"
                "Thank you for your email. I'll get back to you as soon as possible.\n\n"
                f"Best regards,\n{user_name or 'Me'}"
            )

        # Upgrade with LLM if available
        if model_router:
            try:
                system = (
                    f"You are drafting a {tone} email reply. "
                    f"The user's name is {user_name}, title: {user_title}. "
                    "Write a concise, warm reply. Output ONLY the email body, no subject line."
                )
                user_msg = (
                    f"Original email from {sender}:\nSubject: {subject}\n\n{body}\n\n"
                    "Draft a reply:"
                )
                resp = model_router.ask(system=system, user=user_msg, task_type="email")
                if resp and len(resp.strip()) > 20:
                    draft = resp.strip()
            except NoModelAvailableError:
                _log.warning("Draft generation skipped — no AI model available")
            except Exception as _e:
                _log.error("Draft generation failed: %s", _e)

        return {
            "success":    True,
            "draft":      draft,
            "reply_to":   orig["sender_email"],
            "subject":    "Re: " + subject if not subject.startswith("Re:") else subject,
            "email_id":   email_id,
            "classification": cls,
        }

    # ------------------------------------------------------------------
    # Internal IMAP helpers
    # ------------------------------------------------------------------

    def _test_imap(self, email_addr, password, imap_host, imap_port) -> dict:
        """Attempt a real IMAP connection to verify credentials."""
        try:
            context = ssl.create_default_context()
            conn = imaplib.IMAP4_SSL(imap_host, imap_port, ssl_context=context)
            conn.login(email_addr, password)
            conn.logout()
            return {"success": True}
        except imaplib.IMAP4.error as e:
            err = str(e).lower()
            # Produce actionable error messages per provider
            if "authentication" in err or "login" in err or "invalid credentials" in err:
                if "gmail" in imap_host:
                    return {
                        "success": False,
                        "error": (
                            "Gmail authentication failed.\n"
                            "1. Enable IMAP: Gmail Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP\n"
                            "2. Use an App Password (not your regular Gmail password):\n"
                            "   Google Account → Security → 2-Step Verification → App passwords"
                        ),
                    }
                if "outlook" in imap_host or "office365" in imap_host:
                    return {
                        "success": False,
                        "error": (
                            "Outlook/Hotmail authentication failed.\n"
                            "Use an App Password (requires MFA to be ON):\n"
                            "  account.microsoft.com → Security → Advanced security → App passwords\n"
                            "Make sure IMAP is enabled: Outlook Settings → Mail → Sync email → IMAP"
                        ),
                    }
                return {"success": False, "error": "Authentication failed. Use an App Password, not your regular password."}
            return {"success": False, "error": f"IMAP error: {str(e)}"}
        except OSError as exc:
            return {"success": False, "error": f"Cannot reach mail server ({imap_host}:{imap_port}). Check your internet connection. Detail: {exc}"}
        except Exception as exc:
            return {"success": False, "error": f"Connection failed: {exc}"}

    def _get_imap(self, account: EmailAccount) -> imaplib.IMAP4_SSL:
        """Return a live (or reconnected) IMAP connection for an account."""
        email_addr = account.email
        conn = self._imap_conns.get(email_addr)
        # Test if connection is still alive
        if conn:
            try:
                conn.noop()
                return conn
            except Exception:
                pass
        # Reconnect
        password = self._creds().load(self._service_key(email_addr), "password")
        if not password:
            raise ValueError(f"No stored password for {email_addr}")
        context = ssl.create_default_context()
        new_conn = imaplib.IMAP4_SSL(account.imap_host, account.imap_port, ssl_context=context)
        new_conn.login(email_addr, password)
        self._imap_conns[email_addr] = new_conn
        account.connected = True
        return new_conn

    def _close_imap(self, email_addr: str) -> None:
        """Gracefully close an IMAP connection."""
        conn = self._imap_conns.pop(email_addr, None)
        if conn:
            try:
                conn.logout()
            except Exception:
                pass

    def _set_flag(self, email_id: str, op: str, flag: str, message: str,
                  expunge: bool = False) -> dict:
        account_email, uid = self._parse_email_id(email_id)
        account = self._accounts.get(account_email)
        if not account:
            return {"success": False, "error": "Account not found."}
        try:
            conn = self._get_imap(account)
            conn.select("INBOX")
            conn.store(uid.encode(), op, flag)
            if expunge:
                conn.expunge()
            return {"success": True, "message": message}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @staticmethod
    def _parse_email_id(email_id: str) -> tuple[str, str]:
        """Split an email_id into (account_email, uid)."""
        if "::" in email_id:
            parts = email_id.split("::", 1)
            return parts[0].lower(), parts[1]
        return "", email_id

    @staticmethod
    def _resolve_account_str(accounts: dict, hint: str) -> Optional[EmailAccount]:
        if hint:
            return accounts.get(hint.lower())
        # Return first connected account
        for a in accounts.values():
            if a.connected:
                return a
        # Return any account
        for a in accounts.values():
            return a
        return None

    def _resolve_account(self, hint: str = "") -> Optional[EmailAccount]:
        return self._resolve_account_str(self._accounts, hint)

    @staticmethod
    def _no_account_err() -> dict:
        return {"success": False,
                "error": "No email account connected. Please add an account in the Email tab."}

    @staticmethod
    def _build_search_criteria(query: str) -> str:
        """Convert a plain-text query to an IMAP SEARCH string."""
        q = query.strip()
        if q.upper().startswith(("FROM", "TO", "SUBJECT", "BODY", "ALL", "UNSEEN", "SEEN")):
            return q
        # Treat as subject search
        safe = q.replace('"', '')
        return f'SUBJECT "{safe}"'

    @staticmethod
    def _extract_number(text: str, default: int) -> int:
        m = re.search(r"\b(\d+)\b", text)
        return int(m.group(1)) if m else default

    @staticmethod
    def _extract_quoted_or_last_words(text: str) -> str:
        m = re.search(r'"([^"]+)"', text)
        if m:
            return m.group(1)
        words = text.split()
        return " ".join(words[-3:]) if len(words) >= 3 else text

    # ------------------------------------------------------------------
    # Metadata persistence (no passwords — just account config)
    # ------------------------------------------------------------------

    _META_PATH = Path("profiles") / "email_accounts.json"

    def _save_account_metadata(self) -> None:
        """Persist account configs (without passwords) to disk."""
        meta = {}
        for email_addr, acc in self._accounts.items():
            meta[email_addr] = {
                "email":        acc.email,
                "provider":     acc.provider,
                "imap_host":    acc.imap_host,
                "imap_port":    acc.imap_port,
                "smtp_host":    acc.smtp_host,
                "smtp_port":    acc.smtp_port,
                "display_name": acc.display_name,
            }
        try:
            self._META_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._META_PATH.write_text(
                __import__("json").dumps(meta, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _load_account_metadata(self) -> None:
        """Reload account configs from disk on startup."""
        if not self._META_PATH.exists():
            return
        try:
            meta = __import__("json").loads(
                self._META_PATH.read_text(encoding="utf-8")
            )
        except Exception:
            return

        # Guard: must be a dict keyed by email address.
        # Old/wrong placeholder format {"accounts": [...]} is silently ignored.
        if not isinstance(meta, dict):
            return

        for email_addr, conf in meta.items():
            # Skip malformed entries (e.g. old list-based format)
            if not isinstance(conf, dict) or "email" not in conf:
                continue
            try:
                # Verify password still stored
                svc_key = self._service_key(email_addr)
                try:
                    from .credential_store import get_credential_store
                    cs = get_credential_store()
                    has_pw = cs.exists(svc_key)
                except Exception:
                    has_pw = False

                acc = EmailAccount(
                    account_id   = email_addr,
                    email        = conf["email"],
                    provider     = conf.get("provider", "custom"),
                    imap_host    = conf.get("imap_host", ""),
                    imap_port    = int(conf.get("imap_port", 993)),
                    smtp_host    = conf.get("smtp_host", ""),
                    smtp_port    = int(conf.get("smtp_port", 587)),
                    display_name = conf.get("display_name", ""),
                    connected    = has_pw,
                )
                self._accounts[email_addr] = acc
            except Exception:
                continue


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Return the shared EmailService singleton."""
    global _service
    if _service is None:
        _service = EmailService()
    return _service
