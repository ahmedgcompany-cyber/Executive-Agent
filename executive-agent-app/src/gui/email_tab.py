"""
MegaV Email Tab — full email management UI.

Layout (horizontal splitter):
  LEFT  — Account cards + Add Account button
  CENTER — Inbox list + Smart Inbox classification
  RIGHT  — Email detail view + AI suggestions + CRM mini-panel + Action log

Follows the same dark/neon design system as the rest of MegaV.
"""

from __future__ import annotations

from typing import Optional

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QScrollArea, QFrame, QLineEdit, QDialog, QTextEdit,
        QListWidget, QListWidgetItem, QSplitter, QComboBox,
        QSizePolicy, QMessageBox, QProgressBar, QApplication,
        QStackedWidget, QFormLayout, QSpinBox,
    )
    from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSize
    from PySide6.QtGui import QFont, QColor, QPainter, QBrush, QPen
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


if not PYSIDE_AVAILABLE:
    class EmailTab:  # type: ignore
        pass
else:
    # ── Design tokens (matching main_window.py warm theme) ───────────
    BG      = "#1c1917"
    PANEL   = "#272420"
    PANEL2  = "#332e28"
    PANEL3  = "#3f3830"
    BORDER  = "#4a4138"
    TEXT    = "#f5f0ea"
    MUTED   = "#8a8279"
    ACCENT  = "#e8825c"   # Claude orange
    GREEN   = "#00e676"
    RED     = "#ff4444"
    YELLOW  = "#ffb020"
    CYAN    = "#00e5ff"
    TEAL    = "#00e5a0"
    PURPLE  = "#a855f7"
    PINK    = "#ff3e8a"
    ORANGE  = "#ff8c00"
    EMAIL_COLOR = "#7dff3a"   # lime_green — matches Email tab indicator

    # Priority colour mapping
    PRIORITY_COLORS = {
        "Urgent":   RED,
        "High":     ORANGE,
        "Normal":   ACCENT,
        "Low":      MUTED,
    }
    CATEGORY_COLORS = {
        "Job Applications": TEAL,
        "Work":             ACCENT,
        "Personal":         PURPLE,
        "Spam / Low Value": MUTED,
        "Notifications":    YELLOW,
        "Sales / Leads":    GREEN,
        "Urgent":           RED,
    }

    # ── Background workers ────────────────────────────────────────────

    class ConnectAccountWorker(QThread):
        finished = Signal(bool, str, str)   # success, message, email

        def __init__(self, email, password, provider,
                     imap_host="", imap_port=0, smtp_host="", smtp_port=0,
                     display_name=""):
            super().__init__()
            self._email        = email
            self._password     = password
            self._provider     = provider
            self._imap_host    = imap_host
            self._imap_port    = imap_port
            self._smtp_host    = smtp_host
            self._smtp_port    = smtp_port
            self._display_name = display_name

        def run(self):
            try:
                from ..integrations.email_service import get_email_service
                svc = get_email_service()
                r = svc.add_account(
                    email_addr   = self._email,
                    password     = self._password,
                    provider     = self._provider,
                    display_name = self._display_name,
                    imap_host    = self._imap_host,
                    imap_port    = self._imap_port,
                    smtp_host    = self._smtp_host,
                    smtp_port    = self._smtp_port,
                )
                if r.get("success"):
                    self.finished.emit(True, r.get("message", "Connected!"), self._email)
                else:
                    self.finished.emit(False, r.get("error", "Connection failed"), "")
            except Exception as exc:
                self.finished.emit(False, str(exc), "")


    class FetchInboxWorker(QThread):
        finished = Signal(dict)
        progress = Signal(str)

        def __init__(self, email_addr="", limit=20, smart=True):
            super().__init__()
            self._email = email_addr
            self._limit = limit
            self._smart = smart

        def run(self):
            try:
                from ..integrations.email_service import get_email_service
                svc = get_email_service()
                if self._smart:
                    r = svc.classify_inbox(self._email, limit=self._limit)
                else:
                    r = svc.get_inbox(self._email, limit=self._limit)
                self.finished.emit(r)
            except Exception as exc:
                self.finished.emit({"success": False, "error": str(exc)})


    class ReadEmailWorker(QThread):
        finished = Signal(dict)

        def __init__(self, email_id):
            super().__init__()
            self._id = email_id

        def run(self):
            try:
                from ..integrations.email_service import get_email_service
                r = get_email_service().read_email(self._id)
                self.finished.emit(r)
            except Exception as exc:
                self.finished.emit({"success": False, "error": str(exc)})


    class SendEmailWorker(QThread):
        finished = Signal(dict)

        def __init__(self, to, subject, body, from_account=""):
            super().__init__()
            self._to      = to
            self._subject = subject
            self._body    = body
            self._from    = from_account

        def run(self):
            try:
                from ..integrations.email_service import get_email_service
                r = get_email_service().send_email(
                    to=self._to, subject=self._subject,
                    body=self._body, from_account=self._from,
                )
                self.finished.emit(r)
            except Exception as exc:
                self.finished.emit({"success": False, "error": str(exc)})


    class DraftWorker(QThread):
        finished = Signal(dict)

        def __init__(self, email_id, runtime=None):
            super().__init__()
            self._id      = email_id
            self._runtime = runtime

        def run(self):
            try:
                from ..integrations.email_service import get_email_service
                svc    = get_email_service()
                router = None
                profile = {}
                if self._runtime:
                    try:
                        from ..providers.model_router import ModelRouter
                        router = ModelRouter()
                        ctx = self._runtime.get("context")
                        if ctx:
                            profile = dict(getattr(ctx, "profile", {}) or {})
                    except Exception:
                        pass
                r = svc.generate_reply_draft(
                    self._id, model_router=router, user_profile=profile
                )
                self.finished.emit(r)
            except Exception as exc:
                self.finished.emit({"success": False, "error": str(exc)})


    # ── Add Account Dialog ────────────────────────────────────────────

    class AddAccountDialog(QDialog):
        """Dialog to connect a new email account."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Add Email Account")
            self.setMinimumWidth(480)
            self.setModal(True)
            self.setStyleSheet(f"""
                QDialog   {{ background:{BG}; color:{TEXT}; }}
                QLabel    {{ color:{TEXT}; }}
                QLineEdit, QComboBox, QSpinBox {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:6px; padding:7px 10px; font-size:12px;
                }}
                QLineEdit:focus, QComboBox:focus {{ border:1px solid {EMAIL_COLOR}; }}
                QComboBox::drop-down {{ border:none; }}
            """)

            root = QVBoxLayout(self)
            root.setSpacing(12)
            root.setContentsMargins(24, 20, 24, 20)

            title = QLabel("Connect Email Account")
            title.setFont(QFont("Segoe UI", 14, QFont.Bold))
            title.setStyleSheet(f"color:{EMAIL_COLOR};")
            root.addWidget(title)

            note = QLabel(
                "For Gmail / Outlook: use an App Password (not your main password).\n"
                "Gmail: Google Account → Security → App passwords.\n"
                "Outlook: account.microsoft.com → Security → App passwords."
            )
            note.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            note.setWordWrap(True)
            root.addWidget(note)

            form = QFormLayout()
            form.setSpacing(8)
            form.setLabelAlignment(Qt.AlignRight)

            self._provider = QComboBox()
            from ..integrations.email_service import PROVIDERS
            for k, v in PROVIDERS.items():
                self._provider.addItem(v["name"], k)
            self._provider.currentIndexChanged.connect(self._on_provider_changed)
            form.addRow("Provider:", self._provider)

            self._email = QLineEdit()
            self._email.setPlaceholderText("you@gmail.com")
            form.addRow("Email:", self._email)

            self._display_name = QLineEdit()
            self._display_name.setPlaceholderText("Your Name (optional)")
            form.addRow("Display Name:", self._display_name)

            self._password = QLineEdit()
            self._password.setPlaceholderText("App password")
            self._password.setEchoMode(QLineEdit.Password)
            form.addRow("App Password:", self._password)

            # Custom IMAP/SMTP fields
            self._custom_widget = QWidget()
            cv = QFormLayout(self._custom_widget)
            cv.setSpacing(6)
            cv.setContentsMargins(0, 4, 0, 0)
            self._imap_host = QLineEdit(); self._imap_host.setPlaceholderText("mail.example.com")
            self._imap_port = QSpinBox(); self._imap_port.setRange(1, 65535); self._imap_port.setValue(993)
            self._smtp_host = QLineEdit(); self._smtp_host.setPlaceholderText("smtp.example.com")
            self._smtp_port = QSpinBox(); self._smtp_port.setRange(1, 65535); self._smtp_port.setValue(587)
            cv.addRow("IMAP Host:", self._imap_host)
            cv.addRow("IMAP Port:", self._imap_port)
            cv.addRow("SMTP Host:", self._smtp_host)
            cv.addRow("SMTP Port:", self._smtp_port)
            self._custom_widget.setVisible(False)
            form.addRow("", self._custom_widget)
            root.addLayout(form)

            self._prog = QProgressBar()
            self._prog.setRange(0, 0)
            self._prog.setFixedHeight(4)
            self._prog.setVisible(False)
            self._prog.setStyleSheet(f"""
                QProgressBar {{ background:{PANEL}; border:none; border-radius:2px; }}
                QProgressBar::chunk {{ background:{EMAIL_COLOR}; border-radius:2px; }}
            """)
            root.addWidget(self._prog)

            self._status = QLabel("")
            self._status.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            self._status.setWordWrap(True)
            self._status.setMinimumHeight(18)
            root.addWidget(self._status)

            btn_row = QHBoxLayout()
            self._connect_btn = QPushButton("Connect Account")
            self._connect_btn.setFixedHeight(38)
            self._connect_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self._connect_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{EMAIL_COLOR}; color:#000; border:none;
                    border-radius:8px; padding:0 20px;
                }}
                QPushButton:hover {{ background:#33deff; }}
                QPushButton:disabled {{ background:{PANEL2}; color:{MUTED}; }}
            """)
            self._connect_btn.clicked.connect(self._start_connect)

            cancel = QPushButton("Cancel")
            cancel.setFixedHeight(38)
            cancel.setStyleSheet(f"""
                QPushButton {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:8px; padding:0 20px;
                }}
                QPushButton:hover {{ background:{PANEL2}; }}
            """)
            cancel.clicked.connect(self.reject)
            btn_row.addWidget(self._connect_btn, 1)
            btn_row.addWidget(cancel)
            root.addLayout(btn_row)

            self._result = {}
            self._worker: Optional[QThread] = None

        def _on_provider_changed(self, _):
            is_custom = self._provider.currentData() == "custom"
            self._custom_widget.setVisible(is_custom)
            self.adjustSize()

        def _start_connect(self):
            email    = self._email.text().strip()
            password = self._password.text()
            provider = self._provider.currentData()
            if not email or not password:
                self._show_status("Email and password are required.", RED)
                return
            self._prog.setVisible(True)
            self._connect_btn.setEnabled(False)
            self._show_status("Testing connection…", MUTED)

            self._worker = ConnectAccountWorker(
                email=email, password=password, provider=provider,
                display_name=self._display_name.text().strip(),
                imap_host=self._imap_host.text().strip() if provider == "custom" else "",
                imap_port=self._imap_port.value()       if provider == "custom" else 0,
                smtp_host=self._smtp_host.text().strip() if provider == "custom" else "",
                smtp_port=self._smtp_port.value()       if provider == "custom" else 0,
            )
            self._worker.finished.connect(self._on_done)
            self._worker.start()

        def _on_done(self, success, message, email_addr):
            self._prog.setVisible(False)
            self._connect_btn.setEnabled(True)
            if success:
                self._result = {"success": True, "message": message, "email": email_addr}
                self._show_status(message, GREEN)
                QTimer.singleShot(1200, self.accept)
            else:
                self._result = {"success": False, "error": message}
                self._show_status(f"Error: {message}", RED)

        def _show_status(self, msg, color=MUTED):
            self._status.setText(msg)
            self._status.setStyleSheet(f"color:{color}; font-size:11px;")

        def get_result(self):
            return self._result

    # ── Compose / Send Dialog ─────────────────────────────────────────

    class ComposeDialog(QDialog):
        """Dialog to compose and send an email."""

        def __init__(self, to="", subject="", body="", from_account="",
                     runtime=None, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Compose Email")
            self.setMinimumSize(560, 460)
            self.setModal(True)
            self.setStyleSheet(f"""
                QDialog {{ background:{BG}; color:{TEXT}; }}
                QLabel  {{ color:{TEXT}; }}
                QLineEdit, QTextEdit {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:6px; padding:7px; font-size:12px;
                }}
                QLineEdit:focus, QTextEdit:focus {{ border:1px solid {EMAIL_COLOR}; }}
            """)
            self._runtime = runtime

            root = QVBoxLayout(self)
            root.setSpacing(8)
            root.setContentsMargins(20, 16, 20, 16)

            hdr = QLabel("Compose Email")
            hdr.setFont(QFont("Segoe UI", 13, QFont.Bold))
            hdr.setStyleSheet(f"color:{EMAIL_COLOR};")
            root.addWidget(hdr)

            form = QFormLayout()
            form.setSpacing(6)

            self._to   = QLineEdit(to);     self._to.setPlaceholderText("recipient@example.com")
            self._subj = QLineEdit(subject); self._subj.setPlaceholderText("Subject")
            form.addRow("To:",      self._to)
            form.addRow("Subject:", self._subj)

            # From account selector
            self._from_combo = QComboBox()
            self._from_combo.setStyleSheet(f"""
                QComboBox {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:6px; padding:6px;
                }}
            """)
            try:
                from ..integrations.email_service import get_email_service
                for acc in get_email_service().get_accounts():
                    if acc["connected"]:
                        self._from_combo.addItem(acc["email"], acc["email"])
                if from_account:
                    idx = self._from_combo.findData(from_account)
                    if idx >= 0:
                        self._from_combo.setCurrentIndex(idx)
            except Exception:
                pass
            form.addRow("From:", self._from_combo)
            root.addLayout(form)

            self._body = QTextEdit(body)
            self._body.setPlaceholderText("Email body…")
            self._body.setMinimumHeight(160)
            root.addWidget(self._body, 1)

            self._prog = QProgressBar()
            self._prog.setRange(0, 0)
            self._prog.setFixedHeight(4)
            self._prog.setVisible(False)
            self._prog.setStyleSheet(f"""
                QProgressBar {{ background:{PANEL}; border:none; border-radius:2px; }}
                QProgressBar::chunk {{ background:{GREEN}; border-radius:2px; }}
            """)
            root.addWidget(self._prog)

            self._status = QLabel("")
            self._status.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            root.addWidget(self._status)

            btn_row = QHBoxLayout()
            send = QPushButton("Send Email")
            send.setFixedHeight(38)
            send.setFont(QFont("Segoe UI", 11, QFont.Bold))
            send.setStyleSheet(f"""
                QPushButton {{
                    background:{GREEN}; color:#0d1117; border:none;
                    border-radius:8px; padding:0 20px;
                }}
                QPushButton:hover {{ background:#56d364; }}
                QPushButton:disabled {{ background:{PANEL}; color:{MUTED}; }}
            """)
            send.clicked.connect(self._send)

            cancel = QPushButton("Cancel")
            cancel.setFixedHeight(38)
            cancel.setStyleSheet(f"""
                QPushButton {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:8px; padding:0 20px;
                }}
            """)
            cancel.clicked.connect(self.reject)
            btn_row.addWidget(send, 1)
            btn_row.addWidget(cancel)
            root.addLayout(btn_row)
            self._worker: Optional[QThread] = None
            self._send_btn = send

        def _send(self):
            to      = self._to.text().strip()
            subject = self._subj.text().strip()
            body    = self._body.toPlainText().strip()
            fr      = self._from_combo.currentData() or ""
            if not to or not subject or not body:
                self._status.setText("To, Subject, and Body are required.")
                self._status.setStyleSheet(f"color:{RED};")
                return
            self._prog.setVisible(True)
            self._send_btn.setEnabled(False)
            self._status.setText("Sending…")
            self._status.setStyleSheet(f"color:{MUTED};")
            self._worker = SendEmailWorker(to, subject, body, fr)
            self._worker.finished.connect(self._on_sent)
            self._worker.start()

        def _on_sent(self, result):
            self._prog.setVisible(False)
            self._send_btn.setEnabled(True)
            if result.get("success"):
                self._status.setText(result.get("message", "Sent!"))
                self._status.setStyleSheet(f"color:{GREEN};")
                QTimer.singleShot(1500, self.accept)
            else:
                self._status.setText(result.get("error", "Send failed."))
                self._status.setStyleSheet(f"color:{RED};")

    # ── Account card ──────────────────────────────────────────────────

    class AccountCard(QFrame):
        """Single email account row card."""
        disconnect_requested = Signal(str)
        fetch_requested      = Signal(str)

        def __init__(self, account: dict, parent=None):
            super().__init__(parent)
            self._account = account
            email    = account.get("email", "")
            provider = account.get("provider", "")
            connected = account.get("connected", False)

            # Provider colour map
            colors = {
                "gmail":   "#ea4335",
                "outlook": "#0078d4",
                "yahoo":   "#720e9e",
                "custom":  ACCENT,
            }
            color = colors.get(provider, ACCENT)

            self.setFixedHeight(72)
            self.setStyleSheet(f"""
                AccountCard {{
                    background:{PANEL}; border:1px solid {BORDER};
                    border-radius:10px;
                }}
            """)

            row = QHBoxLayout(self)
            row.setContentsMargins(14, 0, 14, 0)
            row.setSpacing(12)

            # Provider badge
            badge = _Badge(provider[:2].upper(), color)
            row.addWidget(badge)

            # Info col
            info = QVBoxLayout()
            info.setSpacing(2)
            name_lbl = QLabel(account.get("display_name") or email)
            name_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
            name_lbl.setStyleSheet(f"color:{TEXT};")
            email_lbl = QLabel(email)
            email_lbl.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            info.addWidget(name_lbl)
            info.addWidget(email_lbl)
            row.addLayout(info, 1)

            # Status
            inbox = account.get("inbox_count", 0)
            status_lbl = QLabel(f"Connected — {inbox} messages" if connected else "Not connected")
            status_lbl.setStyleSheet(
                f"color:{GREEN}; font-size:10px;" if connected
                else f"color:{MUTED}; font-size:10px;"
            )
            row.addWidget(status_lbl)

            # Fetch button
            fetch_btn = QPushButton("Refresh")
            fetch_btn.setFixedSize(72, 28)
            fetch_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{PANEL2}; color:{ACCENT}; border:1px solid {ACCENT};
                    border-radius:6px; font-size:10px;
                }}
                QPushButton:hover {{ background:{PANEL}; }}
            """)
            fetch_btn.clicked.connect(lambda: self.fetch_requested.emit(email))
            row.addWidget(fetch_btn)

            # Disconnect button
            disc_btn = QPushButton("Disconnect")
            disc_btn.setFixedSize(90, 28)
            disc_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#1a1a2d; color:{RED}; border:1px solid {RED};
                    border-radius:6px; font-size:10px;
                }}
                QPushButton:hover {{ background:#2a1a1a; }}
            """)
            disc_btn.clicked.connect(lambda: self.disconnect_requested.emit(email))
            row.addWidget(disc_btn)

    class _Badge(QWidget):
        def __init__(self, text, color, size=42):
            super().__init__()
            self._text  = text.upper()[:2]
            self._color = QColor(color)
            self._size  = size
            self.setFixedSize(size, size)

        def paintEvent(self, _):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QBrush(self._color))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 0, self._size, self._size, 8, 8)
            p.setPen(QPen(QColor(255, 255, 255, 230)))
            p.setFont(QFont("Segoe UI", max(8, self._size // 4), QFont.Bold))
            p.drawText(0, 0, self._size, self._size, Qt.AlignCenter, self._text)
            p.end()

    # ── Email list item ───────────────────────────────────────────────

    def _make_email_item(msg: dict) -> QListWidgetItem:
        cls      = msg.get("classification", {})
        subject  = msg.get("subject", "(no subject)")[:60]
        sender   = msg.get("sender", "")[:30]
        priority = cls.get("priority", "Normal")
        category = cls.get("category", "")
        is_read  = msg.get("is_read", False)

        pcolor = PRIORITY_COLORS.get(priority, ACCENT)
        badge  = {"Urgent": "!!! ", "High": "!! ", "Normal": "", "Low": ""}.get(priority, "")
        read_dot = " " if is_read else "● "

        text = f"{read_dot}{badge}{subject}\n    {sender}  |  {category}"
        item = QListWidgetItem(text)
        item.setForeground(QColor(pcolor if not is_read else MUTED))
        item.setData(Qt.UserRole, msg)
        return item

    # ── Main EmailTab ─────────────────────────────────────────────────

    class EmailTab(QWidget):
        """Full Email management tab for MainWindow."""

        action_logged = Signal(str)   # emit log lines to main status bar

        def __init__(self, runtime=None, parent=None):
            super().__init__(parent)
            self._runtime = runtime or {}
            self._workers: list[QThread] = []
            self._current_email_id: str = ""
            self._current_messages: list[dict] = []
            self._log_lines: list[str] = []

            self.setStyleSheet(f"background:{BG};")
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            # ── Header bar ────────────────────────────────────────────
            hdr_bar = QFrame()
            hdr_bar.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {EMAIL_COLOR}25, stop:0.7 {CYAN}10, stop:1 transparent);
                    border-left:5px solid {EMAIL_COLOR};
                    border-radius:6px;
                    margin:10px 10px 4px 10px;
                }}
            """)
            hbar_l = QHBoxLayout(hdr_bar)
            hbar_l.setContentsMargins(12, 6, 12, 6)
            hdr_title = QLabel("Email Automation")
            hdr_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
            hdr_title.setStyleSheet(f"color:{EMAIL_COLOR}; background:transparent; border:none;")
            hbar_l.addWidget(hdr_title)
            hbar_l.addStretch()

            refresh_all = QPushButton("Refresh All")
            refresh_all.setFixedHeight(30)
            refresh_all.setStyleSheet(f"""
                QPushButton {{
                    background:{PANEL2}; color:{EMAIL_COLOR}; border:1px solid {EMAIL_COLOR};
                    border-radius:6px; padding:0 12px; font-size:10px;
                }}
                QPushButton:hover {{ background:{PANEL}; }}
            """)
            refresh_all.clicked.connect(self._fetch_all)
            hbar_l.addWidget(refresh_all)

            add_btn = QPushButton("+ Add Account")
            add_btn.setFixedHeight(30)
            add_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{EMAIL_COLOR}; color:#000; border:none;
                    border-radius:6px; padding:0 14px; font-size:10px; font-weight:bold;
                }}
                QPushButton:hover {{ background:#33deff; }}
            """)
            add_btn.clicked.connect(self._add_account)
            hbar_l.addWidget(add_btn)
            root.addWidget(hdr_bar)

            # ── Main horizontal splitter ───────────────────────────────
            splitter = QSplitter(Qt.Horizontal)
            splitter.setHandleWidth(2)
            splitter.setStyleSheet(f"QSplitter::handle {{ background:{BORDER}; }}")

            # ── LEFT: Account cards ────────────────────────────────────
            left = QWidget()
            left.setMinimumWidth(220)
            left.setMaximumWidth(320)
            lv = QVBoxLayout(left)
            lv.setContentsMargins(8, 8, 4, 8)
            lv.setSpacing(6)

            acct_hdr = QLabel("Connected Accounts")
            acct_hdr.setFont(QFont("Segoe UI", 11, QFont.Bold))
            acct_hdr.setStyleSheet(f"color:{EMAIL_COLOR};")
            lv.addWidget(acct_hdr)

            self._accounts_scroll = QScrollArea()
            self._accounts_scroll.setWidgetResizable(True)
            self._accounts_scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{BG}; }}")
            self._accounts_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._accounts_container = QWidget()
            self._accounts_container.setStyleSheet(f"background:{BG};")
            self._accounts_layout = QVBoxLayout(self._accounts_container)
            self._accounts_layout.setContentsMargins(0, 0, 0, 0)
            self._accounts_layout.setSpacing(4)
            self._accounts_layout.addStretch()
            self._accounts_scroll.setWidget(self._accounts_container)
            lv.addWidget(self._accounts_scroll, 1)

            # Smart inbox stats
            self._stats_frame = QFrame()
            self._stats_frame.setStyleSheet(f"""
                QFrame {{
                    background:{PANEL}; border:1px solid {BORDER};
                    border-radius:8px;
                }}
            """)
            sf = QVBoxLayout(self._stats_frame)
            sf.setContentsMargins(10, 8, 10, 8)
            sf.setSpacing(4)
            stats_hdr = QLabel("Inbox Summary")
            stats_hdr.setFont(QFont("Segoe UI", 10, QFont.Bold))
            stats_hdr.setStyleSheet(f"color:{TEAL};")
            sf.addWidget(stats_hdr)
            self._stats_urgent = QLabel("Urgent: —")
            self._stats_urgent.setStyleSheet(f"color:{RED}; font-size:10px;")
            self._stats_reply  = QLabel("Need Reply: —")
            self._stats_reply.setStyleSheet(f"color:{YELLOW}; font-size:10px;")
            self._stats_total  = QLabel("Total: —")
            self._stats_total.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            sf.addWidget(self._stats_urgent)
            sf.addWidget(self._stats_reply)
            sf.addWidget(self._stats_total)
            lv.addWidget(self._stats_frame)

            splitter.addWidget(left)

            # ── CENTER: Inbox list ─────────────────────────────────────
            center = QWidget()
            cv = QVBoxLayout(center)
            cv.setContentsMargins(4, 8, 4, 8)
            cv.setSpacing(6)

            inbox_hdr_row = QHBoxLayout()
            inbox_hdr = QLabel("Smart Inbox")
            inbox_hdr.setFont(QFont("Segoe UI", 11, QFont.Bold))
            inbox_hdr.setStyleSheet(f"color:{TEAL};")
            inbox_hdr_row.addWidget(inbox_hdr)

            self._filter_combo = QComboBox()
            self._filter_combo.addItems([
                "All", "Urgent", "Needs Reply", "Job Applications",
                "Work", "Personal", "Spam / Low Value", "Notifications",
            ])
            self._filter_combo.setFixedHeight(26)
            self._filter_combo.setStyleSheet(f"""
                QComboBox {{
                    background:{PANEL2}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:6px; padding:2px 8px; font-size:10px;
                }}
            """)
            self._filter_combo.currentTextChanged.connect(self._apply_filter)
            inbox_hdr_row.addWidget(self._filter_combo)

            self._search_box = QLineEdit()
            self._search_box.setPlaceholderText("Search inbox…")
            self._search_box.setFixedHeight(26)
            self._search_box.setStyleSheet(f"""
                QLineEdit {{
                    background:{PANEL2}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:6px; padding:2px 8px; font-size:10px;
                }}
            """)
            self._search_box.returnPressed.connect(self._do_search)
            inbox_hdr_row.addWidget(self._search_box)
            cv.addLayout(inbox_hdr_row)

            self._inbox_list = QListWidget()
            self._inbox_list.setStyleSheet(f"""
                QListWidget {{
                    background:{PANEL}; border:1px solid {BORDER};
                    border-radius:8px; padding:4px;
                }}
                QListWidget::item {{
                    padding:8px 6px; border-radius:6px; border-bottom:1px solid {BORDER};
                }}
                QListWidget::item:hover {{ background:{PANEL2}; }}
                QListWidget::item:selected {{ background:{EMAIL_COLOR}18; border-left:3px solid {EMAIL_COLOR}; }}
            """)
            self._inbox_list.setSpacing(1)
            self._inbox_list.currentItemChanged.connect(self._on_email_selected)
            cv.addWidget(self._inbox_list, 1)

            self._inbox_progress = QProgressBar()
            self._inbox_progress.setRange(0, 0)
            self._inbox_progress.setFixedHeight(4)
            self._inbox_progress.setVisible(False)
            self._inbox_progress.setStyleSheet(f"""
                QProgressBar {{ background:{PANEL}; border:none; border-radius:2px; }}
                QProgressBar::chunk {{ background:{EMAIL_COLOR}; border-radius:2px; }}
            """)
            cv.addWidget(self._inbox_progress)
            splitter.addWidget(center)

            # ── RIGHT: Detail + Actions ────────────────────────────────
            right = QWidget()
            right.setMinimumWidth(300)
            rv = QVBoxLayout(right)
            rv.setContentsMargins(4, 8, 8, 8)
            rv.setSpacing(6)

            right_splitter = QSplitter(Qt.Vertical)
            right_splitter.setHandleWidth(2)
            right_splitter.setStyleSheet(f"QSplitter::handle {{ background:{BORDER}; }}")

            # Email detail panel
            detail_panel = QWidget()
            dv = QVBoxLayout(detail_panel)
            dv.setContentsMargins(0, 0, 0, 0)
            dv.setSpacing(4)

            self._detail_header = QLabel("Select an email to preview")
            self._detail_header.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self._detail_header.setStyleSheet(f"color:{TEXT};")
            self._detail_header.setWordWrap(True)
            dv.addWidget(self._detail_header)

            self._detail_meta = QLabel("")
            self._detail_meta.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            self._detail_meta.setWordWrap(True)
            dv.addWidget(self._detail_meta)

            # Classification badge
            self._cls_badge = QLabel("")
            self._cls_badge.setStyleSheet(f"color:{TEAL}; font-size:10px; font-weight:bold;")
            dv.addWidget(self._cls_badge)

            self._detail_body = QTextEdit()
            self._detail_body.setReadOnly(True)
            self._detail_body.setStyleSheet(f"""
                QTextEdit {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:8px; padding:8px; font-size:11px;
                }}
            """)
            dv.addWidget(self._detail_body, 1)

            # Action buttons row
            action_row = QHBoxLayout()
            action_row.setSpacing(6)
            for label, color, slot in [
                ("Reply",    ACCENT,  self._reply_selected),
                ("Forward",  PURPLE,  self._forward_selected),
                ("Archive",  YELLOW,  self._archive_selected),
                ("Delete",   RED,     self._delete_selected),
            ]:
                btn = QPushButton(label)
                btn.setFixedHeight(30)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{PANEL2}; color:{color}; border:1px solid {color};
                        border-radius:6px; padding:0 10px; font-size:10px;
                    }}
                    QPushButton:hover {{ background:{PANEL}; }}
                    QPushButton:disabled {{ color:{MUTED}; border-color:{BORDER}; }}
                """)
                btn.clicked.connect(slot)
                action_row.addWidget(btn)
            dv.addLayout(action_row)
            right_splitter.addWidget(detail_panel)

            # AI Suggestions panel
            suggest_panel = QWidget()
            sv = QVBoxLayout(suggest_panel)
            sv.setContentsMargins(0, 0, 0, 0)
            sv.setSpacing(4)

            suggest_hdr_row = QHBoxLayout()
            suggest_hdr = QLabel("AI Suggestions")
            suggest_hdr.setFont(QFont("Segoe UI", 10, QFont.Bold))
            suggest_hdr.setStyleSheet(f"color:{PINK};")
            suggest_hdr_row.addWidget(suggest_hdr)

            draft_btn = QPushButton("Generate Reply Draft")
            draft_btn.setFixedHeight(26)
            draft_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{PANEL2}; color:{PINK}; border:1px solid {PINK};
                    border-radius:6px; padding:0 10px; font-size:9px;
                }}
                QPushButton:hover {{ background:{PANEL}; }}
            """)
            draft_btn.clicked.connect(self._generate_draft)
            suggest_hdr_row.addWidget(draft_btn)
            sv.addLayout(suggest_hdr_row)

            self._suggest_area = QTextEdit()
            self._suggest_area.setReadOnly(True)
            self._suggest_area.setPlaceholderText(
                "Select an email — AI suggestions will appear here.\n\n"
                "I can:\n"
                "  • Classify priority and category\n"
                "  • Detect if a reply is needed\n"
                "  • Draft a professional reply\n"
                "  • Suggest CRM follow-up actions"
            )
            self._suggest_area.setStyleSheet(f"""
                QTextEdit {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:8px; padding:8px; font-size:10px;
                }}
            """)
            sv.addWidget(self._suggest_area, 1)

            # Use draft button
            use_draft_row = QHBoxLayout()
            self._use_draft_btn = QPushButton("Open in Compose Window")
            self._use_draft_btn.setEnabled(False)
            self._use_draft_btn.setFixedHeight(28)
            self._use_draft_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{GREEN}; color:#000; border:none;
                    border-radius:6px; padding:0 12px; font-size:10px; font-weight:bold;
                }}
                QPushButton:hover {{ background:#56d364; }}
                QPushButton:disabled {{ background:{PANEL}; color:{MUTED}; }}
            """)
            self._use_draft_btn.clicked.connect(self._open_draft_compose)
            use_draft_row.addWidget(self._use_draft_btn)
            use_draft_row.addStretch()
            sv.addLayout(use_draft_row)
            self._current_draft: dict = {}
            right_splitter.addWidget(suggest_panel)

            # Action log panel
            log_panel = QWidget()
            logv = QVBoxLayout(log_panel)
            logv.setContentsMargins(0, 0, 0, 0)
            logv.setSpacing(4)
            log_hdr = QLabel("Action Log")
            log_hdr.setFont(QFont("Segoe UI", 10, QFont.Bold))
            log_hdr.setStyleSheet(f"color:{MUTED};")
            logv.addWidget(log_hdr)
            self._log_text = QTextEdit()
            self._log_text.setReadOnly(True)
            self._log_text.setMaximumHeight(100)
            self._log_text.setStyleSheet(f"""
                QTextEdit {{
                    background:{BG}; color:{MUTED}; border:1px solid {BORDER};
                    border-radius:6px; padding:6px; font-size:9px;
                }}
            """)
            logv.addWidget(self._log_text)
            right_splitter.addWidget(log_panel)

            right_splitter.setSizes([320, 200, 100])
            rv.addWidget(right_splitter, 1)
            splitter.addWidget(right)

            splitter.setSizes([260, 420, 360])
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
            splitter.setStretchFactor(2, 0)

            root.addWidget(splitter, 1)

            # ── Initial refresh ────────────────────────────────────────
            self.refresh_accounts()

        # ── Account management ────────────────────────────────────────

        def refresh_accounts(self):
            """Reload account cards from EmailService."""
            try:
                from ..integrations.email_service import get_email_service
                accounts = get_email_service().get_accounts()
            except Exception:
                accounts = []

            # Clear existing cards (leave stretch at end)
            while self._accounts_layout.count() > 1:
                item = self._accounts_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            for acc in accounts:
                card = AccountCard(acc)
                card.disconnect_requested.connect(self._disconnect_account)
                card.fetch_requested.connect(self._fetch_account)
                self._accounts_layout.insertWidget(self._accounts_layout.count() - 1, card)

            if not accounts:
                lbl = QLabel("No accounts connected.\nClick '+ Add Account' above.")
                lbl.setStyleSheet(f"color:{MUTED}; font-size:10px;")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setWordWrap(True)
                self._accounts_layout.insertWidget(0, lbl)

        def _add_account(self):
            dialog = AddAccountDialog(self)
            code   = dialog.exec()
            result = dialog.get_result()
            if code == QDialog.Accepted or result.get("success"):
                self.refresh_accounts()
                self._log(f"Connected {result.get('email', '')} successfully.")
                self._fetch_all()
                self._toast(result.get("message", "Account connected!"), GREEN)
            elif result.get("error"):
                self._toast(f"Error: {result['error'][:80]}", RED)

        def _disconnect_account(self, email_addr: str):
            reply = QMessageBox.question(
                self, "Disconnect Account",
                f"Remove {email_addr} from MegaV?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                try:
                    from ..integrations.email_service import get_email_service
                    get_email_service().remove_account(email_addr)
                except Exception:
                    pass
                self.refresh_accounts()
                self._inbox_list.clear()
                self._log(f"Disconnected {email_addr}.")

        def _fetch_account(self, email_addr: str):
            self._fetch_inbox(email_addr=email_addr)

        def _fetch_all(self):
            try:
                from ..integrations.email_service import get_email_service
                accounts = get_email_service().get_accounts()
                if not accounts:
                    self._toast("No accounts connected.", YELLOW)
                    return
                # Fetch first connected account
                for acc in accounts:
                    if acc.get("connected"):
                        self._fetch_inbox(email_addr=acc["email"])
                        return
                self._toast("No connected accounts to refresh.", YELLOW)
            except Exception as exc:
                self._toast(f"Refresh error: {exc}", RED)

        # ── Inbox fetching ────────────────────────────────────────────

        def _fetch_inbox(self, email_addr: str = "", limit: int = 25):
            self._inbox_progress.setVisible(True)
            self._inbox_list.clear()
            self._log(f"Fetching inbox{'  ('+email_addr+')' if email_addr else ''}…")

            worker = FetchInboxWorker(email_addr=email_addr, limit=limit, smart=True)
            worker.finished.connect(self._on_inbox_fetched)
            worker.finished.connect(lambda _: self._cleanup_worker(worker))
            self._workers.append(worker)
            worker.start()

        def _on_inbox_fetched(self, result: dict):
            self._inbox_progress.setVisible(False)
            if not result.get("success"):
                self._log(f"Fetch failed: {result.get('error', 'Unknown error')}")
                self._toast(f"Inbox error: {result.get('error', '')[:60]}", RED)
                return

            messages = result.get("messages", [])
            self._current_messages = messages
            urgent   = result.get("urgent_count", 0)
            replies  = result.get("needs_reply_count", 0)

            self._stats_urgent.setText(f"Urgent: {urgent}")
            self._stats_reply.setText(f"Need Reply: {replies}")
            self._stats_total.setText(f"Total: {len(messages)}")

            self._inbox_list.clear()
            for msg in messages:
                self._inbox_list.addItem(_make_email_item(msg))

            self._log(f"Fetched {len(messages)} emails. Urgent: {urgent}, Need Reply: {replies}.")

            # Auto-extract contacts to CRM
            try:
                from ..integrations.crm_service import get_crm_service
                new_contacts = get_crm_service().extract_contacts_from_emails(messages)
                if new_contacts:
                    self._log(f"Auto-added {len(new_contacts)} contact(s) to CRM.")
            except Exception:
                pass

        # ── Email selection & display ─────────────────────────────────

        def _on_email_selected(self, current: QListWidgetItem, _):
            if not current:
                return
            msg = current.data(Qt.UserRole)
            if not msg:
                return
            self._current_email_id = msg.get("email_id", "")
            self._display_email(msg)

        def _display_email(self, msg: dict):
            subject = msg.get("subject", "(no subject)")
            sender  = msg.get("sender", "")
            date    = msg.get("date", "")
            body    = msg.get("body_plain", "") or "(no body)"
            cls     = msg.get("classification", {})

            self._detail_header.setText(subject)
            self._detail_meta.setText(f"From: {sender}   |   {date}")
            self._detail_body.setPlainText(body)

            # Classification badge
            priority = cls.get("priority", "")
            category = cls.get("category", "")
            action   = cls.get("suggested_action", "")
            badge_parts = []
            if priority:
                badge_parts.append(f"[{priority}]")
            if category:
                badge_parts.append(f"[{category}]")
            self._cls_badge.setText("  ".join(badge_parts))

            # AI suggestions
            suggest_lines = []
            if cls.get("is_urgent"):
                suggest_lines.append("⚠  URGENT — requires immediate attention.")
            if cls.get("is_job_related"):
                suggest_lines.append("💼  Recruiter / Job related.")
            if cls.get("is_client_related"):
                suggest_lines.append("🤝  Client or business email.")
            if cls.get("needs_reply"):
                suggest_lines.append("✉  A reply appears to be needed.")
                suggest_lines.append("→  Click 'Generate Reply Draft' to draft a response.")
            if cls.get("is_spam"):
                suggest_lines.append("🗑  Low priority / spam indicator detected.")
                suggest_lines.append("→  Consider archiving.")
            if action:
                suggest_lines.append(f"\nSuggested action: {action}")
            self._suggest_area.setPlainText("\n".join(suggest_lines) if suggest_lines else
                                            "No specific suggestions for this email.")
            self._current_draft = {}
            self._use_draft_btn.setEnabled(False)

            # Mark as read in background
            if self._current_email_id and not msg.get("is_read"):
                self._mark_read_bg(self._current_email_id)

        def _mark_read_bg(self, email_id: str):
            import threading
            def _do():
                try:
                    from ..integrations.email_service import get_email_service
                    get_email_service().mark_as_read(email_id)
                except Exception:
                    pass
            threading.Thread(target=_do, daemon=True).start()

        # ── Email actions ─────────────────────────────────────────────

        def _reply_selected(self):
            if not self._current_email_id:
                return
            current = self._inbox_list.currentItem()
            msg     = current.data(Qt.UserRole) if current else {}
            sender_email = msg.get("sender_email", "")
            subject = msg.get("subject", "")
            if not subject.startswith("Re:"):
                subject = "Re: " + subject
            body = self._current_draft.get("draft", "")
            dialog = ComposeDialog(
                to=sender_email, subject=subject, body=body,
                runtime=self._runtime, parent=self
            )
            if dialog.exec() == QDialog.Accepted:
                self._log(f"Replied to: {sender_email}")

        def _forward_selected(self):
            if not self._current_email_id:
                return
            current = self._inbox_list.currentItem()
            msg     = current.data(Qt.UserRole) if current else {}
            subject = msg.get("subject", "")
            if not subject.startswith("Fwd:"):
                subject = "Fwd: " + subject
            orig_body = msg.get("body_plain", "")
            fwd_body  = f"\n\n--- Forwarded message ---\n{orig_body[:500]}"
            dialog = ComposeDialog(subject=subject, body=fwd_body,
                                   runtime=self._runtime, parent=self)
            dialog.exec()

        def _archive_selected(self):
            if not self._current_email_id:
                return
            reply = QMessageBox.question(self, "Archive Email",
                "Archive this email?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                import threading
                eid = self._current_email_id
                def _do():
                    try:
                        from ..integrations.email_service import get_email_service
                        get_email_service().archive_email(eid)
                    except Exception:
                        pass
                threading.Thread(target=_do, daemon=True).start()
                row = self._inbox_list.currentRow()
                self._inbox_list.takeItem(row)
                self._log(f"Archived email: {eid}")
                self._detail_body.clear()
                self._current_email_id = ""

        def _delete_selected(self):
            if not self._current_email_id:
                return
            reply = QMessageBox.question(self, "Delete Email",
                "Permanently delete this email?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                import threading
                eid = self._current_email_id
                def _do():
                    try:
                        from ..integrations.email_service import get_email_service
                        get_email_service().delete_email(eid)
                    except Exception:
                        pass
                threading.Thread(target=_do, daemon=True).start()
                row = self._inbox_list.currentRow()
                self._inbox_list.takeItem(row)
                self._log(f"Deleted email: {eid}")
                self._detail_body.clear()
                self._current_email_id = ""

        # ── AI draft generation ───────────────────────────────────────

        def _generate_draft(self):
            if not self._current_email_id:
                self._suggest_area.setPlainText("Select an email first.")
                return
            self._suggest_area.setPlainText("Generating reply draft…")
            worker = DraftWorker(self._current_email_id, self._runtime)
            worker.finished.connect(self._on_draft_ready)
            worker.finished.connect(lambda _: self._cleanup_worker(worker))
            self._workers.append(worker)
            worker.start()

        def _on_draft_ready(self, result: dict):
            if not result.get("success"):
                self._suggest_area.setPlainText(f"Draft error: {result.get('error', 'Failed')}")
                return
            self._current_draft = result
            draft = result.get("draft", "")
            cls   = result.get("classification", {})
            lines = ["=== Suggested Reply Draft ===", "", draft, "",
                     "─" * 40,
                     f"Category:  {cls.get('category', '')}",
                     f"Priority:  {cls.get('priority', '')}",
                     f"Action:    {cls.get('suggested_action', '')}"]
            self._suggest_area.setPlainText("\n".join(lines))
            self._use_draft_btn.setEnabled(True)
            self._log("Reply draft generated.")

        def _open_draft_compose(self):
            if not self._current_draft:
                return
            dialog = ComposeDialog(
                to      = self._current_draft.get("reply_to", ""),
                subject = self._current_draft.get("subject", ""),
                body    = self._current_draft.get("draft", ""),
                runtime = self._runtime,
                parent  = self,
            )
            if dialog.exec() == QDialog.Accepted:
                self._log(f"Email sent from draft.")

        # ── Search ────────────────────────────────────────────────────

        def _do_search(self):
            query = self._search_box.text().strip()
            if not query:
                return
            self._inbox_progress.setVisible(True)
            self._log(f"Searching: {query}…")
            import threading
            def _do():
                try:
                    from ..integrations.email_service import get_email_service
                    r = get_email_service().search_emails(query)
                    QTimer.singleShot(0, lambda: self._on_search_done(r))
                except Exception as exc:
                    QTimer.singleShot(0, lambda: self._on_search_done({"success": False, "error": str(exc)}))
            threading.Thread(target=_do, daemon=True).start()

        def _on_search_done(self, result: dict):
            self._inbox_progress.setVisible(False)
            if not result.get("success"):
                self._toast(f"Search error: {result.get('error', '')}", RED)
                return
            messages = result.get("messages", [])
            self._inbox_list.clear()
            for msg in messages:
                self._inbox_list.addItem(_make_email_item(msg))
            self._log(f"Search returned {len(messages)} result(s).")

        # ── Filter ────────────────────────────────────────────────────

        def _apply_filter(self, filter_text: str):
            if filter_text == "All":
                for i in range(self._inbox_list.count()):
                    self._inbox_list.item(i).setHidden(False)
                return
            for i in range(self._inbox_list.count()):
                item = self._inbox_list.item(i)
                msg  = item.data(Qt.UserRole) or {}
                cls  = msg.get("classification", {})
                visible = True
                if filter_text == "Urgent":
                    visible = cls.get("priority") == "Urgent"
                elif filter_text == "Needs Reply":
                    visible = cls.get("needs_reply", False)
                else:
                    visible = cls.get("category", "") == filter_text
                item.setHidden(not visible)

        # ── Helpers ───────────────────────────────────────────────────

        def _log(self, msg: str):
            import datetime
            ts   = datetime.datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}] {msg}"
            self._log_lines.append(line)
            self._log_text.append(line)
            self.action_logged.emit(msg)

        def _toast(self, msg: str, _color: str = MUTED):
            mw = self.window()
            if hasattr(mw, "status_bar"):
                mw.status_bar.showMessage(msg, 5000)

        def _cleanup_worker(self, worker: QThread):
            if worker in self._workers:
                self._workers.remove(worker)

        def compose_new(self, to: str = "", subject: str = "", body: str = ""):
            """Open compose dialog programmatically (called by agents)."""
            dialog = ComposeDialog(to=to, subject=subject, body=body,
                                   runtime=self._runtime, parent=self)
            dialog.exec()

        def get_action_log(self) -> list[str]:
            return list(self._log_lines)
