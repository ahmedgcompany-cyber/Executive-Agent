"""Main window — MegaV · colorful redesign with profile editor."""

import datetime
import sys
import os

# Debug: log when module is loaded
_log_file = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "app_debug.log"
)


def _log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] main_window: {msg}\n"
    try:
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


_log("Module loading...")

try:
    from PySide6.QtWidgets import (
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QTabWidget,
        QTabBar,
        QTextEdit,
        QLineEdit,
        QPushButton,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QSplitter,
        QStatusBar,
        QMessageBox,
        QApplication,
        QProgressBar,
        QFileDialog,
        QToolButton,
        QDialog,
        QScrollArea,
        QFrame,
        QFormLayout,
        QSpinBox,
        QSizePolicy,
        QComboBox,
    )
    from PySide6.QtCore import Qt, QThread, Signal, QTimer
    from PySide6.QtGui import (
        QAction,
        QFont,
        QColor,
        QIcon,
        QPainter,
        QBrush,
        QLinearGradient,
    )

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

    class QMainWindow:  # type: ignore
        pass


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _short_path(path: str, max_len: int = 40) -> str:
    """Truncate a long path to last max_len chars with leading ellipsis."""
    if len(path) <= max_len:
        return path
    return "…" + path[-(max_len - 1) :]


# ── Design tokens — Claude warm base + neon accents ──────────────────────────
C = {
    # Claude-inspired warm base
    "bg": "#1c1917",
    "surface": "#272420",
    "surface2": "#332e28",
    "surface3": "#3f3830",
    "border": "#4a4138",
    # Claude signature accent
    "claude_orange": "#e8825c",
    "claude_amber": "#d4a574",
    "claude_warm": "#c8956c",
    # Text
    "text": "#f5f0ea",
    "text_dim": "#c4bbb0",
    "muted": "#8a8279",
    # Vibrant neon accents (no purple primary)
    "blue": "#4d9fff",
    "cyan": "#00e5ff",
    "neon_pink": "#ff2d95",
    "electric_yellow": "#ffe033",
    "lime_green": "#7dff3a",
    "hot_orange": "#ff6d2e",
    "teal": "#00e5a0",
    "sky_blue": "#38bdf8",
    "amber": "#ffb020",
    "pink": "#ff3e8a",
    "green": "#00e676",
    "red": "#ff4444",
    "orange": "#ff8c00",
    "gray": "#64748b",
    # Shadows (simulated via border/bg in Qt)
    "shadow_orange": "rgba(232,130,92,0.15)",
    "shadow_cyan": "rgba(0,229,255,0.1)",
    "shadow_pink": "rgba(255,45,149,0.1)",
    "shadow_lime": "rgba(125,255,58,0.08)",
    "border_warm": "rgba(232,130,92,0.2)",
}

# Per-tab accent [AI Status, Tasks, Skills, Profile, Email, Social, Logs, Approvals, Dashboard, Discovery]
TAB_COLORS = [
    C["claude_orange"], C["electric_yellow"], C["cyan"], C["neon_pink"],
    C["lime_green"], C["teal"], C["sky_blue"], C["red"], C["green"], C["orange"],
]
TAB_GRADIENTS = [
    (C["claude_orange"], C["hot_orange"]),
    (C["electric_yellow"], C["amber"]),
    (C["cyan"], C["sky_blue"]),
    (C["neon_pink"], C["red"]),
    (C["lime_green"], C["teal"]),
    (C["teal"], C["cyan"]),
    (C["sky_blue"], C["blue"]),
    (C["red"], C["pink"]),
    (C["green"], C["lime_green"]),
    (C["orange"], C["amber"]),
]

# ─────────────────────────────────────────────────────────────────────────────
APP_STYLESHEET = (
    "QMainWindow, QWidget {"
    f"background:{C['bg']}; color:{C['text']};"
    "font-family:'Segoe UI',system-ui,sans-serif; }"
    "QSplitter::handle { background:" + C["border"] + "; width:2px; }"
    "QMenuBar { background:" + C["surface"] + "; color:" + C["text"] + ";"
    "border-bottom:1px solid " + C["border"] + "; padding:2px 6px; }"
    "QMenuBar::item:selected { background:" + C["surface3"] + "; border-radius:4px; }"
    "QMenu { background:" + C["surface"] + "; color:" + C["text"] + ";"
    "border:1px solid " + C["border"] + "; border-radius:8px; padding:6px; }"
    "QMenu::item:selected { background:"
    + C["claude_orange"]
    + "; border-radius:4px; color:#fff; }"
    "QLineEdit, QTextEdit, QSpinBox {"
    "background:" + C["surface"] + "; color:" + C["text"] + ";"
    "border:1px solid " + C["border"] + "; border-radius:10px;"
    "padding:6px 10px; font-size:10pt; }"
    "QLineEdit:focus, QTextEdit:focus {"
    "border:1px solid " + C["claude_orange"] + "; background:" + C["surface2"] + "; }"
    "QPushButton {"
    "background:" + C["surface2"] + "; color:" + C["text"] + ";"
    "border:1px solid " + C["border"] + "; border-radius:8px;"
    "padding:7px 18px; font-size:10pt; font-weight:600; }"
    "QPushButton:hover { background:"
    + C["claude_orange"]
    + "; border-color:"
    + C["claude_orange"]
    + "; color:#fff; }"
    "QPushButton:pressed { background:#c06a42; }"
    "QPushButton:disabled { background:"
    + C["surface"]
    + "; color:"
    + C["muted"]
    + "; }"
    "QPushButton#send_btn { background:" + C["claude_orange"] + "; color:#fff; border:none;"
    "border-radius:10px; font-weight:700; min-width:80px; }"
    "QPushButton#send_btn:hover { background:#c06a42; }"
    "QPushButton#send_btn:disabled { background:"
    + C["surface2"]
    + "; color:"
    + C["muted"]
    + "; }"
    "QPushButton#danger_btn { background:transparent; color:" + C["neon_pink"] + ";"
    "border:1px solid "
    + C["neon_pink"]
    + "; border-radius:6px; padding:4px 12px; font-size:9pt; }"
    "QPushButton#danger_btn:hover { background:rgba(255,45,149,0.1); }"
    "QToolButton { background:" + C["surface"] + "; color:" + C["claude_amber"] + ";"
    "border:1px solid " + C["border"] + "; border-radius:8px; font-size:16pt; }"
    "QToolButton:hover { background:"
    + C["surface2"]
    + "; border-color:"
    + C["claude_orange"]
    + "; color:"
    + C["claude_orange"]
    + "; }"
    "QListWidget { background:" + C["surface"] + "; color:" + C["text"] + ";"
    "border:1px solid "
    + C["border"]
    + "; border-radius:8px; padding:4px; font-size:9pt; }"
    "QListWidget::item { padding:4px 8px; border-radius:4px; }"
    "QListWidget::item:selected { background:"
    + C["surface3"]
    + "; color:"
    + C["claude_orange"]
    + "; }"
    "QListWidget::item:hover { background:" + C["surface2"] + "; }"
    "QTabWidget::pane { background:"
    + C["surface"]
    + "; border:1px solid "
    + C["border"]
    + ";"
    "border-radius:0 0 10px 10px; top:-1px; }"
    "QTabBar { background:transparent; border:none; }"
    "QTabBar::tab { background:" + C["surface"] + "; color:" + C["muted"] + ";"
    "border:1px solid " + C["border"] + "; border-bottom:none;"
    "border-radius:8px 8px 0 0; padding:10px 18px; font-size:9pt;"
    "font-weight:700; min-width:64px; margin-right:2px; }"
    "QTabBar::tab:selected { background:"
    + C["surface2"]
    + "; color:"
    + C["text"]
    + "; }"
    "QTabBar::tab:hover:!selected { background:"
    + C["surface2"]
    + "; color:"
    + C["text_dim"]
    + "; }"
    "QScrollBar:vertical { background:"
    + C["surface"]
    + "; width:6px; border-radius:3px; }"
    "QScrollBar::handle:vertical { background:"
    + C["border"]
    + "; border-radius:3px; min-height:30px; }"
    "QScrollBar::handle:vertical:hover { background:" + C["claude_orange"] + "; }"
    "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }"
    "QScrollBar:horizontal { background:"
    + C["surface"]
    + "; height:6px; border-radius:3px; }"
    "QScrollBar::handle:horizontal { background:"
    + C["border"]
    + "; border-radius:3px; min-width:30px; }"
    "QScrollBar::handle:horizontal:hover { background:" + C["claude_orange"] + "; }"
    "QProgressBar { background:"
    + C["surface"]
    + "; border:none; border-radius:3px; max-height:5px; }"
    "QProgressBar::chunk { background:" + C["claude_orange"] + "; border-radius:3px; }"
    "QStatusBar { background:" + C["surface"] + "; color:" + C["muted"] + ";"
    "border-top:1px solid " + C["border"] + "; font-size:9pt; padding:2px 8px; }"
    "QDialog { background:" + C["bg"] + "; color:" + C["text"] + "; }"
    "QLabel { color:" + C["text"] + "; }"
    "QFrame { color:" + C["border"] + "; }"
    "QSpinBox::up-button, QSpinBox::down-button {"
    "background:" + C["surface2"] + "; border:none; width:18px; }"
)


# ── Colored tab bar ───────────────────────────────────────────────────────────

if PYSIDE_AVAILABLE:

    class _ColoredTabBar(QTabWidget):
        """QTabWidget with gradient color strips painted under each tab."""

        def __init__(self, parent=None):
            super().__init__(parent)
            bar = _VividTabBar(TAB_COLORS, TAB_GRADIENTS, self)
            self.setTabBar(bar)

    class _VividTabBar(QTabBar):
        def __init__(self, colors: list, gradients: list, parent=None):
            super().__init__(parent)
            self._colors = colors
            self._gradients = gradients

        def paintEvent(self, event):
            super().paintEvent(event)
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            for i in range(self.count()):
                rect = self.tabRect(i)
                c0, c1 = self._gradients[i % len(self._gradients)]
                active = i == self.currentIndex()
                thickness = 5 if active else 2
                grad = QLinearGradient(
                    rect.x(),
                    rect.bottom() - thickness,
                    rect.x() + rect.width(),
                    rect.bottom() - thickness,
                )
                grad.setColorAt(0, QColor(c0))
                grad.setColorAt(1, QColor(c1))
                p.fillRect(
                    rect.x() + 4,
                    rect.bottom() - thickness,
                    rect.width() - 8,
                    thickness,
                    QBrush(grad),
                )
                if active:
                    glow = QColor(c0)
                    glow.setAlpha(25)
                    p.fillRect(
                        rect.x() + 4,
                        rect.bottom() - 14,
                        rect.width() - 8,
                        9,
                        QBrush(glow),
                    )
            p.end()

    class _SplashBackground(QWidget):
        """Warm gradient blobs painted behind the chat area."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAttribute(Qt.WA_StyledBackground, True)
            self.setStyleSheet("background:transparent;")

        def paintEvent(self, event):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setOpacity(0.12)
            w, h = self.width(), self.height()
            blobs = [
                (0.15, 0.20, 180, C["claude_orange"]),
                (0.80, 0.35, 200, C["cyan"]),
                (0.50, 0.75, 160, C["neon_pink"]),
                (0.25, 0.65, 120, C["lime_green"]),
                (0.70, 0.15, 140, C["claude_amber"]),
            ]
            for bx, by, br, bc in blobs:
                grad = QLinearGradient(int(w * bx), int(h * by - br), int(w * bx), int(h * by + br))
                grad.setColorAt(0, QColor(bc))
                grad.setColorAt(1, QColor(bc))
                grad.setColorAt(0, QColor(bc + "40"))
                grad.setColorAt(1, QColor(bc + "00"))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.NoPen)
                p.drawEllipse(int(w * bx - br), int(h * by - br), br * 2, br * 2)
            p.end()

    class _NeonLoadingBar(QWidget):
        """3-color gradient loading bar (orange → cyan → lime)."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedHeight(4)
            self._offset = 0.0
            self._timer = QTimer(self)
            self._timer.setInterval(16)
            self._timer.timeout.connect(self._tick)

        def _tick(self):
            self._offset = (self._offset + 0.015) % 2.0
            self.update()

        def start(self):
            self._timer.start()

        def stop(self):
            self._timer.stop()
            self.update()

        def paintEvent(self, event):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            w, h = self.width(), self.height()
            bar_w = int(w * 0.35)
            x = int((self._offset / 2.0) * (w + bar_w)) - bar_w
            grad = QLinearGradient(x, 0, x + bar_w, 0)
            grad.setColorAt(0.0, QColor(C["claude_orange"] + "00"))
            grad.setColorAt(0.2, QColor(C["claude_orange"]))
            grad.setColorAt(0.5, QColor(C["cyan"]))
            grad.setColorAt(0.8, QColor(C["lime_green"]))
            grad.setColorAt(1.0, QColor(C["lime_green"] + "00"))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(x, 0, bar_w, h, 2, 2)
            p.end()


# ── Edit Profile dialog ───────────────────────────────────────────────────────

if PYSIDE_AVAILABLE:

    class EditProfileDialog(QDialog):
        """Full profile editor — all fields, saves on confirm."""

        profile_saved = Signal(dict)

        _DIALOG_SS = (
            "QDialog { background:" + C["bg"] + "; color:" + C["text"] + "; }"
            "QLabel { color:" + C["text"] + "; }"
            "QLineEdit, QTextEdit, QSpinBox {"
            "background:" + C["surface"] + "; color:" + C["text"] + ";"
            "border:1px solid "
            + C["border"]
            + "; border-radius:6px; padding:6px 8px; }"
            "QLineEdit:focus, QTextEdit:focus { border:1px solid " + C["pink"] + "; }"
            "QPushButton { background:" + C["surface2"] + "; color:" + C["text"] + ";"
            "border:1px solid "
            + C["border"]
            + "; border-radius:6px; padding:6px 16px; font-weight:600; }"
            "QPushButton:hover { background:"
            + C["pink"]
            + "; color:#fff; border-color:"
            + C["pink"]
            + "; }"
            "QTabWidget::pane { background:"
            + C["surface"]
            + "; border:1px solid "
            + C["border"]
            + ";"
            "border-radius:0 0 8px 8px; }"
            "QTabBar::tab { background:" + C["surface"] + "; color:" + C["muted"] + ";"
            "border:1px solid " + C["border"] + "; border-bottom:none;"
            "border-radius:6px 6px 0 0; padding:6px 14px; font-size:9pt; margin-right:2px; }"
            "QTabBar::tab:selected { background:"
            + C["surface2"]
            + "; color:"
            + C["pink"]
            + "; }"
            "QScrollArea { border:none; background:transparent; }"
        )

        def __init__(self, profile: dict, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Edit Profile")
            self.setMinimumSize(480, 480)
            self.resize(620, 580)
            self.setModal(True)
            self.setStyleSheet(self._DIALOG_SS)
            self._profile = dict(profile)

            root = QVBoxLayout(self)
            root.setSpacing(12)
            root.setContentsMargins(20, 16, 20, 16)

            # Title
            title = QLabel("Edit Your Profile")
            title.setFont(QFont("Segoe UI", 14, QFont.Bold))
            title.setStyleSheet("color:" + C["pink"] + ";")
            root.addWidget(title)

            hint = QLabel("Changes are saved immediately to your local profile file.")
            hint.setStyleSheet("color:" + C["muted"] + "; font-size:9pt;")
            root.addWidget(hint)

            # ── Section tabs ───────────────────────────────────────────
            tabs = QTabWidget()
            root.addWidget(tabs, 1)

            # Tab 1 — Basic Info
            tabs.addTab(self._build_basic_tab(profile), "Basic Info")
            # Tab 2 — Professional
            tabs.addTab(self._build_professional_tab(profile), "Professional")
            # Tab 3 — Education
            tabs.addTab(self._build_education_tab(profile), "Education")
            # Tab 4 — Preferences
            tabs.addTab(self._build_preferences_tab(profile), "Preferences")

            # Status + buttons
            self._status = QLabel("")
            self._status.setStyleSheet("color:" + C["green"] + "; font-size:9pt;")
            root.addWidget(self._status)

            btn_row = QHBoxLayout()
            save_btn = QPushButton("Save Changes")
            save_btn.setFixedHeight(38)
            save_btn.setStyleSheet(
                "QPushButton { background:" + C["pink"] + "; color:#fff; border:none;"
                "border-radius:8px; padding:0 24px; font-size:10pt; font-weight:700; }"
                "QPushButton:hover { background:#ff6ba6; }"
            )
            save_btn.clicked.connect(self._save)

            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedHeight(38)
            cancel_btn.setStyleSheet(
                "QPushButton { background:"
                + C["surface"]
                + "; color:"
                + C["text"]
                + ";"
                "border:1px solid "
                + C["border"]
                + "; border-radius:8px; padding:0 20px; }"
                "QPushButton:hover { background:" + C["surface2"] + "; }"
            )
            cancel_btn.clicked.connect(self.reject)

            btn_row.addWidget(save_btn, 1)
            btn_row.addWidget(cancel_btn)
            root.addLayout(btn_row)

        # ── Tab builders ───────────────────────────────────────────────

        def _build_basic_tab(self, p: dict) -> QWidget:
            w = QWidget()
            f = QFormLayout(w)
            f.setSpacing(10)
            f.setContentsMargins(14, 12, 14, 12)
            f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self._f_name = QLineEdit(p.get("name", ""))
            self._f_location = QLineEdit(p.get("location", ""))
            self._f_linkedin = QLineEdit(p.get("linkedin", ""))
            self._f_portfolio = QLineEdit(p.get("portfolio", ""))
            self._f_website = QLineEdit(p.get("website", ""))
            self._f_emails = self._list_edit(p.get("emails", []))
            self._f_phones = self._list_edit(p.get("phones", []))

            for label, widget in [
                ("Full Name:", self._f_name),
                ("Location:", self._f_location),
                ("LinkedIn URL:", self._f_linkedin),
                ("Portfolio URL:", self._f_portfolio),
                ("Website:", self._f_website),
                ("Emails\n(one/line):", self._f_emails),
                ("Phones\n(one/line):", self._f_phones),
            ]:
                f.addRow(self._lbl(label), widget)
            return w

        def _build_professional_tab(self, p: dict) -> QWidget:
            w = QWidget()
            f = QFormLayout(w)
            f.setSpacing(10)
            f.setContentsMargins(14, 12, 14, 12)
            f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self._f_titles = self._list_edit(p.get("job_titles", []))
            self._f_skills = self._list_edit(p.get("skills", []))
            self._f_languages = self._list_edit(p.get("languages", []))
            self._f_writing_style = QLineEdit(p.get("writing_style", "professional"))

            for label, widget in [
                ("Job Titles\n(one/line):", self._f_titles),
                ("Skills\n(one/line):", self._f_skills),
                ("Languages\n(one/line):", self._f_languages),
                ("Writing Style:", self._f_writing_style),
            ]:
                f.addRow(self._lbl(label), widget)
            return w

        def _build_education_tab(self, p: dict) -> QWidget:
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(14, 12, 14, 12)
            v.setSpacing(10)

            f = QFormLayout()
            f.setSpacing(8)
            f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

            edu = (p.get("education") or [{}])[0]
            self._f_degree = QLineEdit(edu.get("degree", ""))
            self._f_field = QLineEdit(edu.get("field", ""))
            self._f_inst = QLineEdit(edu.get("institution", ""))
            self._f_year = QLineEdit(str(edu.get("year", "")))

            for label, widget in [
                ("Degree:", self._f_degree),
                ("Field of Study:", self._f_field),
                ("Institution:", self._f_inst),
                ("Graduation Year:", self._f_year),
            ]:
                f.addRow(self._lbl(label), widget)
            v.addLayout(f)

            v.addWidget(self._lbl("Certifications (one per line):"))
            self._f_certs = self._list_edit(p.get("certifications", []))
            v.addWidget(self._f_certs)
            v.addStretch()
            return w

        def _build_preferences_tab(self, p: dict) -> QWidget:
            w = QWidget()
            f = QFormLayout(w)
            f.setSpacing(10)
            f.setContentsMargins(14, 12, 14, 12)
            f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

            prefs = p.get("preferences", {})
            self._f_job_type = self._list_edit(prefs.get("job_type", []))
            self._f_work_mode = self._list_edit(prefs.get("work_mode", []))
            self._f_industries = self._list_edit(prefs.get("industries", []))
            self._f_currency = QLineEdit(prefs.get("salary_currency", "USD"))
            self._f_notice = QSpinBox()
            self._f_notice.setRange(0, 365)
            self._f_notice.setValue(int(prefs.get("notice_period_days", 30)))
            self._f_notice.setStyleSheet(
                "background:" + C["surface"] + "; color:" + C["text"] + ";"
                "border:1px solid " + C["border"] + "; border-radius:6px; padding:4px;"
            )

            for label, widget in [
                ("Job Type\n(one/line):", self._f_job_type),
                ("Work Mode\n(one/line):", self._f_work_mode),
                ("Industries\n(one/line):", self._f_industries),
                ("Salary Currency:", self._f_currency),
                ("Notice Period (days):", self._f_notice),
            ]:
                f.addRow(self._lbl(label), widget)
            return w

        # ── Helpers ────────────────────────────────────────────────────

        def _lbl(self, text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("color:" + C["muted"] + "; font-size:9pt;")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
            return lbl

        @staticmethod
        def _list_edit(items: list) -> QTextEdit:
            te = QTextEdit("\n".join(str(v) for v in items if v))
            te.setFixedHeight(74)
            return te

        @staticmethod
        def _te_lines(te: QTextEdit) -> list:
            return [ln.strip() for ln in te.toPlainText().splitlines() if ln.strip()]

        def _save(self):
            try:
                new_profile = {
                    "name": self._f_name.text().strip(),
                    "location": self._f_location.text().strip(),
                    "emails": self._te_lines(self._f_emails),
                    "phones": self._te_lines(self._f_phones),
                    "linkedin": self._f_linkedin.text().strip(),
                    "portfolio": self._f_portfolio.text().strip(),
                    "website": self._f_website.text().strip(),
                    "resume_default": self._profile.get("resume_default", ""),
                    "job_titles": self._te_lines(self._f_titles),
                    "writing_style": self._f_writing_style.text().strip()
                    or "professional",
                    "languages": self._te_lines(self._f_languages),
                    "skills": self._te_lines(self._f_skills),
                    "education": [
                        {
                            "degree": self._f_degree.text().strip(),
                            "field": self._f_field.text().strip(),
                            "institution": self._f_inst.text().strip(),
                            "year": self._f_year.text().strip(),
                        }
                    ],
                    "certifications": self._te_lines(self._f_certs),
                    "preferences": {
                        "job_type": self._te_lines(self._f_job_type),
                        "work_mode": self._te_lines(self._f_work_mode),
                        "industries": self._te_lines(self._f_industries),
                        "salary_currency": self._f_currency.text().strip() or "USD",
                        "notice_period_days": self._f_notice.value(),
                    },
                }
                self.profile_saved.emit(new_profile)
                self._status.setText("Saved successfully!")
                self._status.setStyleSheet("color:" + C["green"] + "; font-size:9pt;")
                QTimer.singleShot(900, self.accept)
            except Exception as exc:
                self._status.setText("Error: " + str(exc))
                self._status.setStyleSheet("color:" + C["red"] + "; font-size:9pt;")


# ── Profile tab widget ─────────────────────────────────────────────────────────

if PYSIDE_AVAILABLE:

    class ProfileTabWidget(QWidget):
        """Profile tab: styled info cards + prominent Edit Profile button."""

        edit_requested = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setStyleSheet("background:" + C["surface"] + ";")

            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet(
                "QScrollArea { border:none; background:" + C["surface"] + "; }"
            )
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

            self._inner = QWidget()
            self._inner.setStyleSheet("background:" + C["surface"] + ";")
            self._cv = QVBoxLayout(self._inner)
            self._cv.setContentsMargins(14, 10, 14, 14)
            self._cv.setSpacing(10)

            # Header row
            hdr_row = QHBoxLayout()
            hdr_lbl = QLabel("My Profile")
            hdr_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
            hdr_lbl.setStyleSheet("color:" + C["pink"] + "; background:transparent;")
            hdr_row.addWidget(hdr_lbl)
            hdr_row.addStretch()

            self._edit_btn = QPushButton("Edit Profile")
            self._edit_btn.setFixedHeight(34)
            self._edit_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self._edit_btn.setStyleSheet(
                "QPushButton { background:" + C["pink"] + "; color:#fff; border:none;"
                "border-radius:8px; padding:0 16px; font-weight:700; }"
                "QPushButton:hover { background:#ff6ba6; }"
            )
            self._edit_btn.clicked.connect(self.edit_requested)
            hdr_row.addWidget(self._edit_btn)
            self._cv.addLayout(hdr_row)

            self._placeholder = QLabel(
                "Profile data loads here after runtime initialises.\n\n"
                "Click 'Edit Profile' to fill in your details."
            )
            self._placeholder.setStyleSheet("color:" + C["muted"] + "; font-size:10pt;")
            self._placeholder.setWordWrap(True)
            self._cv.addWidget(self._placeholder)

            self._tasks_lbl = QLabel()
            self._tasks_lbl.setStyleSheet("color:" + C["muted"] + "; font-size:9pt;")
            self._tasks_lbl.setWordWrap(True)
            self._tasks_lbl.setVisible(False)
            self._cv.addWidget(self._tasks_lbl)

            self._cv.addStretch()
            scroll.setWidget(self._inner)
            root.addWidget(scroll)

            self._cards: list = []

        def refresh(self, profile: dict, task_history: list):
            for card in self._cards:
                self._cv.removeWidget(card)
                card.deleteLater()
            self._cards.clear()

            if not profile:
                self._placeholder.setVisible(True)
                return
            self._placeholder.setVisible(False)

            def _val(v):
                if isinstance(v, list):
                    joined = ", ".join(str(x) for x in v if x)
                    return joined if joined else "—"
                return str(v) if v else "—"

            def _card(title: str, color: str, rows: list) -> QFrame:
                frame = QFrame()
                frame.setStyleSheet(
                    "QFrame { background:"
                    + C["bg"]
                    + "; border:1px solid "
                    + color
                    + "30;"
                    "border-left:4px solid " + color + "; border-radius:8px; }"
                )
                fv = QVBoxLayout(frame)
                fv.setContentsMargins(12, 8, 12, 10)
                fv.setSpacing(4)
                t = QLabel(title)
                t.setFont(QFont("Segoe UI", 9, QFont.Bold))
                t.setStyleSheet(
                    "color:" + color + "; border:none; background:transparent;"
                )
                fv.addWidget(t)
                for row_text in rows:
                    if row_text:
                        rl = QLabel(row_text)
                        rl.setStyleSheet(
                            "color:" + C["text"] + "; font-size:9pt;"
                            "border:none; background:transparent;"
                        )
                        rl.setWordWrap(True)
                        fv.addWidget(rl)
                return frame

            edu_list = profile.get("education") or [{}]
            edu = edu_list[0] if edu_list else {}
            prefs = profile.get("preferences") or {}

            sections = [
                (
                    "Identity",
                    C["pink"],
                    [
                        "Name: " + (profile.get("name") or "—"),
                        "Location: " + (profile.get("location") or "—"),
                        "Email: " + _val(profile.get("emails", [])),
                        "Phone: " + _val(profile.get("phones", [])),
                    ],
                ),
                (
                    "Online Presence",
                    C["blue"],
                    [
                        "LinkedIn: " + (profile.get("linkedin") or "—"),
                        "Portfolio: " + (profile.get("portfolio") or "—"),
                        "Website: " + (profile.get("website") or "—"),
                    ],
                ),
                (
                    "Professional",
                    C["neon_pink"],
                    [
                        "Titles: " + _val(profile.get("job_titles", [])),
                        "Skills: " + _val(profile.get("skills", [])),
                        "Languages: " + _val(profile.get("languages", [])),
                        "Style: " + (profile.get("writing_style") or "—"),
                    ],
                ),
                (
                    "Education",
                    C["teal"],
                    [
                        "Degree: " + (edu.get("degree") or "—"),
                        "Field: " + (edu.get("field") or "—"),
                        "Institution: " + (edu.get("institution") or "—"),
                        "Year: " + (str(edu.get("year")) if edu.get("year") else "—"),
                    ],
                ),
                (
                    "Preferences",
                    C["amber"],
                    [
                        "Job Type: " + _val(prefs.get("job_type", [])),
                        "Work Mode: " + _val(prefs.get("work_mode", [])),
                        "Currency: " + (prefs.get("salary_currency") or "USD"),
                        "Notice: " + str(prefs.get("notice_period_days", 30)) + " days",
                    ],
                ),
            ]

            # Insert cards before the stretch (last item)
            stretch_pos = self._cv.count() - 1
            for i, (title, color, rows) in enumerate(sections):
                card = _card(title, color, rows)
                self._cv.insertWidget(stretch_pos + i, card)
                self._cards.append(card)

            # Recent tasks
            if task_history:
                lines = []
                for t in reversed(task_history[-5:]):
                    icon = "✓" if t.get("success") else "✗"
                    lines.append(icon + " [" + t["ts"] + "] " + t["goal"][:70])
                self._tasks_lbl.setText("Recent Tasks:\n" + "\n".join(lines))
                self._tasks_lbl.setVisible(True)
            else:
                self._tasks_lbl.setVisible(False)


# ── Background worker ─────────────────────────────────────────────────────────


class AgentWorker(QThread if PYSIDE_AVAILABLE else object):
    finished = Signal(dict) if PYSIDE_AVAILABLE else None
    step_update = Signal(str) if PYSIDE_AVAILABLE else None

    def __init__(self, runtime: dict, goal: str):
        if PYSIDE_AVAILABLE:
            super().__init__()
        self.runtime = runtime
        self.goal = goal

    def run(self):
        try:
            self.step_update.emit("[" + _ts() + "] Starting: " + self.goal[:80])
            import asyncio
            from src.tool_system.agent_loop import AgentLoop

            def _cb(msg: str):
                self.step_update.emit("[" + _ts() + "] " + msg)

            loop = AgentLoop(self.runtime, progress_cb=_cb)
            result = asyncio.run(loop.run(self.goal))
            self.finished.emit(result)
        except Exception as exc:
            import traceback

            self.finished.emit(
                {
                    "success": False,
                    "error": str(exc),
                    "summary": "Error: " + str(exc),
                    "traceback": traceback.format_exc(),
                }
            )


class RuntimeLoader(QThread if PYSIDE_AVAILABLE else object):
    """Loads build_runtime() and AI status check in a background thread so the
    window appears instantly instead of freezing for 10-15 seconds."""

    runtime_ready = Signal(dict, dict) if PYSIDE_AVAILABLE else None
    progress = Signal(str) if PYSIDE_AVAILABLE else None
    load_error = Signal(str) if PYSIDE_AVAILABLE else None

    def __init__(self):
        if PYSIDE_AVAILABLE:
            super().__init__()

    def run(self):
        try:
            self.progress.emit("Loading agents…")
            from src.main import build_runtime
            runtime = build_runtime()
            self.progress.emit("Checking AI models…")
            from src.providers.model_router import ModelRouter
            status = ModelRouter().get_status()
            self.runtime_ready.emit(runtime, status)
        except Exception as exc:
            import traceback
            self.load_error.emit(str(exc) + "\n\n" + traceback.format_exc())


# ── Main window ───────────────────────────────────────────────────────────────


class MainWindow(QMainWindow if PYSIDE_AVAILABLE else object):
    """Main application window — colorful redesign."""

    def __init__(self):
        if not PYSIDE_AVAILABLE:
            return
        super().__init__()
        self.setWindowTitle("MegaV v2.7")
        # Allow free resizing — minimum is ~50% of default 1280×800 launch size
        self.setMinimumSize(640, 480)
        self.resize(1100, 720)

        try:
            from pathlib import Path as _P

            _assets = _P(__file__).parent.parent / "assets"
            for _ico in (_assets / "icon_256.png", _assets / "icon.ico"):
                if _ico.exists():
                    self.setWindowIcon(QIcon(str(_ico)))
                    break
        except Exception:
            pass

        app = QApplication.instance()
        if app:
            app.setStyleSheet(APP_STYLESHEET)

        self.runtime: dict = {}
        self.worker: AgentWorker | None = None
        self._active_task_item: QListWidgetItem | None = None
        self._current_goal: str = ""
        self._task_history: list = []
        self._attached_files: list = []
        self._runtime_loader: "RuntimeLoader | None" = None

        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._start_runtime_loader()

    # ── Runtime ────────────────────────────────────────────────────────

    def _start_runtime_loader(self):
        """Show the window immediately, then load all agents in a background thread."""
        self.status_bar.showMessage("Loading AI agents…")
        self._ai_dot.setStyleSheet("font-size:12pt; color:" + C["amber"] + "; padding:0 2px;")
        self._ai_dot_label.setText("AI: Loading…")
        self._ai_dot_label.setStyleSheet("color:" + C["amber"] + "; font-size:9pt; padding:0 6px 0 0;")
        self._runtime_loader = RuntimeLoader()
        self._runtime_loader.progress.connect(self._on_runtime_progress)
        self._runtime_loader.runtime_ready.connect(self._on_runtime_ready)
        self._runtime_loader.load_error.connect(self._on_runtime_error)
        self._runtime_loader.start()

    def _on_runtime_progress(self, msg: str):
        self.status_bar.showMessage(msg)

    def _on_runtime_ready(self, runtime: dict, status: dict):
        self.runtime = runtime
        self._log_sys("MegaV started successfully.")
        self._log_sys("Type a goal in natural English and press Send.")

        if status["active_provider"]:
            model_info = status.get("active_model", "")
            provider = status["active_provider"]
            color = C["green"]
            ai_msg = f"AI: {provider.title()} connected | Model: {model_info}"
            self._log_sys(ai_msg)
            self.chat_history.append(
                "<div style='margin:6px 0; padding:6px 10px; background:"
                + C["surface2"] + "; border-left:4px solid " + color
                + "; border-radius:6px;'>"
                "<b style='color:" + color + ";'>AI Status</b> "
                "<span style='color:" + C["text"] + ";'>" + ai_msg + "</span></div>"
            )
        else:
            color = C["red"]
            from src.providers.model_router import ModelRouter
            fix = ModelRouter()._build_fix_hint(status.get("ollama", {}))
            ai_msg = "AI: No model available"
            self._log_sys(ai_msg)
            self._log_sys(fix)
            fix_html = fix.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            self.chat_history.append(
                "<div style='margin:6px 0; padding:6px 10px; background:"
                + C["surface2"] + "; border-left:4px solid " + color
                + "; border-radius:6px;'>"
                "<b style='color:" + color + ";'>AI Status</b> "
                "<span style='color:" + C["text"] + ";'>" + ai_msg + "</span><br>"
                "<span style='color:" + C["muted"] + "; font-size:9pt;'>" + fix_html + "</span></div>"
            )

        self._populate_skills_tab()
        self._populate_workflows_tab()
        self._populate_profile_tab()
        self._build_email_tab()
        self._build_social_tab()
        self._build_approvals_tab()
        self._build_dashboard_tab()
        self._build_discovery_tab()
        self.status_bar.showMessage("Ready — type a goal and press Send.")
        self._ai_dot.setStyleSheet("font-size:12pt; color:" + C["green"] + "; padding:0 2px;")
        self._ai_dot_label.setText("AI: Ready")
        self._ai_dot_label.setStyleSheet("color:" + C["green"] + "; font-size:9pt; padding:0 6px 0 0;")

    def _on_runtime_error(self, error: str):
        self._log_sys("[WARNING] Runtime init: " + error.split("\n")[0])
        self.status_bar.showMessage("AI: Offline — No LLM connected")
        self._ai_dot.setStyleSheet("font-size:12pt; color:" + C["red"] + "; padding:0 2px;")
        self._ai_dot_label.setText("AI: Offline")
        self._ai_dot_label.setStyleSheet("color:" + C["red"] + "; font-size:9pt; padding:0 6px 0 0;")

    # ── UI Layout ──────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 4)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        root.addWidget(splitter, 1)

        # ── LEFT: Chat panel ───────────────────────────────────────────
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 6, 0)
        lv.setSpacing(6)

        lv.addWidget(self._section_header("CHAT", C["claude_orange"], ""))

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setFont(QFont("Segoe UI", 10))
        self.chat_history.setStyleSheet(
            "QTextEdit { background:"
            + C["surface"]
            + "; border:1px solid "
            + C["border"]
            + ";"
            "border-radius:10px; padding:10px; }"
        )
        lv.addWidget(self.chat_history, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setVisible(False)
        lv.addWidget(self.progress_bar)

        # Attach bar
        self._attach_bar = QWidget()
        self._attach_bar.setVisible(False)
        self._attach_bar.setStyleSheet(
            "background:" + C["surface2"] + "; border:1px solid " + C["blue"] + "50;"
            "border-radius:8px;"
        )
        ab = QHBoxLayout(self._attach_bar)
        ab.setContentsMargins(10, 4, 10, 4)
        self._attach_label = QLabel()
        self._attach_label.setStyleSheet(
            "color:" + C["blue"] + "; font-size:9pt; background:transparent;"
        )
        self._attach_label.setWordWrap(True)
        ab.addWidget(self._attach_label, 1)
        clr_btn = QPushButton("✕ Clear")
        clr_btn.setMinimumSize(64, 22)
        clr_btn.setMaximumSize(80, 28)
        clr_btn.setObjectName("danger_btn")
        clr_btn.clicked.connect(self._clear_attachments)
        ab.addWidget(clr_btn)
        lv.addWidget(self._attach_bar)

        # Input row
        inp = QHBoxLayout()
        inp.setSpacing(6)

        self.attach_button = QToolButton()
        self.attach_button.setText("📎")
        self.attach_button.setMinimumSize(38, 38)
        self.attach_button.setMaximumSize(46, 46)
        self.attach_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.attach_button.setToolTip("Attach a file (PDF, Word, Excel, image, code…)")
        self.attach_button.clicked.connect(self._attach_file)
        inp.addWidget(self.attach_button)

        self.message_input = QLineEdit()
        self.message_input.setFont(QFont("Segoe UI", 10))
        self.message_input.setMinimumHeight(38)
        self.message_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.message_input.setPlaceholderText(
            "Type a goal in plain English, e.g. 'Find Python developer jobs on LinkedIn'"
        )
        self.message_input.returnPressed.connect(self.send_message)
        inp.addWidget(self.message_input, 1)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("send_btn")
        self.send_button.setMinimumSize(80, 38)
        self.send_button.setMaximumWidth(110)
        self.send_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.send_button.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.send_button.clicked.connect(self.send_message)
        inp.addWidget(self.send_button)
        lv.addLayout(inp)

        splitter.addWidget(left)

        # ── RIGHT: Tab panel ───────────────────────────────────────────
        right_tabs = _ColoredTabBar()
        right_tabs.setDocumentMode(True)

        # AI Status tab (first tab)
        ai_w = QWidget()
        ai_v = QVBoxLayout(ai_w)
        ai_v.setContentsMargins(6, 6, 6, 6)
        ai_v.setSpacing(8)
        ai_v.addWidget(self._section_header("AI STATUS", C["claude_orange"], ""))
        self._ai_status_label = QLabel("Checking AI providers...")
        self._ai_status_label.setWordWrap(True)
        self._ai_status_label.setStyleSheet(
            "color:" + C["text_dim"] + "; font-size:10pt; padding:8px;"
            "background:" + C["surface2"] + "; border-radius:8px;"
            "border:1px solid " + C["border"] + ";"
        )
        ai_v.addWidget(self._ai_status_label)
        self._ai_guide_label = QLabel(
            "To connect an AI provider:\n"
            "1. Start Ollama locally: ollama serve\n"
            "2. Or add an API key in Settings\n"
            "3. Supported: Ollama, DeepSeek, Claude"
        )
        self._ai_guide_label.setWordWrap(True)
        self._ai_guide_label.setStyleSheet(
            "color:" + C["muted"] + "; font-size:9pt; padding:8px;"
            "background:" + C["surface"] + "; border-radius:8px;"
            "border:1px solid " + C["border_warm"] + ";"
        )
        ai_v.addWidget(self._ai_guide_label)
        ai_v.addStretch()
        right_tabs.addTab(ai_w, "AI Status")

        # Tasks tab
        t_w = QWidget()
        tv = QVBoxLayout(t_w)
        tv.setContentsMargins(6, 6, 6, 6)
        tv.addWidget(self._section_header("ACTIVE TASKS", C["electric_yellow"], ""))
        self.tasks_list = QListWidget()
        self.tasks_list.setFont(QFont("Consolas", 9))
        tv.addWidget(self.tasks_list)
        right_tabs.addTab(t_w, "Tasks")

        # Skills tab — full 31-skill registry panel
        sk_w = QWidget()
        skv = QVBoxLayout(sk_w)
        skv.setContentsMargins(6, 6, 6, 6)
        skv.setSpacing(6)

        # Header
        skv.addWidget(self._section_header("SKILLS ENGINE", C["cyan"], ""))

        # Stats bar
        self._skills_stats_label = QLabel("Loading skills…")
        self._skills_stats_label.setStyleSheet(
            "color:" + C["muted"] + "; font-size:8pt; padding:0 4px;"
        )
        skv.addWidget(self._skills_stats_label)

        # Search bar
        self._skills_search = QLineEdit()
        self._skills_search.setPlaceholderText(
            "🔍  Search skills by name, category, or keyword…"
        )
        self._skills_search.setStyleSheet(
            "QLineEdit { background:"
            + C["surface2"]
            + "; border:1px solid "
            + C["border"]
            + ";"
            "border-radius:6px; padding:5px 10px; color:"
            + C["text"]
            + "; font-size:9pt; }"
            "QLineEdit:focus { border-color:" + C["cyan"] + "; }"
        )
        self._skills_search.textChanged.connect(self._filter_skills_list)
        skv.addWidget(self._skills_search)

        # Skills list
        self.skills_list = QListWidget()
        self.skills_list.setStyleSheet(
            "QListWidget { background:"
            + C["surface"]
            + "; border:1px solid "
            + C["border"]
            + ";"
            "border-radius:8px; padding:4px; }"
            "QListWidget::item { padding:6px 8px; border-radius:6px; }"
            "QListWidget::item:hover { background:" + C["surface2"] + "; }"
            "QListWidget::item:selected { background:" + C["cyan"] + "33; "
            "border-left:3px solid " + C["cyan"] + "; }"
        )
        self.skills_list.setSpacing(1)
        skv.addWidget(self.skills_list, stretch=1)

        # Detail label at bottom
        self._skill_detail = QLabel("Click a skill to see details.")
        self._skill_detail.setWordWrap(True)
        self._skill_detail.setStyleSheet(
            "background:" + C["surface2"] + "; border:1px solid " + C["border"] + ";"
            "border-radius:6px; padding:8px; color:"
            + C["text_dim"]
            + "; font-size:8pt;"
        )
        self._skill_detail.setMaximumHeight(72)
        skv.addWidget(self._skill_detail)
        self.skills_list.currentItemChanged.connect(self._on_skill_selected)

        right_tabs.addTab(sk_w, "Skills")

        # Profile tab — card-based widget with Edit button
        self._profile_widget = ProfileTabWidget()
        self._profile_widget.edit_requested.connect(self._open_profile_editor)
        right_tabs.addTab(self._profile_widget, "Profile")

        # Email tab — placeholder until runtime builds it
        self._email_tab_widget = None
        self._email_placeholder = QLabel(
            "Email Automation\n\nConnect Gmail, Outlook, or custom accounts here."
        )
        self._email_placeholder.setAlignment(Qt.AlignCenter)
        self._email_placeholder.setStyleSheet(
            "color:" + C["muted"] + "; font-size:12pt; background:" + C["surface"] + ";"
        )
        right_tabs.addTab(self._email_placeholder, "Email")

        # Social tab — placeholder until runtime builds it
        self._social_tab_widget = None
        self._social_placeholder = QLabel(
            "Social Accounts\n\nConnect Facebook, LinkedIn, Instagram,\n"
            "Google Business, and TikTok here."
        )
        self._social_placeholder.setAlignment(Qt.AlignCenter)
        self._social_placeholder.setStyleSheet(
            "color:" + C["muted"] + "; font-size:12pt; background:" + C["surface"] + ";"
        )
        right_tabs.addTab(self._social_placeholder, "Social")

        # Logs tab
        log_w = QWidget()
        logv = QVBoxLayout(log_w)
        logv.setContentsMargins(6, 6, 6, 6)
        logv.addWidget(self._section_header("SYSTEM LOGS", C["sky_blue"], ""))
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Consolas", 9))
        self.logs_text.setStyleSheet(
            "QTextEdit { background:"
            + C["bg"]
            + "; border:1px solid "
            + C["border"]
            + ";"
            "border-radius:8px; color:" + C["muted"] + "; padding:6px; }"
        )
        logv.addWidget(self.logs_text)
        right_tabs.addTab(log_w, "Logs")

        # Approvals tab placeholder
        self._approvals_tab_widget = None
        self._approvals_placeholder = QLabel(
            "Approval Center\n\nView and manage all financial action approvals here."
        )
        self._approvals_placeholder.setAlignment(Qt.AlignCenter)
        self._approvals_placeholder.setStyleSheet(
            "color:" + C["muted"] + "; font-size:12pt; background:" + C["surface"] + ";"
        )
        right_tabs.addTab(self._approvals_placeholder, "Approvals")

        # Dashboard tab placeholder
        self._dashboard_tab_widget = None
        self._dashboard_placeholder = QLabel(
            "Business Dashboard\n\nRevenue summary, pipeline, and recent activity."
        )
        self._dashboard_placeholder.setAlignment(Qt.AlignCenter)
        self._dashboard_placeholder.setStyleSheet(
            "color:" + C["muted"] + "; font-size:12pt; background:" + C["surface"] + ";"
        )
        right_tabs.addTab(self._dashboard_placeholder, "Dashboard")

        # Discovery tab placeholder
        self._discovery_tab_widget = None
        self._discovery_placeholder = QLabel(
            "Discovery\n\nScan for installed CLIs, skills, and capability gaps."
        )
        self._discovery_placeholder.setAlignment(Qt.AlignCenter)
        self._discovery_placeholder.setStyleSheet(
            "color:" + C["muted"] + "; font-size:12pt; background:" + C["surface"] + ";"
        )
        right_tabs.addTab(self._discovery_placeholder, "Discovery")

        splitter.addWidget(right_tabs)
        # Proportional split: 60% chat, 40% right panel
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([660, 440])

        self._right_tabs = right_tabs
        self._email_tab_idx = 4      # Email is index 4
        self._social_tab_idx = 5     # Social is index 5
        self._approvals_tab_idx = 7  # Approvals is index 7
        self._dashboard_tab_idx = 8  # Dashboard is index 8
        self._discovery_tab_idx = 9  # Discovery is index 9

    def _section_header(self, title: str, color: str, icon: str = "") -> QWidget:
        w = QWidget()
        w.setFixedHeight(34)
        w.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 " + color + "28, stop:1 transparent);"
            "border-left:4px solid " + color + "; border-radius:4px;"
        )
        row = QHBoxLayout(w)
        row.setContentsMargins(10, 0, 10, 0)
        lbl = QLabel((icon + "  " + title) if icon else title)
        lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lbl.setStyleSheet("color:" + color + "; background:transparent; border:none;")
        row.addWidget(lbl)
        row.addStretch()
        return w

    def _setup_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("File")
        a = QAction("New Session", self)
        a.setShortcut("Ctrl+N")
        a.triggered.connect(self.new_session)
        fm.addAction(a)
        fm.addSeparator()
        a = QAction("Exit", self)
        a.setShortcut("Ctrl+Q")
        a.triggered.connect(self.close)
        fm.addAction(a)

        tm = mb.addMenu("Tools")
        a = QAction("Check AI Status", self)
        a.triggered.connect(self._check_ai_status)
        tm.addAction(a)
        a = QAction("Settings…", self)
        a.triggered.connect(self._open_settings)
        tm.addAction(a)
        a = QAction("Reload Agents", self)
        a.triggered.connect(self._start_runtime_loader)
        tm.addAction(a)
        a = QAction("Edit Profile…", self)
        a.triggered.connect(self._open_profile_editor)
        tm.addAction(a)

        hm = mb.addMenu("Help")
        a = QAction("About", self)
        a.triggered.connect(self.show_about)
        hm.addAction(a)

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Starting…")
        # AI status indicator dot + label
        self._ai_dot = QLabel("●")
        self._ai_dot.setStyleSheet("font-size:12pt; padding:0 2px;")
        self._ai_dot_label = QLabel("AI: Checking…")
        self._ai_dot_label.setStyleSheet(
            "color:" + C["muted"] + "; font-size:9pt; padding:0 6px 0 0;"
        )
        self.status_bar.addWidget(self._ai_dot)
        self.status_bar.addWidget(self._ai_dot_label)

        # Quick model picker — cloud + installed local models
        self._model_picker = QComboBox()
        self._model_picker.setStyleSheet(
            "QComboBox { font-size:9pt; padding:1px 6px; min-width:200px; }"
        )
        self._model_picker.setToolTip("Active model — applies to every task")
        self._populate_model_picker()
        self._model_picker.currentIndexChanged.connect(self._on_model_picker_changed)
        self.status_bar.addPermanentWidget(self._model_picker)

    _CLOUD_MODELS = (
        "kimi-k2.6:cloud",
        "qwen3.5:cloud",
        "minimax-m2.7:cloud",
        "glm-5.1:cloud",
    )

    def _populate_model_picker(self):
        """Fill the status-bar model dropdown with cloud + installed models."""
        try:
            from src.providers.model_router import ModelRouter, get_model_router
        except Exception:
            from providers.model_router import ModelRouter, get_model_router  # type: ignore
        combo = self._model_picker
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Auto (best available)", "")
        for cm in self._CLOUD_MODELS:
            combo.addItem(f"☁ {cm}", cm)
        try:
            installed = get_model_router().get_status().get("ollama", {}).get("models", [])
        except Exception:
            installed = []
        for m in installed:
            combo.addItem(m, m)
        # Restore current preference
        preferred = ModelRouter.get_preferred_local_model()
        if preferred:
            idx = combo.findData(preferred)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _on_model_picker_changed(self, _idx: int):
        try:
            from src.providers.model_router import ModelRouter, get_model_router
        except Exception:
            from providers.model_router import ModelRouter, get_model_router  # type: ignore
        data = self._model_picker.currentData()
        ModelRouter.set_preferred_local_model(data or "")
        # Force router to re-read installed models on next request
        try:
            get_model_router().invalidate_model_cache()
        except Exception:
            pass
        # Refresh AI status label
        try:
            self._check_ai_status()
        except Exception:
            pass

    # ── Messaging ──────────────────────────────────────────────────────

    def _check_ai_status(self):
        """Show current AI model status in the chat panel, status bar, and AI Status tab."""
        try:
            from src.providers.model_router import get_model_router
            from src.providers.uncensored_catalog import UncensoredModelCatalog
            router = get_model_router()
            catalog = UncensoredModelCatalog()
            status = router.get_status()

            # Build provider card list for AI Status tab
            provider_cards = []
            _co = C["claude_orange"]
            _cg = C["green"]
            _cr = C["red"]
            _cm = C["muted"]
            provider_cards.append("<b style='color:" + _co + "'>Connected Providers</b><br>")

            if status["active_provider"]:
                color = _cg
                provider = status["active_provider"].title()
                model = status.get("active_model", "unknown")
                msg = f"AI: {provider} ({model})"
                # Update status bar indicator
                self._ai_dot.setStyleSheet("font-size:12pt; color:" + _cg + "; padding:0 2px;")
                self._ai_dot_label.setText(msg[:40])
                self._ai_dot_label.setStyleSheet("color:" + _cg + "; font-size:9pt; padding:0 6px 0 0;")
                # Show provider details
                details = []
                if status.get("deepseek"):
                    details.append("DeepSeek: connected")
                    provider_cards.append("<span style='color:" + _cg + "'>● DeepSeek</span> — connected<br>")
                if status.get("claude"):
                    details.append("Claude: connected")
                    provider_cards.append("<span style='color:" + _cg + "'>● Claude</span> — connected<br>")
                if status.get("openrouter"):
                    details.append("OpenRouter: connected")
                    provider_cards.append("<span style='color:" + _cg + "'>● OpenRouter</span> — connected<br>")
                if status["active_provider"] == "ollama":
                    models = status.get("ollama", {}).get("models", [])
                    uncensored = status.get("ollama", {}).get("uncensored_count", 0)
                    provider_cards.append("<span style='color:" + _cg + "'>● Ollama</span> — " + str(len(models)) + " model(s)<br>")
                    if models:
                        msg += f" | {', '.join(models[:4])}"
                    if uncensored:
                        details.append(f"{uncensored} uncensored model(s)")
                if details:
                    msg += " | " + " | ".join(details)
                chat_msg = msg
            else:
                color = _cr
                chat_msg = "AI: Offline — No LLM connected"
                # Update status bar indicator
                self._ai_dot.setStyleSheet("font-size:12pt; color:" + _cr + "; padding:0 2px;")
                self._ai_dot_label.setText("AI: Offline")
                self._ai_dot_label.setStyleSheet("color:" + _cr + "; font-size:9pt; padding:0 6px 0 0;")
                provider_cards.append("<span style='color:" + _cr + "'>● No providers connected</span><br>")
                fix = router._build_fix_hint(status.get("ollama", {}))
                fix_html = fix.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                provider_cards.append("<br><span style='color:" + _cm + "; font-size:9pt;'>" + fix_html + "</span>")
                # Chat message with fix hint
                self.chat_history.append(
                    "<div style='margin:6px 0; padding:6px 10px; background:"
                    + C["surface2"] + "; border-left:4px solid " + color
                    + "; border-radius:6px;'>"
                    "<b style='color:" + color + ";'>" + chat_msg + "</b><br>"
                    "<span style='color:" + C["muted"] + "; font-size:9pt;'>" + fix_html + "</span></div>"
                )
                self.chat_history.ensureCursorVisible()
                # Update AI Status tab
                self._ai_status_label.setText("".join(provider_cards))
                return

            # Success message in chat
            self.chat_history.append(
                "<div style='margin:6px 0; padding:6px 10px; background:"
                + C["surface2"] + "; border-left:4px solid " + color
                + "; border-radius:6px;'>"
                "<b style='color:" + color + ";'>" + chat_msg + "</b></div>"
            )
            self.chat_history.ensureCursorVisible()
            # Update AI Status tab
            self._ai_status_label.setText("".join(provider_cards))
        except Exception as e:
            self.chat_history.append(
                "<div style='margin:6px 0; padding:6px 10px; background:"
                + C["surface2"] + "; border-left:4px solid " + C["red"]
                + "; border-radius:6px;'>"
                "<b style='color:" + C["red"] + ";'>AI Status: Error checking status</b><br>"
                "<span style='color:" + C["muted"] + ";'>" + str(e)[:200] + "</span></div>"
            )

    def _open_settings(self):
        """Open Settings dialog for API keys and model configuration."""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
            QLabel, QLineEdit, QPushButton, QGroupBox, QCheckBox,
            QComboBox,
        )
        from src.providers.model_router import ModelRouter, get_model_router
        from src.providers.uncensored_catalog import UncensoredModelCatalog

        router = get_model_router()
        catalog = UncensoredModelCatalog()

        dlg = QDialog(self)
        dlg.setWindowTitle("MegaV Settings — Uncensored-First AI")
        dlg.setMinimumWidth(580)
        dlg.setStyleSheet(f"""
            QDialog {{ background: {C['bg']}; color: {C['text']}; }}
            QLabel {{ color: {C['text']}; font-size: 11pt; }}
            QLineEdit {{ background: {C['surface2']}; color: {C['text']};
                         border: 1px solid {C['border']}; border-radius: 4px;
                         padding: 8px; font-size: 11pt; }}
            QLineEdit:focus {{ border: 1px solid {C['claude_orange']}; }}
            QPushButton {{ background: {C['claude_orange']}; color: white;
                          border: none; border-radius: 4px; padding: 8px 20px;
                          font-size: 11pt; font-weight: bold; }}
            QPushButton:hover {{ background: #d4714a; }}
            QPushButton:pressed {{ background: #c0603a; }}
            QPushButton#cancelBtn {{ background: {C['surface3']}; color: {C['text_dim']}; }}
            QPushButton#cancelBtn:hover {{ background: {C['border']}; }}
            QPushButton#testBtn {{ background: {C['surface3']}; color: {C['text']};
                          border: 1px solid {C['border']}; border-radius: 4px;
                          padding: 6px 16px; font-size: 10pt; font-weight: normal; }}
            QPushButton#testBtn:hover {{ background: {C['border']}; }}
            QGroupBox {{ color: {C['text']}; border: 1px solid {C['border']};
                        border-radius: 6px; margin-top: 12px; padding-top: 20px;
                        font-size: 11pt; font-weight: bold; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
            QCheckBox {{ color: {C['text']}; font-size: 10pt; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; }}
            QComboBox {{ background: {C['surface2']}; color: {C['text']};
                         border: 1px solid {C['border']}; border-radius: 4px;
                         padding: 6px; font-size: 10pt; }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        # ── DeepSeek API Key ──────────────────────────────────
        group_ds = QGroupBox("AI Provider — DeepSeek (Uncensored Cloud)")
        ds_layout = QVBoxLayout(group_ds)

        ds_info = QLabel(
            "DeepSeek is a cheap, capable, uncensored cloud AI.\n"
            "Pricing: $0.27/1M input tokens — get a key at: https://platform.deepseek.com/"
        )
        ds_info.setWordWrap(True)
        ds_info.setStyleSheet(f"color: {C['muted']}; font-size: 9pt;")
        ds_layout.addWidget(ds_info)

        ds_key_layout = QHBoxLayout()
        ds_key_label = QLabel("API Key:")
        ds_key_label.setMinimumWidth(80)
        ds_key_input = QLineEdit()
        ds_key_input.setPlaceholderText("sk-...")
        ds_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        existing_ds_key = ModelRouter.get_deepseek_api_key()
        if existing_ds_key:
            ds_key_input.setText(existing_ds_key)

        ds_key_layout.addWidget(ds_key_label)
        ds_key_layout.addWidget(ds_key_input)

        show_ds_key = QCheckBox("Show key")
        show_ds_key.setStyleSheet(f"color: {C['muted']}; font-size: 9pt;")
        show_ds_key.toggled.connect(lambda checked: ds_key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        ))
        ds_key_layout.addWidget(show_ds_key)
        ds_layout.addLayout(ds_key_layout)

        ds_status_label = QLabel()
        ds_status_label.setWordWrap(True)
        ds_status_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt; padding: 4px;")
        ds_layout.addWidget(ds_status_label)

        # ── Shared signal-safe result poster ──────────────────────────
        from PySide6.QtCore import QObject, Signal as _Signal

        class _Tester(QObject):
            done = _Signal(str, bool, str)   # label_id, ok, message

        _tester = _Tester()

        def _post_result(label_id: str, ok: bool, msg: str):
            _tester.done.emit(label_id, ok, msg)

        def _apply_result(label_id, ok, msg):
            mapping = {
                "ds":     (ds_status_label, ds_test_btn),
                "or":     (or_status_label, or_test_btn),
                "claude": (status_label,    test_btn),
            }
            lbl, btn = mapping.get(label_id, (None, None))
            if lbl is None:
                return
            btn.setEnabled(True)
            if ok:
                lbl.setText(f"✅ {msg}")
                lbl.setStyleSheet(f"color: {C['green']}; font-size: 9pt; padding: 4px;")
            else:
                lbl.setText(f"❌ {msg}")
                lbl.setStyleSheet(f"color: {C['red']}; font-size: 9pt; padding: 4px;")

        _tester.done.connect(_apply_result)

        def _test_ds():
            import threading, requests as _req
            key = ds_key_input.text().strip()
            if not key:
                ds_status_label.setText("❌ Enter your DeepSeek API key above")
                ds_status_label.setStyleSheet(f"color: {C['red']}; font-size: 9pt; padding: 4px;")
                return
            ModelRouter.set_deepseek_api_key(key)
            router._deepseek = None
            ds_test_btn.setEnabled(False)
            ds_status_label.setText("⏳ Testing...")
            ds_status_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt; padding: 4px;")
            def _run():
                try:
                    r = _req.get("https://api.deepseek.com/v1/models",
                                 headers={"Authorization": f"Bearer {key}"}, timeout=10)
                    if r.status_code == 200:
                        _post_result("ds", True, "DeepSeek connected — deepseek-chat ready")
                    else:
                        _post_result("ds", False, f"DeepSeek: HTTP {r.status_code} — check your key")
                except Exception as e:
                    _post_result("ds", False, f"DeepSeek: {str(e)[:60]}")
            threading.Thread(target=_run, daemon=True).start()

        ds_test_btn = QPushButton("Test Connection")
        ds_test_btn.setObjectName("testBtn")
        ds_test_btn.clicked.connect(_test_ds)
        ds_layout.addWidget(ds_test_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(group_ds)

        # Initial status — no network call, just check if key is saved
        if ModelRouter.get_deepseek_api_key():
            ds_status_label.setText("🔑 Key saved — click Test to verify connection")
            ds_status_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt; padding: 4px;")
        else:
            ds_status_label.setText("❌ No DeepSeek connection — enter a valid API key above")
            ds_status_label.setStyleSheet(f"color: {C['red']}; font-size: 9pt; padding: 4px;")

        # ── OpenRouter API Key ──────────────────────────────────
        group_or = QGroupBox("AI Provider — OpenRouter (100+ Cloud Models)")
        or_layout = QVBoxLayout(group_or)

        or_info = QLabel(
            "OpenRouter gives access to 100+ models through a single API key.\n"
            "Free models available (DeepSeek, Gemma, Llama, Qwen). Get a key at: https://openrouter.ai/keys"
        )
        or_info.setWordWrap(True)
        or_info.setStyleSheet(f"color: {C['muted']}; font-size: 9pt;")
        or_layout.addWidget(or_info)

        or_key_layout = QHBoxLayout()
        or_key_label = QLabel("API Key:")
        or_key_label.setMinimumWidth(80)
        or_key_input = QLineEdit()
        or_key_input.setPlaceholderText("sk-or-...")
        or_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        existing_or_key = ModelRouter.get_openrouter_api_key()
        if existing_or_key:
            or_key_input.setText(existing_or_key)

        or_key_layout.addWidget(or_key_label)
        or_key_layout.addWidget(or_key_input)

        show_or_key = QCheckBox("Show key")
        show_or_key.setStyleSheet(f"color: {C['muted']}; font-size: 9pt;")
        show_or_key.toggled.connect(lambda checked: or_key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        ))
        or_key_layout.addWidget(show_or_key)
        or_layout.addLayout(or_key_layout)

        or_status_label = QLabel()
        or_status_label.setWordWrap(True)
        or_status_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt; padding: 4px;")
        or_layout.addWidget(or_status_label)

        def _test_or():
            import threading, requests as _req
            key = or_key_input.text().strip()
            if not key:
                or_status_label.setText("❌ Enter your OpenRouter API key above")
                or_status_label.setStyleSheet(f"color: {C['red']}; font-size: 9pt; padding: 4px;")
                return
            ModelRouter.set_openrouter_api_key(key)
            router._openrouter = None
            or_test_btn.setEnabled(False)
            or_status_label.setText("⏳ Testing...")
            or_status_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt; padding: 4px;")
            def _run():
                try:
                    r = _req.get("https://openrouter.ai/api/v1/auth/key",
                                 headers={"Authorization": f"Bearer {key}"}, timeout=10)
                    if r.status_code == 200:
                        data = r.json().get("data", {})
                        label = data.get("label", "key valid")
                        _post_result("or", True, f"OpenRouter connected — {label}")
                    else:
                        _post_result("or", False, f"OpenRouter: HTTP {r.status_code} — check your key")
                except Exception as e:
                    _post_result("or", False, f"OpenRouter: {str(e)[:60]}")
            threading.Thread(target=_run, daemon=True).start()

        or_test_btn = QPushButton("Test Connection")
        or_test_btn.setObjectName("testBtn")
        or_test_btn.clicked.connect(_test_or)
        or_layout.addWidget(or_test_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(group_or)

        # Initial status — no network call
        if ModelRouter.get_openrouter_api_key():
            or_status_label.setText("🔑 Key saved — click Test to verify connection")
            or_status_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt; padding: 4px;")
        else:
            or_status_label.setText("❌ No OpenRouter connection — enter a valid API key above")
            or_status_label.setStyleSheet(f"color: {C['red']}; font-size: 9pt; padding: 4px;")

        # ── Ollama Cloud API Key ───────────────────────────────
        group_oc = QGroupBox("AI Provider — Ollama Cloud (kimi/qwen/minimax/glm)")
        oc_layout = QVBoxLayout(group_oc)
        oc_info = QLabel(
            "Cloud models (kimi-k2.6:cloud, qwen3.5:cloud, minimax-m2.7:cloud, glm-5.1:cloud)\n"
            "work via the local Ollama daemon after you run `ollama signin`. As a fallback,\n"
            "paste an OLLAMA_API_KEY here (https://ollama.com/settings/keys) for direct cloud access."
        )
        oc_info.setWordWrap(True)
        oc_info.setStyleSheet(f"color: {C['muted']}; font-size: 9pt;")
        oc_layout.addWidget(oc_info)

        oc_key_layout = QHBoxLayout()
        oc_key_label = QLabel("API Key:")
        oc_key_label.setMinimumWidth(80)
        oc_key_input = QLineEdit()
        oc_key_input.setPlaceholderText("ollama key (optional if signed-in)")
        oc_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        existing_oc_key = ModelRouter.get_ollama_api_key()
        if existing_oc_key:
            oc_key_input.setText(existing_oc_key)
        oc_key_layout.addWidget(oc_key_label)
        oc_key_layout.addWidget(oc_key_input)
        show_oc_key = QCheckBox("Show key")
        show_oc_key.setStyleSheet(f"color: {C['muted']}; font-size: 9pt;")
        show_oc_key.toggled.connect(lambda checked: oc_key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        ))
        oc_key_layout.addWidget(show_oc_key)
        oc_layout.addLayout(oc_key_layout)
        layout.addWidget(group_oc)

        # ── Anthropic API Key ──────────────────────────────────
        group_ai = QGroupBox("AI Provider — Anthropic Claude")
        ai_layout = QVBoxLayout(group_ai)

        info_label = QLabel(
            "Enter your Anthropic API key to use Claude (premium quality for complex tasks).\n"
            "Get a key at: https://console.anthropic.com/"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt;")
        ai_layout.addWidget(info_label)

        key_layout = QHBoxLayout()
        key_label = QLabel("API Key:")
        key_label.setMinimumWidth(80)
        key_input = QLineEdit()
        key_input.setPlaceholderText("sk-ant-...")
        key_input.setEchoMode(QLineEdit.EchoMode.Password)

        existing_key = ModelRouter.get_api_key()
        if existing_key:
            key_input.setText(existing_key)

        key_layout.addWidget(key_label)
        key_layout.addWidget(key_input)

        show_key = QCheckBox("Show key")
        show_key.setStyleSheet(f"color: {C['muted']}; font-size: 9pt;")
        show_key.toggled.connect(lambda checked: key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        ))
        key_layout.addWidget(show_key)
        ai_layout.addLayout(key_layout)

        status_label = QLabel()
        status_label.setWordWrap(True)
        status_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt; padding: 4px;")
        ai_layout.addWidget(status_label)

        def _test_claude():
            import threading, requests as _req
            key = key_input.text().strip()
            if not key:
                status_label.setText("❌ Enter your Anthropic API key above")
                status_label.setStyleSheet(f"color: {C['red']}; font-size: 9pt; padding: 4px;")
                return
            ModelRouter.set_api_key(key)
            router._claude = None
            test_btn.setEnabled(False)
            status_label.setText("⏳ Testing...")
            status_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt; padding: 4px;")
            def _run():
                try:
                    r = _req.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                 "content-type": "application/json"},
                        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1,
                              "messages": [{"role": "user", "content": "hi"}]},
                        timeout=15,
                    )
                    if r.status_code == 200:
                        _post_result("claude", True, "Claude connected — claude-sonnet-4-6 ready")
                    else:
                        body = r.json().get("error", {}).get("message", r.text)[:80]
                        _post_result("claude", False, f"Claude: {body}")
                except Exception as e:
                    _post_result("claude", False, f"Claude: {str(e)[:60]}")
            threading.Thread(target=_run, daemon=True).start()

        test_btn = QPushButton("Test Connection")
        test_btn.setObjectName("testBtn")
        test_btn.clicked.connect(_test_claude)
        ai_layout.addWidget(test_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(group_ai)

        # Initial status — no network call
        if ModelRouter.get_api_key():
            status_label.setText("🔑 Key saved — click Test to verify connection")
            status_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt; padding: 4px;")
        else:
            status_label.setText("❌ No Claude connection — enter a valid API key above")
            status_label.setStyleSheet(f"color: {C['red']}; font-size: 9pt; padding: 4px;")

        # ── Ollama Settings ────────────────────────────────────
        group_ollama = QGroupBox("Local AI — Ollama (Uncensored Models)")
        ollama_layout = QVBoxLayout(group_ollama)

        ollama_status = router.ollama_status()
        if ollama_status.get("running"):
            models = ollama_status.get("models", [])
            # Show which models are uncensored
            model_lines = []
            for m in models[:8]:
                is_uncensored = catalog.is_uncensored(m)
                badge = "🔓" if is_uncensored else "🔒"
                model_lines.append(f"  {badge} {m}")
            model_text = "\n".join(model_lines) if model_lines else "No models installed"
            uncensored_count = ollama_status.get("uncensored_count", sum(1 for m in models if catalog.is_uncensored(m)))
            ollama_info = QLabel(
                f"✅ Ollama is running — {len(models)} model(s), {uncensored_count} uncensored\n"
                f"{model_text}"
            )
            ollama_info.setStyleSheet(f"color: {C['green']}; font-size: 10pt;")
        else:
            ollama_info = QLabel(
                "❌ Ollama is not running\n"
                "Start Ollama by running: ollama serve"
            )
            ollama_info.setStyleSheet(f"color: {C['red']}; font-size: 10pt;")
        ollama_info.setWordWrap(True)
        ollama_layout.addWidget(ollama_info)

        pull_label = QLabel(
            "MegaV auto-pulls uncensored models (Dolphin 3 Abliterated, Qwen3 14B Abliterated) "
            "when Ollama is running. 🔓 = uncensored, 🔒 = standard."
        )
        pull_label.setWordWrap(True)
        pull_label.setStyleSheet(f"color: {C['muted']}; font-size: 9pt;")
        ollama_layout.addWidget(pull_label)

        layout.addWidget(group_ollama)

        # ── Model Preferences ──────────────────────────────────
        group_pref = QGroupBox("Model Preferences")
        pref_layout = QVBoxLayout(group_pref)

        # Prefer uncensored checkbox
        uncensored_cb = QCheckBox("Prefer uncensored models (recommended)")
        uncensored_cb.setChecked(ModelRouter.get_prefer_uncensored())
        uncensored_cb.setToolTip("When enabled, uncensored local models are tried before cloud APIs")
        pref_layout.addWidget(uncensored_cb)

        # VRAM tier selector
        vram_layout = QHBoxLayout()
        vram_label = QLabel("GPU VRAM:")
        vram_label.setMinimumWidth(80)
        vram_combo = QComboBox()
        vram_combo.addItems([
            "12GB+ (best models)",
            "8-12GB (good models)",
            "4-8GB (lightweight)",
            "Auto-detect",
        ])
        current_tier = ModelRouter.get_vram_tier()
        vram_combo.setCurrentIndex(current_tier - 1 if 1 <= current_tier <= 3 else 3)
        vram_layout.addWidget(vram_label)
        vram_layout.addWidget(vram_combo)
        vram_layout.addStretch()
        pref_layout.addLayout(vram_layout)

        # Preferred local model selector
        model_layout = QHBoxLayout()
        model_label = QLabel("Local model:")
        model_label.setMinimumWidth(80)
        model_combo = QComboBox()
        model_combo.addItem("Auto (best available)")
        # Ollama Cloud models — always shown, work via signin OR API key
        for cm in ("kimi-k2.6:cloud", "qwen3.5:cloud", "minimax-m2.7:cloud", "glm-5.1:cloud"):
            model_combo.addItem(f"{cm} ☁", cm)
        if ollama_status.get("running"):
            for m in ollama_status.get("models", []):
                badge = " 🔓" if catalog.is_uncensored(m) else ""
                model_combo.addItem(f"{m}{badge}", m)
        preferred = ModelRouter.get_preferred_local_model()
        if preferred:
            idx = model_combo.findData(preferred)
            if idx >= 0:
                model_combo.setCurrentIndex(idx)
        model_layout.addWidget(model_label)
        model_layout.addWidget(model_combo)
        model_layout.addStretch()
        pref_layout.addLayout(model_layout)

        # Pull uncensored models button
        def _pull_uncensored():
            import subprocess
            models_to_pull = catalog.get_auto_pull_list(vram_tier=ModelRouter.get_vram_tier())
            if not models_to_pull:
                models_to_pull = catalog.AUTO_PULL_IDS[:2]  # fallback to top 2
            for mid in models_to_pull:
                try:
                    subprocess.Popen(
                        ["ollama", "pull", mid],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                    )
                except Exception:
                    pass
            self.chat_history.append(
                "<div style='margin:6px 0; padding:6px 10px; background:"
                + C["surface2"] + "; border-left:4px solid " + C["blue"]
                + "; border-radius:6px;'>"
                "<b style='color:" + C["blue"] + ";'>📦 Pulling uncensored models...</b><br>"
                "<span style='color:" + C["muted"] + "; font-size:9pt;'>"
                + ", ".join(models_to_pull)
                + "</span></div>"
            )
            self.chat_history.ensureCursorVisible()

        pull_btn = QPushButton("Pull Recommended Uncensored Models")
        pull_btn.setStyleSheet(f"""
            background: {C['amber']}; color: #000; font-weight: bold;
            border: none; border-radius: 4px; padding: 8px 16px; font-size: 10pt;
        """)
        pull_btn.clicked.connect(_pull_uncensored)
        pref_layout.addWidget(pull_btn)

        layout.addWidget(group_pref)

        # ── Buttons ─────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(dlg.accept)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        # Show dialog
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Save Anthropic API key
            new_key = key_input.text().strip()
            if new_key:
                ModelRouter.set_api_key(new_key)
                self.chat_history.append(
                    "<div style='margin:6px 0; padding:6px 10px; background:"
                    + C["surface2"] + "; border-left:4px solid " + C["green"]
                    + "; border-radius:6px;'>"
                    "<b style='color:" + C["green"] + ";'>✅ Anthropic API key saved!</b><br>"
                    "<span style='color:" + C["muted"] + "; font-size:9pt;'>"
                    "Claude models are now available. Use Tools > Check AI Status to verify.</span></div>"
                )
            elif not existing_key:
                ModelRouter.clear_api_key()
                self.chat_history.append(
                    "<div style='margin:6px 0; padding:6px 10px; background:"
                    + C["surface2"] + "; border-left:4px solid " + C["amber"]
                    + "; border-radius:6px;'>"
                    "<b style='color:" + C["amber"] + ";'>⚠️ API key removed</b><br>"
                    "<span style='color:" + C["muted"] + "; font-size:9pt;'>"
                    "MegaV will use local Ollama and DeepSeek models.</span></div>"
                )

            # Save DeepSeek API key
            new_ds_key = ds_key_input.text().strip()
            if new_ds_key:
                ModelRouter.set_deepseek_api_key(new_ds_key)
                self.chat_history.append(
                    "<div style='margin:6px 0; padding:6px 10px; background:"
                    + C["surface2"] + "; border-left:4px solid " + C["green"]
                    + "; border-radius:6px;'>"
                    "<b style='color:" + C["green"] + ";'>✅ DeepSeek API key saved!</b><br>"
                    "<span style='color:" + C["muted"] + "; font-size:9pt;'>"
                    "DeepSeek (uncensored cloud AI) is now available.</span></div>"
                )
            elif not existing_ds_key:
                ModelRouter.clear_deepseek_api_key()
                self.chat_history.append(
                    "<div style='margin:6px 0; padding:6px 10px; background:"
                    + C["surface2"] + "; border-left:4px solid " + C["amber"]
                    + "; border-radius:6px;'>"
                    "<b style='color:" + C["amber"] + ";'>⚠️ DeepSeek key removed</b></div>"
                )

            # Save OpenRouter API key
            new_or_key = or_key_input.text().strip()
            if new_or_key:
                ModelRouter.set_openrouter_api_key(new_or_key)
                self.chat_history.append(
                    "<div style='margin:6px 0; padding:6px 10px; background:"
                    + C["surface2"] + "; border-left:4px solid " + C["green"]
                    + "; border-radius:6px;'>"
                    "<b style='color:" + C["green"] + ";'>✅ OpenRouter API key saved!</b><br>"
                    "<span style='color:" + C["muted"] + "; font-size:9pt;'>"
                    "OpenRouter (100+ cloud models) is now available.</span></div>"
                )
            elif not existing_or_key:
                ModelRouter.clear_openrouter_api_key()
                self.chat_history.append(
                    "<div style='margin:6px 0; padding:6px 10px; background:"
                    + C["surface2"] + "; border-left:4px solid " + C["amber"]
                    + "; border-radius:6px;'>"
                    "<b style='color:" + C["amber"] + ";'>⚠️ OpenRouter key removed</b></div>"
                )

            # Save Ollama Cloud API key
            new_oc_key = oc_key_input.text().strip()
            if new_oc_key:
                ModelRouter.set_ollama_api_key(new_oc_key)
                self.chat_history.append(
                    "<div style='margin:6px 0; padding:6px 10px; background:"
                    + C["surface2"] + "; border-left:4px solid " + C["green"]
                    + "; border-radius:6px;'>"
                    "<b style='color:" + C["green"] + ";'>✅ Ollama Cloud key saved!</b><br>"
                    "<span style='color:" + C["muted"] + "; font-size:9pt;'>"
                    "Cloud models (kimi/qwen/minimax/glm) now reachable directly.</span></div>"
                )
            elif not existing_oc_key:
                ModelRouter.clear_ollama_api_key()

            # Save preferences
            ModelRouter.set_prefer_uncensored(uncensored_cb.isChecked())
            vram_idx = vram_combo.currentIndex()
            vram_tier = vram_idx + 1 if vram_idx < 3 else 1  # Auto-detect defaults to tier 1
            ModelRouter.set_vram_tier(vram_tier)
            selected_model = model_combo.currentData()
            ModelRouter.set_preferred_local_model(selected_model or "")

            # Sync the status-bar model picker with the new selection
            try:
                self._populate_model_picker()
                self._check_ai_status()
            except Exception:
                pass

            self.chat_history.ensureCursorVisible()

    def send_message(self):
        msg = self.message_input.text().strip()
        if not msg:
            return
        if self.worker and self.worker.isRunning():
            self.chat_history.append(
                "<i style='color:"
                + C["gray"]
                + ";'>Please wait — a task is already running.</i>"
            )
            return

        safe = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ts = _ts()
        self.chat_history.append(
            "<div style='margin:4px 0;'>"
            "<span style='color:" + C["blue"] + "; font-weight:bold;'>You</span> "
            "<span style='color:" + C["muted"] + "; font-size:8pt;'>[" + ts + "]</span>"
            "<br><span style='color:" + C["text"] + ";'>" + safe + "</span></div>"
        )
        self.message_input.clear()
        full_goal = self._build_message_with_files(msg)
        self._clear_attachments()
        self._start_task(full_goal)

    def _start_task(self, goal: str):
        self.send_button.setEnabled(False)
        self.message_input.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Running: " + goal[:60] + "…")

        # ── Check AI availability before executing ──────────────────────
        try:
            from src.providers.model_router import ModelRouter
            router = ModelRouter()
            if not router.is_available():
                fix = router._build_fix_hint(router.ollama_status())
                fix_html = fix.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                self.chat_history.append(
                    "<div style='margin:6px 0; padding:8px 10px; background:"
                    + C["surface2"] + "; border-left:4px solid " + C["red"]
                    + "; border-radius:6px;'>"
                    "<b style='color:" + C["red"] + ";'>No AI model available</b><br>"
                    "<span style='color:" + C["text"] + ";'>MegaV needs an AI model to process your request.</span><br><br>"
                    "<span style='color:" + C["muted"] + "; font-size:9pt;'>" + fix_html + "</span></div>"
                )
                self.chat_history.ensureCursorVisible()
                self.send_button.setEnabled(True)
                self.message_input.setEnabled(True)
                self.progress_bar.setVisible(False)
                self.status_bar.showMessage("No AI model available — see instructions above.")
                return
        except Exception:
            pass  # If check fails, proceed anyway
        self._current_goal = goal

        item = QListWidgetItem("[…] " + goal[:80])
        item.setForeground(QColor(C["amber"]))
        self.tasks_list.addItem(item)
        self._active_task_item = item
        self.tasks_list.scrollToBottom()
        self._right_tabs.setCurrentIndex(0)

        if not self.runtime:
            self._finish_task(
                {
                    "success": False,
                    "summary": "Agents not initialised. Try Tools → Reload Agents.",
                }
            )
            return

        self.worker = AgentWorker(self.runtime, goal)
        self.worker.finished.connect(self._finish_task)
        self.worker.step_update.connect(self._on_step_update)
        self.worker.start()

    # ── Progress ───────────────────────────────────────────────────────

    def _on_step_update(self, msg: str):
        self.status_bar.showMessage(msg[-80:])
        self.logs_text.append(msg)
        self.logs_text.ensureCursorVisible()

        sub = QListWidgetItem("   " + msg)
        sub.setForeground(QColor(C["muted"]))
        self.tasks_list.addItem(sub)
        self.tasks_list.scrollToBottom()

        # Show planning + execution steps in the chat panel
        key_prefixes = (
            "Routing to:",
            "Executing",
            "[1/",
            "[2/",
            "[3/",
            "[4/",
            "[5/",
            "[6/",
            "[7/",
            "[8/",
            "[9/",
            "Analys",
            "Building execution",
            "Plan ready",
            "Multi-phase plan",
            "Skill detected",
            "NEXUS pipeline",
            "Agency specialist",
            "  ->",
            "  SAVED:",
        )
        if any(p in msg for p in key_prefixes):
            clean = msg.split("] ", 1)[-1] if "] " in msg else msg
            clean_h = (
                clean.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            # Use different colours: plan steps vs result lines
            if clean.startswith("  ->") or clean.startswith("  SAVED"):
                color = C["teal"]
            elif any(
                clean.startswith(p) for p in ("Routing", "NEXUS", "Agency", "Skill")
            ):
                color = C["amber"]
            else:
                color = C["muted"]
            self.chat_history.append(
                "<i style='color:" + color + "; font-size:9pt;'>" + clean_h + "</i>"
            )
            self.chat_history.ensureCursorVisible()

    def _finish_task(self, result: dict):
        self.send_button.setEnabled(True)
        self.message_input.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.message_input.setFocus()

        if self._active_task_item:
            ok = result.get("success")
            txt = self._active_task_item.text().replace("[…]", "✓" if ok else "✗")
            self._active_task_item.setText(txt)
            self._active_task_item.setForeground(QColor(C["green"] if ok else C["red"]))
            self._active_task_item = None

        for entry in result.get("steps_log", []):
            icon = "  ✓" if entry.get("success") else "  ✗"
            detail = entry.get("summary", "")[:100]
            li = QListWidgetItem(
                icon
                + " "
                + entry.get("description", entry.get("action", ""))
                + " — "
                + detail
            )
            li.setForeground(QColor(C["muted"]))
            self.tasks_list.addItem(li)
        self.tasks_list.scrollToBottom()

        summary = result.get("summary", "")
        agent_name = result.get("agent", "MegaV")
        ts = _ts()
        if result.get("success"):
            html = (
                summary.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            self.chat_history.append(
                "<div style='margin:6px 0; padding:8px 10px; background:"
                + C["surface2"]
                + ";"
                "border-left:4px solid " + C["cyan"] + "; border-radius:6px;'>"
                "<b style='color:" + C["claude_orange"] + ";'>MegaV [" + agent_name + "]</b> "
                "<span style='color:"
                + C["muted"]
                + "; font-size:8pt;'>["
                + ts
                + "]</span>"
                "<br><span style='color:" + C["text"] + ";'>" + html + "</span></div>"
            )
            self.status_bar.showMessage("Done.")
            saved_path = self._extract_saved_path(result)
            if saved_path:
                self._show_output_notification(saved_path)
            elif len(summary) > 300:
                # Auto-save substantial output to Desktop via OutputEngine
                self._auto_save_to_desktop(
                    summary, self._current_goal, result_dict=result
                )
        else:
            err = summary or result.get("error", "Unknown error")
            err_h = err.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Add fix hint for common errors
            fix_hint = ""
            if "No LLM" in err or "No model" in err:
                fix_hint = "<br><span style='color:" + C["claude_amber"] + "; font-size:9pt;'>Try: Start Ollama with <code>ollama serve</code> or add an API key in Settings.</span>"
            self.chat_history.append(
                "<div style='margin:6px 0; padding:8px 10px; background:"
                + C["surface2"]
                + ";"
                "border-left:4px solid " + C["neon_pink"] + "; border-radius:6px;'>"
                "<b style='color:" + C["neon_pink"] + ";'>MegaV [" + agent_name + "]</b>"
                "<br><span style='color:" + C["text"] + ";'>" + err_h + "</span>" + fix_hint + "</div>"
            )
            self.status_bar.showMessage("Failed.")
            if result.get("traceback"):
                self._log_sys(result["traceback"])

        self.chat_history.ensureCursorVisible()

        self._task_history.append(
            {
                "goal": self._current_goal,
                "success": result.get("success", False),
                "summary": (result.get("summary", "") or "")[:200],
                "ts": ts,
            }
        )

        if self.runtime and self._current_goal:
            try:
                ws = self.runtime.get("workflow_store")
                if ws:
                    import re as _re

                    g = self._current_goal.lower()
                    if any(
                        x in g for x in ["browse", "linkedin", "indeed", "job", "web"]
                    ):
                        cat = "browser"
                    elif any(
                        x in g for x in ["write", "blog", "content", "email", "post"]
                    ):
                        cat = "content"
                    else:
                        cat = "creative_apps"
                    tag = "success" if result.get("success") else "failed"
                    name = _re.sub(r"[^\w\-]", "_", self._current_goal[:50]).strip("_")
                    ws.save_workflow(
                        name=name,
                        category=cat,
                        steps=result.get("steps_log", []),
                        description=self._current_goal[:200],
                        tags=["auto-recorded", tag],
                    )
            except Exception:
                pass

        if self.runtime:
            self._populate_skills_tab()
            self._populate_workflows_tab()
            self._populate_profile_tab()

    # ── Tab population ─────────────────────────────────────────────────

    # Execution type badge colours
    _EXEC_COLORS = {
        "prompt": C["blue"],
        "script": C["amber"],
        "hybrid": C["teal"],
    }

    # Category colour mapping
    _CAT_COLORS = {
        "content": C["neon_pink"],
        "career": C["pink"],
        "business": C["amber"],
        "automation": C["teal"],
        "integration": C["cyan"],
        "development": C["green"],
        "communication": C["blue"],
        "documents": C["orange"],
        "utility": C["gray"],
    }

    @staticmethod
    def _skill_val(skill, key: str, default="") -> str:
        """Get a field from a Skill object or plain dict."""
        if isinstance(skill, dict):
            return skill.get(key, default)
        # Skill dataclass — map execution_type enum to string
        val = getattr(skill, key, default)
        if hasattr(val, "value"):
            return val.value
        if isinstance(val, list):
            return val
        return val if val is not None else default

    def _populate_skills_tab(self):
        """Populate Skills tab using the new skill_engine SkillRegistry."""
        self.skills_list.clear()
        self._all_skill_items: list[tuple] = []

        try:
            registry = None
            if self.runtime:
                registry = self.runtime.get("skill_registry")

            # Lazy-load from new skill_engine package
            if registry is None:
                try:
                    import sys as _sys, os as _os

                    _app = _os.path.dirname(
                        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
                    )
                    if _app not in _sys.path:
                        _sys.path.insert(0, _app)
                    from skill_engine.registry import SkillRegistry as _SE_Registry

                    registry = _SE_Registry()
                except Exception:
                    pass

            if registry is None:
                self.skills_list.addItem(
                    "(Skill registry not available — check skills folder)"
                )
                self._skills_stats_label.setText("Skills unavailable")
                return

            summary = registry.summary()
            cats = summary.get("categories", [])
            total = summary.get("total", 0)
            self._skills_stats_label.setText(
                "Skills: "
                + str(total)
                + "  |  Categories: "
                + str(len(cats))
                + "  |  Keywords: "
                + str(summary.get("keyword_tokens", 0))
                + "  |  Root: "
                + _short_path(str(summary.get("skills_root", "")))
            )

            # Get all skills — new engine returns Skill dataclass objects
            skills = registry.all_skills()

            # Group by category
            cat_groups: dict[str, list] = {}
            cats_order: list[str] = []
            for s in skills:
                cat = str(self._skill_val(s, "category") or "general")
                if cat not in cat_groups:
                    cat_groups[cat] = []
                    cats_order.append(cat)
                cat_groups[cat].append(s)

            for cat in cats_order:
                cat_color = self._CAT_COLORS.get(cat, C["muted"])
                hdr = QListWidgetItem("  " + cat.upper())
                hdr.setForeground(QColor(cat_color))
                f = hdr.font()
                f.setBold(True)
                f.setPointSize(8)
                hdr.setFont(f)
                hdr.setFlags(Qt.ItemIsEnabled)
                hdr.setBackground(QColor(C["surface2"]))
                self.skills_list.addItem(hdr)

                for skill in cat_groups[cat]:
                    exec_t = str(self._skill_val(skill, "execution_type") or "prompt")
                    name = str(self._skill_val(skill, "name") or "?")
                    desc = str(self._skill_val(skill, "description") or "")[:72]
                    is_active = getattr(
                        skill,
                        "is_active",
                        skill.get("active", True) if isinstance(skill, dict) else True,
                    )
                    badge = {"prompt": "[P]", "script": "[S]", "hybrid": "[H]"}.get(
                        exec_t, "[?]"
                    )
                    dot = "●" if is_active else "○"
                    label = "    " + dot + "  " + badge + "  " + name + "  —  " + desc

                    item = QListWidgetItem(label)
                    exec_color = self._EXEC_COLORS.get(exec_t, C["muted"])
                    item.setForeground(QColor(exec_color if is_active else C["muted"]))
                    item.setData(Qt.UserRole, skill)
                    self.skills_list.addItem(item)
                    self._all_skill_items.append((item, skill))

        except Exception as exc:
            self.skills_list.addItem("(Error: " + str(exc) + ")")
            self._skills_stats_label.setText("Error loading skills")

    def _filter_skills_list(self, text: str):
        """Show/hide skill items based on search text."""
        q = text.lower().strip()
        for item, skill in getattr(self, "_all_skill_items", []):
            if not q:
                item.setHidden(False)
            else:
                kws = self._skill_val(skill, "trigger_keywords") or []
                haystack = (
                    str(self._skill_val(skill, "name")).lower()
                    + " "
                    + str(self._skill_val(skill, "category")).lower()
                    + " "
                    + str(self._skill_val(skill, "description")).lower()
                    + " "
                    + " ".join(kws if isinstance(kws, list) else [])
                )
                item.setHidden(q not in haystack)

    def _on_skill_selected(self, current, _previous):
        """Show skill detail when a skill row is clicked."""
        if current is None:
            return
        skill = current.data(Qt.UserRole)
        if not skill:
            return
        deps_raw = self._skill_val(skill, "dependencies") or []
        deps = ", ".join(deps_raw if isinstance(deps_raw, list) else []) or "none"
        kws_raw = self._skill_val(skill, "trigger_keywords") or []
        kws = ", ".join((kws_raw if isinstance(kws_raw, list) else [])[:6])
        uc_raw = self._skill_val(skill, "use_cases") or []
        uc = "  |  ".join((uc_raw if isinstance(uc_raw, list) else [])[:3])
        text = (
            str(self._skill_val(skill, "name"))
            + "  ["
            + str(self._skill_val(skill, "execution_type"))
            + "]"
            + "  |  "
            + str(self._skill_val(skill, "category"))
            + "\n"
            + "Deps: "
            + deps
            + "\n"
            + "Keywords: "
            + kws
            + "\n"
            + ("Use cases: " + uc + "\n" if uc else "")
            + str(self._skill_val(skill, "description"))
        )
        self._skill_detail.setText(text)

    def _populate_workflows_tab(self):
        pass  # Workflows tab removed

    def _populate_profile_tab(self):
        profile = {}
        try:
            ps = self.runtime.get("profile_store") if self.runtime else None
            if ps:
                profile = ps.user_profile or {}
        except Exception:
            pass
        self._profile_widget.refresh(profile, self._task_history)

    # ── Profile editor ─────────────────────────────────────────────────

    def _open_profile_editor(self):
        profile = {}
        try:
            ps = self.runtime.get("profile_store") if self.runtime else None
            if ps:
                profile = dict(ps.user_profile or {})
        except Exception:
            pass

        dlg = EditProfileDialog(profile, self)
        dlg.profile_saved.connect(self._on_profile_saved)
        dlg.exec()

    def _on_profile_saved(self, new_profile: dict):
        try:
            import json
            from src.integrations.profile_paths import profile_file

            path = profile_file("user_profile.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(new_profile, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            ps = self.runtime.get("profile_store") if self.runtime else None
            if ps:
                ps.user_profile = new_profile
            self._populate_profile_tab()
            self.status_bar.showMessage("Profile saved successfully.", 4000)
            self.chat_history.append(
                "<div style='padding:6px 10px; background:" + C["surface2"] + ";"
                "border-left:4px solid "
                + C["pink"]
                + "; border-radius:6px; margin:4px 0;'>"
                "<span style='color:"
                + C["pink"]
                + "; font-weight:bold;'>Profile updated</span>"
                " — changes saved to disk.</div>"
            )
        except Exception as exc:
            QMessageBox.warning(
                self, "Save Error", "Could not save profile:\n" + str(exc)
            )

    # ── Email tab ──────────────────────────────────────────────────────

    def _build_email_tab(self):
        try:
            from .email_tab import EmailTab

            self._email_tab_widget = EmailTab(runtime=self.runtime)
            self._email_tab_widget.action_logged.connect(
                lambda msg: self.status_bar.showMessage(msg, 4000)
            )
            self._right_tabs.removeTab(self._email_tab_idx)
            self._right_tabs.insertTab(
                self._email_tab_idx, self._email_tab_widget, "Email"
            )
            self._right_tabs.setCurrentIndex(0)
        except Exception as exc:
            self._log_sys("[Email tab] Could not load: " + str(exc))

    # ── Social tab ─────────────────────────────────────────────────────

    def _build_social_tab(self):
        try:
            from .social_tab import SocialTab

            social_tools = self.runtime.get("social_tools")
            if not social_tools:
                from src.tools_ext.social_tools import SocialTools

                social_tools = SocialTools()
                self.runtime["social_tools"] = social_tools
            self._social_tab_widget = SocialTab(social_tools)
            self._right_tabs.removeTab(self._social_tab_idx)
            self._right_tabs.insertTab(
                self._social_tab_idx, self._social_tab_widget, "Social"
            )
            self._right_tabs.setCurrentIndex(0)
        except Exception as exc:
            self._log_sys("[Social tab] Could not load: " + str(exc))

    # ── Approvals tab ────────────────────────────────────────────────

    def _build_approvals_tab(self):
        try:
            from PySide6.QtWidgets import (
                QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
                QPushButton, QFileDialog, QMessageBox,
            )
            from PySide6.QtCore import Qt
            from pathlib import Path
            import json
            import csv

            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(6, 6, 6, 6)
            v.addWidget(self._section_header("APPROVAL LOG", C["red"], ""))

            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["Timestamp", "Action", "Amount", "Recipient", "Decision"])
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setAlternatingRowColors(True)
            table.setStyleSheet(
                "QTableWidget { background:" + C["surface"] + "; border:1px solid " + C["border"] + "; border-radius:8px; }"
                "QHeaderView::section { background:" + C["surface2"] + "; color:" + C["text"] + "; padding:4px; }"
            )
            v.addWidget(table)

            btn_row = QHBoxLayout()
            refresh_btn = QPushButton("Refresh")
            refresh_btn.setStyleSheet(
                "QPushButton { background:" + C["surface2"] + "; color:" + C["text"] + "; border:1px solid " + C["border"] + "; border-radius:6px; padding:4px 12px; }"
                "QPushButton:hover { background:" + C["claude_orange"] + "; color:#fff; }"
            )
            export_btn = QPushButton("Export CSV")
            export_btn.setStyleSheet(refresh_btn.styleSheet())
            btn_row.addWidget(refresh_btn)
            btn_row.addWidget(export_btn)
            btn_row.addStretch()
            v.addLayout(btn_row)

            def load_log():
                table.setRowCount(0)
                log_path = Path.home() / ".megav" / "audit_log.jsonl"
                if not log_path.exists():
                    return
                try:
                    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
                    for line in lines:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        row = table.rowCount()
                        table.insertRow(row)
                        ts = entry.get("timestamp", "")
                        action = entry.get("action", "")
                        details = entry.get("details", {})
                        amount = str(details.get("amount", ""))
                        recipient = details.get("recipient") or details.get("client_email", "")
                        approved = entry.get("approved", False)
                        decision = "Approved" if approved else "Rejected"
                        table.setItem(row, 0, QTableWidgetItem(ts))
                        table.setItem(row, 1, QTableWidgetItem(action))
                        table.setItem(row, 2, QTableWidgetItem(amount))
                        table.setItem(row, 3, QTableWidgetItem(recipient))
                        table.setItem(row, 4, QTableWidgetItem(decision))
                        color = C["green"] if approved else C["red"]
                        for c in range(5):
                            table.item(row, c).setForeground(color)
                except Exception:
                    pass

            def export_csv():
                desktop = Path.home() / "Desktop"
                path, _ = QFileDialog.getSaveFileName(self, "Export Approval Log", str(desktop / "approvals.csv"), "CSV (*.csv)")
                if not path:
                    return
                try:
                    with open(path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["Timestamp", "Action", "Amount", "Recipient", "Decision"])
                        for r in range(table.rowCount()):
                            writer.writerow([table.item(r, c).text() for c in range(5)])
                    QMessageBox.information(self, "Exported", f"Saved to {path}")
                except Exception as exc:
                    QMessageBox.warning(self, "Export Error", str(exc))

            refresh_btn.clicked.connect(load_log)
            export_btn.clicked.connect(export_csv)
            load_log()

            self._approvals_tab_widget = w
            self._right_tabs.removeTab(self._approvals_tab_idx)
            self._right_tabs.insertTab(self._approvals_tab_idx, w, "Approvals")
            self._right_tabs.setCurrentIndex(0)
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            self._log_sys("[Approvals tab] Could not load: " + str(exc))
            print("[APPROVALS TAB ERROR]", exc)
            print(tb)

    # ── Dashboard tab ──────────────────────────────────────────────────

    def _build_dashboard_tab(self):
        try:
            from PySide6.QtWidgets import QGridLayout, QPushButton, QMessageBox
            from PySide6.QtCore import Qt
            from pathlib import Path
            import json

            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(6, 6, 6, 6)
            v.addWidget(self._section_header("BUSINESS DASHBOARD", C["green"], ""))

            # Revenue cards
            grid = QGridLayout()
            grid.setSpacing(8)

            def _card(title: str, value: str, color: str):
                lbl = QLabel(f"<b>{title}</b><br><span style='font-size:16pt; color:{color};'>{value}</span>")
                lbl.setStyleSheet(
                    f"background:{C['surface']}; border:1px solid {C['border']}; border-radius:8px; padding:8px;"
                )
                lbl.setAlignment(Qt.AlignCenter)
                return lbl

            self._dash_paid = _card("Paid This Month", "—", C["green"])
            self._dash_pending = _card("Pending", "—", C["electric_yellow"])
            self._dash_overdue = _card("Overdue", "—", C["red"])
            grid.addWidget(self._dash_paid, 0, 0)
            grid.addWidget(self._dash_pending, 0, 1)
            grid.addWidget(self._dash_overdue, 0, 2)
            v.addLayout(grid)

            # Stripe key resolved from env or encrypted CredentialStore — never settings.yaml.
            stripe_key = ""
            try:
                from src.integrations.secrets import get_stripe_key
                stripe_key = get_stripe_key()
            except Exception:
                pass

            # Stripe key input row
            key_row = QHBoxLayout()
            key_lbl = QLabel("Stripe Key:")
            key_lbl.setStyleSheet("color:" + C["muted"] + ";")
            self._stripe_input = QLineEdit()
            self._stripe_input.setEchoMode(QLineEdit.Password)
            self._stripe_input.setPlaceholderText("sk_test_...")
            self._stripe_input.setStyleSheet(
                "QLineEdit { background:" + C["surface"] + "; color:" + C["text"] + "; border:1px solid " + C["border"] + "; border-radius:6px; padding:4px 8px; }"
            )
            if stripe_key:
                self._stripe_input.setText(stripe_key)
            save_key_btn = QPushButton("Save")
            save_key_btn.setStyleSheet(
                "QPushButton { background:" + C["surface2"] + "; color:" + C["text"] + "; border:1px solid " + C["border"] + "; border-radius:6px; padding:4px 12px; }"
                "QPushButton:hover { background:" + C["claude_orange"] + "; color:#fff; }"
            )
            key_row.addWidget(key_lbl)
            key_row.addWidget(self._stripe_input, 1)
            key_row.addWidget(save_key_btn)
            v.addLayout(key_row)

            def save_stripe_key():
                key = self._stripe_input.text().strip()
                if not key:
                    QMessageBox.warning(self, "Missing Key", "Enter a Stripe key starting with sk_test_ or sk_live_")
                    return
                try:
                    from src.integrations.secrets import set_stripe_key
                    set_stripe_key(key)
                    QMessageBox.information(self, "Saved", "Stripe key saved to encrypted local store.")
                    refresh_dashboard()
                except Exception as exc:
                    QMessageBox.warning(self, "Save Error", str(exc))

            save_key_btn.clicked.connect(save_stripe_key)

            # Pipeline summary placeholder
            v.addWidget(QLabel("<b>Pipeline</b>"))
            self._dash_pipeline = QLabel("No CRM data available.")
            self._dash_pipeline.setStyleSheet("color:" + C["muted"] + "; padding:4px;")
            v.addWidget(self._dash_pipeline)

            # Recent activity
            v.addWidget(QLabel("<b>Recent Activity</b>"))
            self._dash_activity = QLabel("No recent activity.")
            self._dash_activity.setStyleSheet("color:" + C["muted"] + "; padding:4px;")
            v.addWidget(self._dash_activity)

            # Run Daily Operations button
            run_btn = QPushButton("Run Daily Operations")
            run_btn.setStyleSheet(
                "QPushButton { background:" + C["surface2"] + "; color:" + C["text"] + "; border:1px solid " + C["border"] + "; border-radius:6px; padding:6px 16px; }"
                "QPushButton:hover { background:" + C["claude_orange"] + "; color:#fff; }"
            )
            v.addWidget(run_btn)

            def refresh_dashboard():
                current_key = self._stripe_input.text().strip()
                if current_key:
                    try:
                        from src.integrations.payment_service import PaymentService
                        ps = PaymentService(current_key)
                        rev = ps.get_revenue_summary()
                        self._dash_paid.setText(f"<b>Paid This Month</b><br><span style='font-size:16pt; color:{C['green']};'>${rev['paid_this_month']:,.2f}</span>")
                        self._dash_pending.setText(f"<b>Pending</b><br><span style='font-size:16pt; color:{C['electric_yellow']};'>${rev['pending']:,.2f}</span>")
                        self._dash_overdue.setText(f"<b>Overdue</b><br><span style='font-size:16pt; color:{C['red']};'>${rev['overdue']:,.2f}</span>")
                    except Exception as exc:
                        self._dash_paid.setText(f"<b>Paid This Month</b><br><span style='font-size:16pt; color:{C['red']};'>Error: {exc}</span>")
                # Activity feed
                lines = []
                log_path = Path.home() / ".megav" / "audit_log.jsonl"
                if log_path.exists():
                    try:
                        for line in log_path.read_text(encoding="utf-8").strip().splitlines()[-10:]:
                            e = json.loads(line)
                            lines.append(f"{e['timestamp'][:19]} — {e['action']} — {'Approved' if e['approved'] else 'Rejected'}")
                    except Exception:
                        pass
                if lines:
                    self._dash_activity.setText("<br>".join(lines))

            def run_daily_ops():
                try:
                    import yaml
                    wf = yaml.safe_load(Path("workflows/daily_operations.yaml").read_text(encoding="utf-8"))
                    QMessageBox.information(self, "Daily Operations", f"Loaded workflow: {wf['name']} with {len(wf['tasks'])} tasks.")
                except Exception as exc:
                    QMessageBox.warning(self, "Error", str(exc))

            run_btn.clicked.connect(run_daily_ops)
            refresh_dashboard()

            self._dashboard_tab_widget = w
            self._right_tabs.removeTab(self._dashboard_tab_idx)
            self._right_tabs.insertTab(self._dashboard_tab_idx, w, "Dashboard")
            self._right_tabs.setCurrentIndex(0)
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            self._log_sys("[Dashboard tab] Could not load: " + str(exc))
            print("[DASHBOARD TAB ERROR]", exc)
            print(tb)

    # ── Discovery tab ────────────────────────────────────────────────────

    def _build_discovery_tab(self):
        try:
            from PySide6.QtWidgets import QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QColor as _QColor

            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(6, 6, 6, 6)
            v.addWidget(self._section_header("DISCOVERY", C["orange"], ""))

            # CLI table
            self._cli_table = QTableWidget()
            self._cli_table.setColumnCount(4)
            self._cli_table.setHorizontalHeaderLabels(["CLI", "Status", "Install Command", "Action"])
            self._cli_table.horizontalHeader().setStretchLastSection(True)
            self._cli_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self._cli_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self._cli_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self._cli_table.setAlternatingRowColors(True)
            self._cli_table.setStyleSheet(
                "QTableWidget { background:" + C["surface"] + "; border:1px solid " + C["border"] + "; border-radius:8px; }"
                "QHeaderView::section { background:" + C["surface2"] + "; color:" + C["text"] + "; padding:4px; }"
            )
            v.addWidget(self._cli_table)

            scan_btn = QPushButton("Scan Now")
            scan_btn.setStyleSheet(
                "QPushButton { background:" + C["surface2"] + "; color:" + C["text"] + "; border:1px solid " + C["border"] + "; border-radius:6px; padding:4px 12px; }"
                "QPushButton:hover { background:" + C["claude_orange"] + "; color:#fff; }"
            )
            v.addWidget(scan_btn)

            # Skill count label
            self._skill_count_label = QLabel("Skills: scanning…")
            self._skill_count_label.setStyleSheet("color:" + C["muted"] + "; padding:4px;")
            v.addWidget(self._skill_count_label)

            # Gap report
            self._gap_label = QLabel("Gap report: scanning…")
            self._gap_label.setStyleSheet("color:" + C["muted"] + "; padding:4px;")
            v.addWidget(self._gap_label)

            def do_scan():
                from src.discovery.cli_discovery import CLIDiscovery
                from src.discovery.skill_scanner import SkillScanner
                from src.discovery.capability_gap_analyzer import CapabilityGapAnalyzer

                report = CLIDiscovery().full_report()
                self._cli_table.setRowCount(0)
                installed = set(report["installed"])

                def _run_install(cmd: str):
                    def _inner():
                        try:
                            import subprocess
                            if cmd.startswith("pip "):
                                parts = ["python", "-m"] + cmd.split()
                            else:
                                parts = cmd.split()
                            subprocess.Popen(
                                ["cmd", "/c", "start", "cmd", "/k"] + parts,
                                creationflags=subprocess.CREATE_NEW_CONSOLE,
                            )
                            QMessageBox.information(self, "Installing", f"A terminal opened to run:\n{cmd}\n\nWait for it to finish, then click Scan Now.")
                        except Exception as exc:
                            QMessageBox.warning(self, "Install Error", str(exc))
                    return _inner

                for info in report["missing"]:
                    row = self._cli_table.rowCount()
                    self._cli_table.insertRow(row)
                    self._cli_table.setItem(row, 0, QTableWidgetItem(info["name"]))
                    self._cli_table.setItem(row, 1, QTableWidgetItem("Missing"))
                    self._cli_table.setItem(row, 2, QTableWidgetItem(info["install"]))
                    for c in range(3):
                        self._cli_table.item(row, c).setForeground(_QColor(C["red"]))
                    ibtn = QPushButton("Install")
                    ibtn.setStyleSheet(
                        "QPushButton { background:" + C["red"] + "; color:#fff; border:1px solid " + C["red"] + "; border-radius:4px; padding:2px 8px; font-size:8pt; }"
                        "QPushButton:hover { background:#ff6666; }"
                    )
                    ibtn.clicked.connect(_run_install(info["install"]))
                    self._cli_table.setCellWidget(row, 3, ibtn)
                for name in report["installed"]:
                    row = self._cli_table.rowCount()
                    self._cli_table.insertRow(row)
                    self._cli_table.setItem(row, 0, QTableWidgetItem(name))
                    self._cli_table.setItem(row, 1, QTableWidgetItem("Installed"))
                    self._cli_table.setItem(row, 2, QTableWidgetItem("—"))
                    self._cli_table.setItem(row, 3, QTableWidgetItem("—"))
                    for c in range(4):
                        self._cli_table.item(row, c).setForeground(_QColor(C["green"]))

                skills = SkillScanner().full_report()
                self._skill_count_label.setText(
                    f"Local skills available: {skills['local_skills_count']}  |  "
                    f"MCP servers: {', '.join(skills['installed_mcps']) or 'none'}"
                )

                gaps = CapabilityGapAnalyzer().generate_report()
                self._gap_label.setText(gaps.replace("\n", "<br>"))

            scan_btn.clicked.connect(do_scan)
            do_scan()

            self._discovery_tab_widget = w
            self._right_tabs.removeTab(self._discovery_tab_idx)
            self._right_tabs.insertTab(self._discovery_tab_idx, w, "Discovery")
            self._right_tabs.setCurrentIndex(0)
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            self._log_sys("[Discovery tab] Could not load: " + str(exc))
            print("[DISCOVERY TAB ERROR]", exc)
            print(tb)
            # Show error on placeholder so user sees it
            err_lbl = QLabel(f"Discovery tab failed to load:\n{exc}\n\nCheck logs for details.")
            err_lbl.setStyleSheet("color:" + C["red"] + "; font-size:10pt; padding:8px;")
            err_lbl.setAlignment(Qt.AlignCenter)
            self._discovery_placeholder = err_lbl

    # ── File attachment ────────────────────────────────────────────────

    def _attach_file(self):
        file_filter = (
            "All Supported Files (*.pdf *.docx *.doc *.xlsx *.xls *.csv *.pptx *.ppt "
            "*.txt *.md *.py *.js *.ts *.html *.css *.json *.xml *.yaml *.yml "
            "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.eml);;"
            "Documents (*.pdf *.docx *.doc *.xlsx *.xls *.csv *.pptx *.txt *.md);;"
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;"
            "Code Files (*.py *.js *.ts *.html *.css *.json *.xml *.yaml);;"
            "All Files (*)"
        )
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach Files to Message", "", file_filter
        )
        for path in paths:
            self._process_and_attach(path)

    def _process_and_attach(self, file_path: str):
        try:
            from src.tools_ext.file_processor import FileProcessor

            result = FileProcessor().process(file_path)
            import os

            file_name = os.path.basename(file_path)
            if result.get("success"):
                self._attached_files.append(
                    {
                        "file_path": file_path,
                        "file_name": file_name,
                        "result": result,
                    }
                )
                self._update_attach_bar()
                cat = result.get("category", "file").upper()
                summ = result.get("summary", file_name)
                self.chat_history.append(
                    "<div style='background:"
                    + C["surface2"]
                    + "; border-left:3px solid "
                    + C["blue"]
                    + ";"
                    "padding:6px 10px; margin:2px 0; font-size:9pt; border-radius:4px;'>"
                    "<b style='color:" + C["blue"] + ";'>📎 Attached:</b> "
                    "<span style='color:" + C["text"] + ";'>" + file_name + "</span> "
                    "<span style='color:"
                    + C["muted"]
                    + ";'>["
                    + cat
                    + "] — "
                    + summ
                    + "</span></div>"
                )
            else:
                err = result.get("error", "Could not read file")
                hint = result.get("install_hint", "")
                msg = (
                    "<span style='color:"
                    + C["red"]
                    + ";'>Could not read "
                    + file_name
                    + ": "
                    + err
                )
                if hint:
                    msg += "<br><i>Fix: " + hint + "</i>"
                msg += "</span>"
                self.chat_history.append(msg)
        except Exception as exc:
            self.chat_history.append(
                "<span style='color:"
                + C["red"]
                + ";'>File attach error: "
                + str(exc)
                + "</span>"
            )

    def _update_attach_bar(self):
        if self._attached_files:
            names = ", ".join(f["file_name"] for f in self._attached_files)
            count = len(self._attached_files)
            self._attach_label.setText(
                "📎 "
                + str(count)
                + " file"
                + ("s" if count > 1 else "")
                + " attached: "
                + names
            )
            self._attach_bar.setVisible(True)
        else:
            self._attach_bar.setVisible(False)

    def _clear_attachments(self):
        self._attached_files.clear()
        self._update_attach_bar()

    def _build_message_with_files(self, goal: str) -> str:
        if not self._attached_files:
            return goal
        try:
            from src.tools_ext.file_processor import FileProcessor

            blocks = [
                FileProcessor.build_context_block(a["result"])
                for a in self._attached_files
            ]
            return "\n\n".join(blocks) + "\n\n--- User Request ---\n" + goal
        except Exception:
            return goal

    # ── Helpers ────────────────────────────────────────────────────────

    def _log_sys(self, text: str):
        self.logs_text.append("[" + _ts() + "] " + text)

    def _extract_saved_path(self, result: dict) -> str:
        import re, os

        p = result.get("path", "")
        if p and os.path.exists(p):
            return p
        for match in re.finditer(
            r"([A-Za-z]:\\[^\n\r<>\"]+)", result.get("summary", "")
        ):
            c = match.group(1).strip()
            if os.path.exists(c):
                return c
        for d in result.get("details", []):
            p = d.get("path", "")
            if p and os.path.exists(p):
                return p
        return ""

    def _show_output_notification(self, path: str):
        import os
        from pathlib import Path

        safe = path.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        folder = str(Path(path).parent) if os.path.isfile(path) else path
        run_bat = os.path.join(folder, "run.bat")
        has_bat = os.path.isfile(run_bat)
        extra = ""
        if has_bat:
            extra = (
                "<br><span style='color:"
                + C["green"]
                + ";'>Double-click <b>run.bat</b> to launch it.</span>"
            )
        self.chat_history.append(
            "<div style='background:"
            + C["surface2"]
            + "; border-left:3px solid "
            + C["green"]
            + ";"
            "padding:8px 10px; margin:4px 0; border-radius:6px;'>"
            "<b style='color:" + C["green"] + ";'>Task Complete!</b><br>"
            "<span style='color:" + C["muted"] + ";'>Saved to:</span> "
            "<span style='color:"
            + C["blue"]
            + ";'>"
            + safe
            + "</span>"
            + extra
            + "</div>"
        )
        self.status_bar.showMessage("Done — output: " + path)
        try:
            import subprocess

            target = run_bat if has_bat else path
            subprocess.Popen('explorer /select,"' + target + '"')
        except Exception:
            pass

    def _auto_save_to_desktop(self, content: str, goal: str, result_dict=None):
        """Save task output to Desktop using the Output Intelligence Engine.

        Picks the best format (Excel/PDF/HTML/JSON/code/txt) based on the goal
        and result content.  Falls back to plain .txt if OutputEngine fails.
        """
        # ── Primary path: delegate to OutputEngine ────────────────────
        try:
            from src.tool_system.output_engine import get_output_engine

            r = result_dict if result_dict is not None else {"summary": content}
            export_path = get_output_engine().auto_export(goal, r)
            if export_path:
                self._show_output_notification(export_path)
                return
        except Exception as exc:
            self._log_sys(f"[OutputEngine] {exc}")

        # ── Fallback: plain .txt ───────────────────────────────────────
        try:
            import datetime, re as _re
            from pathlib import Path

            # Use local Desktop (NOT OneDrive)
            desktop = Path.home() / "Desktop"
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
                )
                real_desktop = winreg.QueryValueEx(key, "Desktop")[0]
                if real_desktop:
                    desktop = Path(real_desktop)
            except Exception:
                pass
            desktop.mkdir(parents=True, exist_ok=True)

            ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = _re.sub(r"[^\w]+", "_", goal[:45]).strip("_")
            out_path = desktop / f"MegaV_{slug}_{ts_str}.txt"

            goal_preview = goal[:200] + ("…" if len(goal) > 200 else "")
            header = (
                "MegaV Task Output\n"
                + "=" * 60
                + "\n"
                + f"Goal : {goal_preview}\n"
                + f"Date : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                + "=" * 60
                + "\n\n"
            )
            out_path.write_text(header + content, encoding="utf-8")
            self._show_output_notification(str(out_path))
        except Exception as exc:
            self._log_sys("[auto-save] " + str(exc))

    def closeEvent(self, event):
        import os as _os
        try:
            _os.remove(_os.path.join(_os.path.expanduser("~"), ".megav", "megav.pid"))
        except Exception:
            pass
        event.accept()
        from PySide6.QtWidgets import QApplication
        try:
            app = QApplication.instance()
            if app:
                app.processEvents()
                app.quit()
        except Exception:
            pass
        # Hard exit — prevents background QThreads / asyncio loops from keeping
        # pythonw.exe alive after the user clicks the X (zombie-window bug).
        _os._exit(0)

    def new_session(self):
        self.chat_history.clear()
        self.tasks_list.clear()
        self.logs_text.clear()
        self._clear_attachments()
        self._log_sys("--- New session ---")

    def show_about(self):
        QMessageBox.about(
            self,
            "About MegaV",
            "<h2 style='color:#4d9fff;'>MegaV 1.0</h2>"
            "<p>Local-first AI operator — coding, browser automation, desktop control,<br>"
            "email &amp; CRM, GitHub, social media, and 184-agent NEXUS orchestration.</p>"
            "<p>Type any goal in plain English and the agent executes it step by step.</p>"
            "<p><b>Skills:</b> 51 registered · <b>Agents:</b> 184 specialists across 14 domains</p>"
            "<p style='color:#7a8bb5;'>Built with PySide6 · Python 3.10+</p>",
        )
