"""Social Accounts tab — connect, view, and manage social media platforms."""

from pathlib import Path
from typing import Any, Optional

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QScrollArea, QFrame, QLineEdit, QDialog,
        QTextEdit, QStackedWidget, QSizePolicy, QMessageBox,
        QProgressBar, QComboBox, QApplication,
    )
    from PySide6.QtCore import Qt, Signal, QThread, QSize, QTimer
    from PySide6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QPixmap, QPalette
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


if not PYSIDE_AVAILABLE:
    class SocialTab:  # type: ignore
        pass
else:

    # ── Colours (unified with main window warm theme) ─────────────────
    BG      = "#1c1917"
    PANEL   = "#272420"
    PANEL2  = "#332e28"
    BORDER  = "#4a4138"
    ACCENT  = "#00e5a0"   # teal — matches Social tab indicator
    GREEN   = "#00e676"
    RED     = "#ff4444"
    YELLOW  = "#ffb020"
    TEXT    = "#f5f0ea"
    MUTED   = "#8a8279"
    BLUE    = "#4d9fff"
    CYAN    = "#00e5ff"
    TEAL    = "#00e5a0"
    PINK    = "#ff3e8a"
    PURPLE  = "#a855f7"
    AMBER   = "#ffb020"
    SURFACE2 = "#332e28"
    SURFACE3 = "#3f3830"

    # ── Browser-login worker ───────────────────────────────────────────

    class ConnectWorker(QThread):
        """Runs login_via_browser() in a background thread."""
        progress = Signal(str)
        finished = Signal(bool, str)   # success, message

        def __init__(self, social_tools, platform: str, email: str, password: str):
            super().__init__()
            self.social    = social_tools
            self.platform  = platform
            self.email     = email
            self.password  = password

        def run(self):
            try:
                result = self.social.login_via_browser(
                    self.platform,
                    self.email,
                    self.password,
                    progress_cb=lambda msg: self.progress.emit(msg),
                )
            except Exception as exc:
                self.finished.emit(False, str(exc))
                return

            if result.get("success"):
                acc = result.get("account_name", "")
                self.finished.emit(True, f"Connected{' as ' + acc if acc else ''}!")
            else:
                self.finished.emit(False, result.get("error", "Connection failed"))

    # ── Token-only worker (fallback) ───────────────────────────────────

    class TokenWorker(QThread):
        """Saves a pasted access token directly — no browser needed."""
        finished = Signal(bool, str)

        def __init__(self, social_tools, platform: str, token: str, account_name: str):
            super().__init__()
            self.social       = social_tools
            self.platform     = platform
            self.token        = token
            self.account_name = account_name

        def run(self):
            try:
                result = self.social.connect_with_token(
                    self.platform,
                    access_token=self.token,
                    account_name=self.account_name,
                )
            except Exception as exc:
                self.finished.emit(False, str(exc))
                return

            if result.get("success"):
                acc = result.get("account_name", self.account_name)
                self.finished.emit(True, f"Connected{' as ' + acc if acc else ''}!")
            else:
                self.finished.emit(False, result.get("error", "Connection failed"))

    # ── Connect dialog ─────────────────────────────────────────────────

    class ConnectDialog(QDialog):
        """
        Login dialog — two tabs:
          • Browser Login  (primary)  — email + password → Playwright opens the real site
          • Paste Token    (advanced) — for users who already have an API access token
        """

        def __init__(self, platform_id: str, platform_info: dict,
                     social_tools, parent=None):
            super().__init__(parent)
            self.platform_id   = platform_id
            self.platform_info = platform_info
            self.social        = social_tools
            self._worker: Optional[QThread] = None

            self.setWindowTitle(f"Connect {platform_info['name']}")
            self.setFixedWidth(480)
            self.setModal(True)
            self.setStyleSheet(f"""
                QDialog   {{ background:{BG}; color:{TEXT}; }}
                QLabel    {{ color:{TEXT}; }}
                QLineEdit {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:6px; padding:8px 10px; font-size:12px;
                }}
                QLineEdit:focus {{ border:1px solid {ACCENT}; }}
            """)

            root = QVBoxLayout(self)
            root.setSpacing(14)
            root.setContentsMargins(24, 20, 24, 20)

            # ── Title ──────────────────────────────────────────────────
            color = platform_info["color"]
            title = QLabel(f"Connect {platform_info['name']}")
            title.setFont(QFont("Segoe UI", 14, QFont.Bold))
            title.setStyleSheet(f"color:{color};")
            root.addWidget(title)

            # ── Tab bar ────────────────────────────────────────────────
            tab_row = QHBoxLayout()
            tab_row.setSpacing(6)
            self._tab_browser = QPushButton("Browser Login")
            self._tab_token   = QPushButton("Paste Token")
            for btn in (self._tab_browser, self._tab_token):
                btn.setFixedHeight(30)
                btn.setCheckable(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{PANEL}; color:{MUTED}; border:1px solid {BORDER};
                        border-radius:6px; padding:0 14px; font-size:11px;
                    }}
                    QPushButton:checked {{
                        background:{ACCENT}; color:#000; border:none; font-weight:bold;
                    }}
                """)
                tab_row.addWidget(btn)
            tab_row.addStretch()
            self._tab_browser.setChecked(True)
            self._tab_browser.clicked.connect(lambda: self._set_tab("browser"))
            self._tab_token.clicked.connect(lambda: self._set_tab("token"))
            root.addLayout(tab_row)

            # ── Stacked pages ──────────────────────────────────────────
            self._stack = QStackedWidget()

            # Page 0 — Browser Login
            browser_page = QWidget()
            bv = QVBoxLayout(browser_page)
            bv.setSpacing(10)
            bv.setContentsMargins(0, 0, 0, 0)

            note = QLabel(
                f"Enter your {platform_info['name']} login credentials below.\n"
                "A browser window will open on screen — log in normally\n"
                "(including 2FA or captcha if prompted). Your session is\n"
                "saved locally so you won't need to log in again."
            )
            note.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            note.setWordWrap(True)
            bv.addWidget(note)

            bv.addWidget(QLabel("Email / Username:"))
            self._email = QLineEdit()
            self._email.setPlaceholderText(f"Your {platform_info['name']} email or username")
            bv.addWidget(self._email)

            bv.addWidget(QLabel("Password:"))
            self._password = QLineEdit()
            self._password.setPlaceholderText("Your password")
            self._password.setEchoMode(QLineEdit.Password)
            bv.addWidget(self._password)

            tip = QLabel(
                "Tip: credentials are used only once to open the login page and\n"
                "are never stored. Only the session cookie is saved."
            )
            tip.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            tip.setWordWrap(True)
            bv.addWidget(tip)

            self._stack.addWidget(browser_page)

            # Page 1 — Paste Token
            token_page = QWidget()
            tv = QVBoxLayout(token_page)
            tv.setSpacing(10)
            tv.setContentsMargins(0, 0, 0, 0)

            token_note = QLabel(
                "Advanced: paste a valid API access token directly.\n"
                "Useful if you already have a developer token."
            )
            token_note.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            token_note.setWordWrap(True)
            tv.addWidget(token_note)

            tv.addWidget(QLabel("Access Token:"))
            self._token_input = QLineEdit()
            self._token_input.setPlaceholderText("Paste access token here")
            self._token_input.setEchoMode(QLineEdit.Password)
            tv.addWidget(self._token_input)

            tv.addWidget(QLabel("Account Name (optional):"))
            self._acc_name = QLineEdit()
            self._acc_name.setPlaceholderText("Your display name or handle")
            tv.addWidget(self._acc_name)

            self._stack.addWidget(token_page)
            root.addWidget(self._stack)

            # ── Progress bar + status ──────────────────────────────────
            self._prog = QProgressBar()
            self._prog.setRange(0, 0)   # indeterminate
            self._prog.setFixedHeight(4)
            self._prog.setVisible(False)
            self._prog.setStyleSheet(f"""
                QProgressBar {{ background:{PANEL}; border:none; border-radius:2px; }}
                QProgressBar::chunk {{ background:{color}; border-radius:2px; }}
            """)
            root.addWidget(self._prog)

            self._status_lbl = QLabel("")
            self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            self._status_lbl.setWordWrap(True)
            self._status_lbl.setMinimumHeight(18)
            root.addWidget(self._status_lbl)

            # ── Action buttons ─────────────────────────────────────────
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)

            self._connect_btn = QPushButton("Open Browser & Login")
            self._connect_btn.setFixedHeight(38)
            self._connect_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self._connect_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{color}; color:#fff; border:none;
                    border-radius:8px; padding:0 20px;
                }}
                QPushButton:hover {{ opacity:0.85; }}
                QPushButton:disabled {{ background:{PANEL2}; color:{MUTED}; }}
            """)
            self._connect_btn.clicked.connect(self._start_login)

            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedHeight(38)
            cancel_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:8px; padding:0 20px;
                }}
                QPushButton:hover {{ background:{PANEL2}; }}
            """)
            cancel_btn.clicked.connect(self._cancel)

            btn_row.addWidget(self._connect_btn, 1)
            btn_row.addWidget(cancel_btn)
            root.addLayout(btn_row)

            # Track result so caller can check
            self._result: dict = {}

        # ── Helpers ────────────────────────────────────────────────────

        def _set_tab(self, mode: str):
            is_browser = (mode == "browser")
            self._tab_browser.setChecked(is_browser)
            self._tab_token.setChecked(not is_browser)
            self._stack.setCurrentIndex(0 if is_browser else 1)
            self._connect_btn.setText(
                "Open Browser & Login" if is_browser else "Connect with Token"
            )

        def _start_login(self):
            if self._tab_token.isChecked():
                self._start_token_login()
            else:
                self._start_browser_login()

        def _start_browser_login(self):
            email    = self._email.text().strip()
            password = self._password.text()
            if not email:
                self._show_status("Please enter your email or username.", RED)
                return

            self._set_busy(True, "Opening browser…")

            self._worker = ConnectWorker(
                self.social, self.platform_id, email, password
            )
            self._worker.progress.connect(self._on_progress)
            self._worker.finished.connect(self._on_done)
            self._worker.start()

        def _start_token_login(self):
            token = self._token_input.text().strip()
            if not token:
                self._show_status("Please paste an access token.", RED)
                return

            self._set_busy(True, "Saving token…")

            self._worker = TokenWorker(
                self.social, self.platform_id, token,
                self._acc_name.text().strip()
            )
            self._worker.finished.connect(self._on_done)
            self._worker.start()

        def _on_progress(self, msg: str):
            self._show_status(msg, MUTED)

        def _on_done(self, success: bool, message: str):
            self._set_busy(False)
            if success:
                self._result = {"success": True, "message": message}
                self._show_status(message, GREEN)
                # Auto-close after a short delay
                QTimer.singleShot(1200, self.accept)
            else:
                self._result = {"success": False, "error": message}
                self._show_status(f"Error: {message}", RED)

        def _cancel(self):
            if self._worker and self._worker.isRunning():
                self._worker.terminate()
                self._worker.wait(2000)
            self.reject()

        def _set_busy(self, busy: bool, msg: str = ""):
            self._prog.setVisible(busy)
            self._connect_btn.setEnabled(not busy)
            if msg:
                self._show_status(msg, MUTED)
            elif not busy:
                pass  # keep existing status

        def _show_status(self, msg: str, color: str = MUTED):
            self._status_lbl.setText(msg)
            self._status_lbl.setStyleSheet(f"color:{color}; font-size:11px;")

        def get_result(self) -> dict:
            return self._result

    # ── Platform card widget ───────────────────────────────────────────

    class PlatformCard(QFrame):
        """One platform row — shows logo, name, status, connect/disconnect button."""

        connect_requested    = Signal(str)   # platform id
        disconnect_requested = Signal(str)

        def __init__(self, platform_id: str, platform_info: dict, parent=None):
            super().__init__(parent)
            self.platform_id = platform_id
            self.pinfo = platform_info
            self._connected = False

            self.setFixedHeight(76)
            self.setStyleSheet(f"""
                PlatformCard {{
                    background:{PANEL};
                    border:1px solid {BORDER};
                    border-radius:10px;
                }}
                PlatformCard:hover {{
                    border:1px solid {platform_info['color']};
                }}
            """)

            row = QHBoxLayout(self)
            row.setContentsMargins(16, 0, 16, 0)
            row.setSpacing(14)

            # Coloured icon box
            self._icon_box = _IconBadge(platform_info["icon"], platform_info["color"])
            row.addWidget(self._icon_box)

            # Name + status
            info_col = QVBoxLayout()
            info_col.setSpacing(2)
            self._name_lbl = QLabel(platform_info["name"])
            self._name_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
            self._name_lbl.setStyleSheet(f"color:{TEXT};")
            self._status_lbl = QLabel("Click to Link")
            self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            info_col.addWidget(self._name_lbl)
            info_col.addWidget(self._status_lbl)
            row.addLayout(info_col, 1)

            # Faded logo accent (right side)
            self._platform_logo = _IconBadge(platform_info["icon"], platform_info["color"], size=36, alpha=40)
            row.addWidget(self._platform_logo)

            # Connect / Disconnect button
            self._btn = QPushButton("Connect")
            self._btn.setFixedSize(110, 36)
            self._btn.setFont(QFont("Segoe UI", 10))
            self._btn.clicked.connect(self._on_btn_click)
            self._apply_btn_style(False)
            row.addWidget(self._btn)

        def _apply_btn_style(self, connected: bool):
            if connected:
                self._btn.setText("Disconnect")
                self._btn.setStyleSheet(f"""
                    QPushButton {{
                        background:#2d1a1a; color:{RED}; border:1px solid {RED};
                        border-radius:8px;
                    }}
                    QPushButton:hover {{ background:#3a1f1f; }}
                """)
            else:
                color = self.pinfo["color"]
                self._btn.setText("Connect")
                self._btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{PANEL2}; color:{color}; border:1px solid {color};
                        border-radius:8px;
                    }}
                    QPushButton:hover {{ background:{PANEL}; }}
                """)

        def _on_btn_click(self):
            if self._connected:
                self.disconnect_requested.emit(self.platform_id)
            else:
                self.connect_requested.emit(self.platform_id)

        def set_status(self, connected: bool, account_name: str = "", connecting: bool = False):
            self._connected = connected
            if connecting:
                self._status_lbl.setText("Connecting…")
                self._status_lbl.setStyleSheet(f"color:{YELLOW}; font-size:11px;")
                self._btn.setEnabled(False)
                return

            self._btn.setEnabled(True)
            self._apply_btn_style(connected)

            if connected:
                label = f"Connected{' — ' + account_name if account_name else ''}"
                self._status_lbl.setText(label)
                self._status_lbl.setStyleSheet(f"color:{GREEN}; font-size:11px;")
                self.setStyleSheet(f"""
                    PlatformCard {{
                        background:{PANEL};
                        border:1px solid {GREEN};
                        border-radius:10px;
                    }}
                """)
            else:
                self._status_lbl.setText("Click to Link")
                self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;")
                self.setStyleSheet(f"""
                    PlatformCard {{
                        background:{PANEL};
                        border:1px solid {BORDER};
                        border-radius:10px;
                    }}
                    PlatformCard:hover {{
                        border:1px solid {self.pinfo['color']};
                    }}
                """)

    class _IconBadge(QWidget):
        """Coloured rounded square with 1-3 letter label."""
        def __init__(self, text: str, color: str, size: int = 44, alpha: int = 255):
            super().__init__()
            self._text = text.upper()[:3]
            self._color = QColor(color)
            self._color.setAlpha(alpha)
            self._size = size
            self.setFixedSize(size, size)

        def paintEvent(self, _):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QBrush(self._color))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 0, self._size, self._size, 8, 8)
            p.setPen(QPen(QColor(255, 255, 255, 220)))
            font = QFont("Segoe UI", max(8, self._size // 4), QFont.Bold)
            p.setFont(font)
            p.drawText(0, 0, self._size, self._size, Qt.AlignCenter, self._text)
            p.end()

    # ── Post composer widget ───────────────────────────────────────────

    class PostComposer(QWidget):
        """Simple post composer for multi-platform posting."""

        post_requested = Signal(str, list)   # text, [platform_ids]

        def __init__(self, social_tools, parent=None):
            super().__init__(parent)
            self.social = social_tools

            v = QVBoxLayout(self)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(8)

            header = QLabel("Compose & Post")
            header.setFont(QFont("Segoe UI", 12, QFont.Bold))
            header.setStyleSheet(f"color:{TEAL};")
            v.addWidget(header)

            self._text = QTextEdit()
            self._text.setPlaceholderText(
                "Write your post here…\n\n"
                "Tip: You can also use the chat panel to post by typing:\n"
                '  "Post this on LinkedIn: Your content here"'
            )
            self._text.setFixedHeight(120)
            self._text.setStyleSheet(f"""
                QTextEdit {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:8px; padding:8px; font-size:12px;
                }}
            """)
            v.addWidget(self._text)

            # Platform selector row
            plat_row = QHBoxLayout()
            plat_row.addWidget(QLabel("Post to:"))
            self._platform_checkboxes: dict[str, QPushButton] = {}

            from ..tools_ext.social_tools import PLATFORMS
            for pid, pinfo in PLATFORMS.items():
                btn = QPushButton(pinfo["name"].split()[0])
                btn.setCheckable(True)
                btn.setFixedHeight(28)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{PANEL2}; color:{MUTED}; border:1px solid {BORDER};
                        border-radius:6px; padding:0 10px; font-size:10px;
                    }}
                    QPushButton:checked {{
                        background:{pinfo['color']}; color:#fff; border:none;
                    }}
                """)
                self._platform_checkboxes[pid] = btn
                plat_row.addWidget(btn)

            plat_row.addStretch()
            v.addLayout(plat_row)

            # Buttons
            btn_row = QHBoxLayout()
            self._post_btn = QPushButton("Post Now")
            self._post_btn.setFixedHeight(36)
            self._post_btn.setFont(QFont("Segoe UI", 11))
            self._post_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{GREEN}; color:#0d1117; border:none;
                    border-radius:8px; padding:0 24px;
                }}
                QPushButton:hover {{ background:#56d364; }}
                QPushButton:disabled {{ background:{PANEL}; color:{MUTED}; }}
            """)
            self._post_btn.clicked.connect(self._on_post)

            self._result_lbl = QLabel("")
            self._result_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            self._result_lbl.setWordWrap(True)

            btn_row.addWidget(self._post_btn)
            btn_row.addWidget(self._result_lbl, 1)
            v.addLayout(btn_row)

            # Mark connected platforms as selected
            self.refresh_connections()

        def refresh_connections(self):
            for pid, btn in self._platform_checkboxes.items():
                connected = self.social.is_connected(pid)
                btn.setChecked(connected)
                btn.setEnabled(connected)

        def _on_post(self):
            text = self._text.toPlainText().strip()
            if not text:
                self._result_lbl.setText("Please write something first.")
                self._result_lbl.setStyleSheet(f"color:{RED};")
                return

            targets = [pid for pid, btn in self._platform_checkboxes.items() if btn.isChecked()]
            if not targets:
                self._result_lbl.setText("Select at least one platform above.")
                self._result_lbl.setStyleSheet(f"color:{RED};")
                return

            self._post_btn.setEnabled(False)
            self._result_lbl.setText("Posting…")
            self._result_lbl.setStyleSheet(f"color:{MUTED};")
            QApplication.processEvents()

            result = self.social.post_to_all(text, platforms=targets)

            self._post_btn.setEnabled(True)
            if result.get("success"):
                succeeded = result.get("succeeded", [])
                from ..tools_ext.social_tools import PLATFORMS as _P
                names = ", ".join(_P[p]["name"] for p in succeeded)
                self._result_lbl.setText(f"Posted to {names}!")
                self._result_lbl.setStyleSheet(f"color:{GREEN};")
                self._text.clear()
            else:
                self._result_lbl.setText(result.get("error", "Post failed"))
                self._result_lbl.setStyleSheet(f"color:{RED};")

    # ── Main SocialTab widget ──────────────────────────────────────────

    class SocialTab(QWidget):
        """Full social media management tab for MainWindow."""

        def __init__(self, social_tools, parent=None):
            super().__init__(parent)
            self.social = social_tools
            self._workers: dict[str, QThread] = {}
            self._cards:   dict[str, PlatformCard] = {}

            self.setStyleSheet(f"background:{BG};")
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            # Scrollable content
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{BG}; }}")
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

            content = QWidget()
            content.setStyleSheet(f"background:{BG};")
            cv = QVBoxLayout(content)
            cv.setContentsMargins(20, 16, 20, 20)
            cv.setSpacing(16)

            # Header with vibrant gradient bar
            hdr_bar = QFrame()
            hdr_bar.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {GREEN}25, stop:0.7 {TEAL}10, stop:1 transparent);
                    border-left:5px solid {GREEN};
                    border-radius:6px;
                }}
            """)
            hdr_bar_l = QHBoxLayout(hdr_bar)
            hdr_bar_l.setContentsMargins(12, 6, 12, 6)
            hdr = QLabel("Social Accounts")
            hdr.setFont(QFont("Segoe UI", 14, QFont.Bold))
            hdr.setStyleSheet(f"color:{GREEN}; background:transparent; border:none;")
            hdr_bar_l.addWidget(hdr)
            hdr_bar_l.addStretch()
            cv.addWidget(hdr_bar)

            sub = QLabel(
                "Connect your social media accounts to let the AI agent post, "
                "read, and manage your content automatically."
            )
            sub.setStyleSheet(f"color:{MUTED}; font-size:12px;")
            sub.setWordWrap(True)
            cv.addWidget(sub)

            # Platform cards
            from ..tools_ext.social_tools import PLATFORMS
            for pid, pinfo in PLATFORMS.items():
                card = PlatformCard(pid, pinfo)
                card.connect_requested.connect(self._on_connect_requested)
                card.disconnect_requested.connect(self._on_disconnect_requested)
                self._cards[pid] = card
                cv.addWidget(card)

            # Divider
            div = QFrame()
            div.setFrameShape(QFrame.HLine)
            div.setStyleSheet(f"color:{BORDER};")
            cv.addWidget(div)

            # Post composer
            self._composer = PostComposer(self.social)
            cv.addWidget(self._composer)

            cv.addStretch()
            scroll.setWidget(content)
            root.addWidget(scroll)

            # Initial status refresh
            self.refresh_all()

        def refresh_all(self):
            """Refresh all card statuses from stored accounts."""
            status = self.social.get_connection_status()
            for pid, card in self._cards.items():
                s = status.get(pid, {})
                card.set_status(
                    connected=s.get("connected", False),
                    account_name=s.get("account_name", ""),
                )
            self._composer.refresh_connections()

        # ── Connect flow ───────────────────────────────────────────────

        def _on_connect_requested(self, platform_id: str):
            from ..tools_ext.social_tools import PLATFORMS
            pinfo = PLATFORMS[platform_id]

            dialog = ConnectDialog(platform_id, pinfo, self.social, self)
            result_code = dialog.exec()

            # ConnectDialog auto-accepts on success; if user manually closed check result
            if result_code == QDialog.Accepted or dialog.get_result().get("success"):
                self.refresh_all()
                msg = dialog.get_result().get("message", f"{pinfo['name']} connected!")
                self._show_toast(msg, GREEN)
            else:
                err = dialog.get_result().get("error", "")
                if err:
                    self._show_toast(f"Failed: {err[:80]}", RED)

        def _on_disconnect_requested(self, platform_id: str):
            from ..tools_ext.social_tools import PLATFORMS
            pname = PLATFORMS[platform_id]["name"]
            reply = QMessageBox.question(
                self, f"Disconnect {pname}",
                f"Are you sure you want to disconnect {pname}?\n"
                "Your stored session will be removed.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.social.disconnect(platform_id)
                self.refresh_all()
                self._show_toast(f"Disconnected from {pname}", YELLOW)

        def _show_toast(self, msg: str, _color: str = MUTED):
            """Brief status message shown in the main window status bar."""
            mw = self.window()
            if hasattr(mw, "status_bar"):
                mw.status_bar.showMessage(msg, 5000)

    # ── GitHub PAT connect worker ──────────────────────────────────────

    class GitHubConnectWorker(QThread):
        """Validates a GitHub PAT in a background thread."""
        finished = Signal(bool, str, str)   # success, message, username

        def __init__(self, token: str, username: str):
            super().__init__()
            self._token    = token
            self._username = username

        def run(self):
            try:
                from ..integrations.github_service import get_github_service
                svc = get_github_service()
                result = svc.set_token(self._token, self._username)
                if result.get("success"):
                    uname = result.get("username", self._username)
                    self.finished.emit(True, f"Connected as {uname}", uname)
                else:
                    self.finished.emit(False, result.get("error", "Authentication failed"), "")
            except Exception as exc:
                self.finished.emit(False, str(exc), "")

    # ── GitHub connect dialog ──────────────────────────────────────────

    class GitHubConnectDialog(QDialog):
        """Dialog for connecting a GitHub account via Personal Access Token."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Connect GitHub")
            self.setFixedWidth(480)
            self.setModal(True)
            self.setStyleSheet(f"""
                QDialog   {{ background:{BG}; color:{TEXT}; }}
                QLabel    {{ color:{TEXT}; }}
                QLineEdit {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:6px; padding:8px 10px; font-size:12px;
                }}
                QLineEdit:focus {{ border:1px solid #6e40c9; }}
            """)

            GITHUB_COLOR = "#6e40c9"

            root = QVBoxLayout(self)
            root.setSpacing(14)
            root.setContentsMargins(24, 20, 24, 20)

            title = QLabel("Connect GitHub")
            title.setFont(QFont("Segoe UI", 14, QFont.Bold))
            title.setStyleSheet(f"color:{GITHUB_COLOR};")
            root.addWidget(title)

            note = QLabel(
                "Paste a GitHub Personal Access Token (PAT) to allow MegaV to\n"
                "create repos, manage files, open issues, and push commits.\n\n"
                "Required scopes: repo, workflow (optional for Actions)"
            )
            note.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            note.setWordWrap(True)
            root.addWidget(note)

            root.addWidget(QLabel("GitHub Username (optional — auto-detected):"))
            self._username = QLineEdit()
            self._username.setPlaceholderText("e.g. octocat")
            root.addWidget(self._username)

            root.addWidget(QLabel("Personal Access Token:"))
            self._token = QLineEdit()
            self._token.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxx")
            self._token.setEchoMode(QLineEdit.Password)
            root.addWidget(self._token)

            how = QLabel(
                "Create a token at: github.com → Settings → Developer settings\n"
                "→ Personal access tokens → Tokens (classic) → Generate new token"
            )
            how.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            how.setWordWrap(True)
            root.addWidget(how)

            self._prog = QProgressBar()
            self._prog.setRange(0, 0)
            self._prog.setFixedHeight(4)
            self._prog.setVisible(False)
            self._prog.setStyleSheet(f"""
                QProgressBar {{ background:{PANEL}; border:none; border-radius:2px; }}
                QProgressBar::chunk {{ background:{GITHUB_COLOR}; border-radius:2px; }}
            """)
            root.addWidget(self._prog)

            self._status_lbl = QLabel("")
            self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            self._status_lbl.setWordWrap(True)
            self._status_lbl.setMinimumHeight(18)
            root.addWidget(self._status_lbl)

            btn_row = QHBoxLayout()
            self._connect_btn = QPushButton("Connect")
            self._connect_btn.setFixedHeight(38)
            self._connect_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self._connect_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{GITHUB_COLOR}; color:#fff; border:none;
                    border-radius:8px; padding:0 20px;
                }}
                QPushButton:hover {{ background:#7c4ddd; }}
                QPushButton:disabled {{ background:{PANEL2}; color:{MUTED}; }}
            """)
            self._connect_btn.clicked.connect(self._start_connect)

            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedHeight(38)
            cancel_btn.setStyleSheet(f"""
                QPushButton {{
                    background:{PANEL}; color:{TEXT}; border:1px solid {BORDER};
                    border-radius:8px; padding:0 20px;
                }}
                QPushButton:hover {{ background:{PANEL2}; }}
            """)
            cancel_btn.clicked.connect(self.reject)

            btn_row.addWidget(self._connect_btn, 1)
            btn_row.addWidget(cancel_btn)
            root.addLayout(btn_row)

            self._result: dict = {}
            self._worker: Optional[QThread] = None

        def _start_connect(self):
            token = self._token.text().strip()
            if not token:
                self._show_status("Please enter a Personal Access Token.", RED)
                return
            self._prog.setVisible(True)
            self._connect_btn.setEnabled(False)
            self._show_status("Validating token…", MUTED)

            self._worker = GitHubConnectWorker(token, self._username.text().strip())
            self._worker.finished.connect(self._on_done)
            self._worker.start()

        def _on_done(self, success: bool, message: str, username: str):
            self._prog.setVisible(False)
            self._connect_btn.setEnabled(True)
            if success:
                self._result = {"success": True, "message": message, "username": username}
                self._show_status(message, GREEN)
                QTimer.singleShot(1200, self.accept)
            else:
                self._result = {"success": False, "error": message}
                self._show_status(f"Error: {message}", RED)

        def _show_status(self, msg: str, color: str = MUTED):
            self._status_lbl.setText(msg)
            self._status_lbl.setStyleSheet(f"color:{color}; font-size:11px;")

        def get_result(self) -> dict:
            return self._result

    # ── GitHub card widget ─────────────────────────────────────────────

    class GitHubCard(QFrame):
        """GitHub account card — PAT-based auth, activity log."""

        connect_requested    = Signal()
        disconnect_requested = Signal()

        GITHUB_COLOR = "#6e40c9"
        GITHUB_COLOR2 = "#24292e"

        def __init__(self, parent=None):
            super().__init__(parent)
            self._connected  = False
            self._username   = ""
            self._last_action = ""

            self.setStyleSheet(f"""
                GitHubCard {{
                    background:{PANEL};
                    border:1px solid {BORDER};
                    border-radius:10px;
                }}
                GitHubCard:hover {{
                    border:1px solid {GitHubCard.GITHUB_COLOR};
                }}
            """)

            main_v = QVBoxLayout(self)
            main_v.setContentsMargins(16, 12, 16, 12)
            main_v.setSpacing(8)

            # ── Top row (icon + info + button) ─────────────────────────
            top_row = QHBoxLayout()
            top_row.setSpacing(14)

            icon = _IconBadge("GH", self.GITHUB_COLOR, size=44)
            top_row.addWidget(icon)

            info_col = QVBoxLayout()
            info_col.setSpacing(2)
            self._name_lbl = QLabel("GitHub")
            self._name_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
            self._name_lbl.setStyleSheet(f"color:{TEXT};")
            self._status_lbl = QLabel("Click to Link")
            self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            info_col.addWidget(self._name_lbl)
            info_col.addWidget(self._status_lbl)
            top_row.addLayout(info_col, 1)

            # Faded accent
            top_row.addWidget(_IconBadge("GH", self.GITHUB_COLOR, size=36, alpha=40))

            self._btn = QPushButton("Connect")
            self._btn.setFixedSize(110, 36)
            self._btn.setFont(QFont("Segoe UI", 10))
            self._btn.clicked.connect(self._on_btn_click)
            self._apply_btn_style(False)
            top_row.addWidget(self._btn)
            main_v.addLayout(top_row)

            # ── Activity log row ───────────────────────────────────────
            self._activity_lbl = QLabel("")
            self._activity_lbl.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            self._activity_lbl.setWordWrap(True)
            self._activity_lbl.setVisible(False)
            main_v.addWidget(self._activity_lbl)

        def _apply_btn_style(self, connected: bool):
            if connected:
                self._btn.setText("Disconnect")
                self._btn.setStyleSheet(f"""
                    QPushButton {{
                        background:#2d1a1a; color:{RED}; border:1px solid {RED};
                        border-radius:8px;
                    }}
                    QPushButton:hover {{ background:#3a1f1f; }}
                """)
            else:
                c = self.GITHUB_COLOR
                self._btn.setText("Connect")
                self._btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{PANEL2}; color:{c}; border:1px solid {c};
                        border-radius:8px;
                    }}
                    QPushButton:hover {{ background:{PANEL}; }}
                """)

        def _on_btn_click(self):
            if self._connected:
                self.disconnect_requested.emit()
            else:
                self.connect_requested.emit()

        def set_status(self, connected: bool, username: str = ""):
            self._connected = connected
            self._username  = username
            self._btn.setEnabled(True)
            self._apply_btn_style(connected)

            if connected:
                label = f"Connected{' — @' + username if username else ''}"
                self._status_lbl.setText(label)
                self._status_lbl.setStyleSheet(f"color:{GREEN}; font-size:11px;")
                self.setStyleSheet(f"""
                    GitHubCard {{
                        background:{PANEL};
                        border:1px solid {GREEN};
                        border-radius:10px;
                    }}
                """)
            else:
                self._status_lbl.setText("Click to Link")
                self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;")
                self.setStyleSheet(f"""
                    GitHubCard {{
                        background:{PANEL};
                        border:1px solid {BORDER};
                        border-radius:10px;
                    }}
                    GitHubCard:hover {{
                        border:1px solid {self.GITHUB_COLOR};
                    }}
                """)
                self._activity_lbl.setVisible(False)

        def log_activity(self, message: str, success: bool = True):
            """Show the last GitHub action result inline."""
            color = GREEN if success else RED
            self._activity_lbl.setText(f"Last action: {message}")
            self._activity_lbl.setStyleSheet(f"color:{color}; font-size:10px;")
            self._activity_lbl.setVisible(True)

    # ── Patch SocialTab to include GitHub section ──────────────────────

    # Save original __init__
    _SocialTab_orig_init = SocialTab.__init__
    _SocialTab_orig_refresh = SocialTab.refresh_all

    def _social_tab_new_init(self, social_tools, parent=None):
        _SocialTab_orig_init(self, social_tools, parent)
        self._github_card: Optional[GitHubCard] = None

        # Find the scroll content widget and add GitHub section after the divider
        scroll_area = self.findChild(QScrollArea)
        if not scroll_area:
            return
        content = scroll_area.widget()
        if not content:
            return
        cv = content.layout()
        if not cv:
            return

        # Insert a section header for "Dev Platforms"
        gh_sep = QFrame()
        gh_sep.setFrameShape(QFrame.HLine)
        gh_sep.setStyleSheet(f"color:{BORDER};")

        gh_hdr_bar = QFrame()
        gh_hdr_bar.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #6e40c925, stop:0.7 #6e40c910, stop:1 transparent);
                border-left:5px solid #6e40c9;
                border-radius:6px;
            }}
        """)
        gh_hdr_bar_l = QHBoxLayout(gh_hdr_bar)
        gh_hdr_bar_l.setContentsMargins(12, 6, 12, 6)
        gh_lbl = QLabel("Dev Platforms")
        gh_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        gh_lbl.setStyleSheet("color:#6e40c9; background:transparent; border:none;")
        gh_hdr_bar_l.addWidget(gh_lbl)
        gh_hdr_bar_l.addStretch()

        card = GitHubCard()
        card.connect_requested.connect(lambda: _gh_on_connect(self))
        card.disconnect_requested.connect(lambda: _gh_on_disconnect(self))
        self._github_card = card

        # Insert before the stretch (last item)
        # Remove the stretch, insert new widgets, re-add stretch
        count = cv.count()
        stretch_item = None
        if count > 0:
            stretch_item = cv.itemAt(count - 1)
            if stretch_item and stretch_item.spacerItem():
                cv.removeItem(stretch_item)
            else:
                stretch_item = None

        cv.addWidget(gh_sep)
        cv.addWidget(gh_hdr_bar)
        cv.addWidget(card)

        if stretch_item:
            cv.addStretch()

        # Restore GitHub status
        _gh_refresh(self)

    def _gh_refresh(tab):
        """Refresh GitHub card status from service."""
        try:
            from ..integrations.github_service import get_github_service
            svc = get_github_service()
            if svc.is_connected():
                st = svc.connection_status()
                uname = st.get("username", "")
                if tab._github_card:
                    tab._github_card.set_status(True, uname)
            else:
                if tab._github_card:
                    tab._github_card.set_status(False)
        except Exception:
            pass

    def _gh_on_connect(tab):
        dialog = GitHubConnectDialog(tab)
        result_code = dialog.exec()
        if result_code == QDialog.Accepted or dialog.get_result().get("success"):
            _gh_refresh(tab)
            msg = dialog.get_result().get("message", "GitHub connected!")
            tab._show_toast(msg, GREEN)
        else:
            err = dialog.get_result().get("error", "")
            if err:
                tab._show_toast(f"GitHub: {err[:80]}", RED)

    def _gh_on_disconnect(tab):
        reply = QMessageBox.question(
            tab, "Disconnect GitHub",
            "Remove your GitHub token from MegaV?\n"
            "You can reconnect at any time.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                from ..integrations.github_service import get_github_service
                get_github_service().disconnect()
            except Exception:
                pass
            if tab._github_card:
                tab._github_card.set_status(False)
            tab._show_toast("Disconnected from GitHub", YELLOW)

    def _social_tab_new_refresh(self):
        _SocialTab_orig_refresh(self)
        _gh_refresh(self)

    SocialTab.__init__    = _social_tab_new_init
    SocialTab.refresh_all = _social_tab_new_refresh
    SocialTab.log_github_activity = lambda self, msg, ok=True: (
        self._github_card.log_activity(msg, ok) if self._github_card else None
    )
