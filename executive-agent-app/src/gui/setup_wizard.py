"""
First-run setup wizard for MegaV.
Guides the user through Ollama installation and model setup.
"""

import os
import sys
import json
import subprocess
import threading
import urllib.request
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QStackedWidget, QWidget, QProgressBar, QComboBox,
        QLineEdit, QCheckBox, QTextEdit, QApplication, QFrame,
        QRadioButton, QButtonGroup,
    )
    from PySide6.QtCore import Qt, Signal, QThread, QTimer
    from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QBrush, QPen, QLinearGradient, QIcon
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


# ── Ollama models — uncensored-first catalog ─────────────────────────────────
# Dynamically loaded from UncensoredModelCatalog, with fallback for import errors
def _get_models():
    try:
        from ..providers.uncensored_catalog import UncensoredModelCatalog
        return UncensoredModelCatalog().get_wizard_models()
    except Exception:
        # Fallback if import fails
        return [
            {"id": "huihui_ai/dolphin3-abliterated", "name": "Dolphin 3 Abliterated (Uncensored — recommended)", "size_gb": 4.9, "tag": "recommended", "uncensored": True},
            {"id": "dolphin-mistral", "name": "Dolphin Mistral (Uncensored — lightweight)", "size_gb": 4.1, "tag": "uncensored", "uncensored": True},
            {"id": "richardyoung/qwen3-14b-abliterated:Q4_K_M", "name": "Qwen3 14B Abliterated (Uncensored — best quality)", "size_gb": 9.0, "tag": "recommended", "uncensored": True},
            {"id": "R4C3R/qwen2.5-3b-heretic", "name": "Qwen 2.5 3B Heretic (Uncensored — ultra-light)", "size_gb": 2.0, "tag": "lightweight", "uncensored": True},
            {"id": "llama3.2", "name": "Llama 3.2 (Standard — censored)", "size_gb": 2.0, "tag": "censored", "uncensored": False},
            {"id": "mistral", "name": "Mistral 7B (Standard — censored)", "size_gb": 4.1, "tag": "censored", "uncensored": False},
        ]

MODELS = _get_models()

OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"
FIRST_RUN_MARKER     = Path(__file__).parent.parent.parent / "config" / "first_run_complete.json"


def is_first_run() -> bool:
    return not FIRST_RUN_MARKER.exists()


def mark_first_run_complete(profile_data: dict = None, model: str = "dolphin-mistral",
                             vram_tier: int = 1):
    """Save first-run completion and model choice to both the marker file and settings."""
    FIRST_RUN_MARKER.parent.mkdir(parents=True, exist_ok=True)
    FIRST_RUN_MARKER.write_text(
        json.dumps({"completed": True, "model": model, "profile": profile_data or {},
                     "vram_tier": vram_tier},
                   indent=2, ensure_ascii=False)
    )
    # Also save to ModelRouter settings so the choice is respected at runtime
    try:
        from src.providers.model_router import ModelRouter
        ModelRouter.set_preferred_local_model(model)
        ModelRouter.set_vram_tier(vram_tier)
        ModelRouter.set_prefer_uncensored(True)
    except Exception:
        pass


def is_ollama_installed() -> bool:
    import shutil
    return bool(shutil.which("ollama"))


def is_ollama_running() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def get_installed_models() -> list[str]:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            data = json.loads(r.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


# ── Background workers ──────────────────────────────────────────────────────

class OllamaInstallWorker(QThread if PYSIDE_AVAILABLE else object):
    progress  = Signal(str)
    finished  = Signal(bool, str)   # success, message

    def run(self):
        try:
            # 1. Download installer
            installer = Path.home() / "Downloads" / "OllamaSetup.exe"
            self.progress.emit("Downloading Ollama installer…")

            def _report(count, block, total):
                if total > 0:
                    pct = int(count * block * 100 / total)
                    self.progress.emit(f"Downloading… {pct}%")

            urllib.request.urlretrieve(OLLAMA_INSTALLER_URL, str(installer), _report)
            self.progress.emit("Download complete. Running installer…")

            # 2. Run installer silently
            result = subprocess.run(
                [str(installer), "/SILENT", "/NORESTART"],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode not in (0, 3010):   # 3010 = restart required
                self.finished.emit(False, f"Installer exited with code {result.returncode}")
                return

            # 3. Start Ollama service
            self.progress.emit("Starting Ollama service…")
            subprocess.Popen(["ollama", "serve"], creationflags=subprocess.DETACHED_PROCESS)
            import time; time.sleep(3)

            self.finished.emit(True, "Ollama installed and started successfully!")
        except Exception as e:
            self.finished.emit(False, str(e))


class ModelPullWorker(QThread if PYSIDE_AVAILABLE else object):
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, model_id: str):
        super().__init__()
        self.model_id = model_id

    def run(self):
        try:
            self.progress.emit(f"Pulling {self.model_id}… (this may take a few minutes)")
            process = subprocess.Popen(
                ["ollama", "pull", self.model_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.progress.emit(line[:100])
            process.wait()
            if process.returncode == 0:
                self.finished.emit(True, f"{self.model_id} is ready!")
            else:
                self.finished.emit(False, f"Pull failed (exit {process.returncode})")
        except Exception as e:
            self.finished.emit(False, str(e))


# ── Wizard dialog ────────────────────────────────────────────────────────────

class SetupWizard(QDialog if PYSIDE_AVAILABLE else object):
    """Multi-step first-run wizard."""

    setup_complete = Signal(dict)   # emits {"model": ..., "profile": ...}

    # ── Colours (unified vibrant theme) ────────────
    BG      = "#0a0e1a"
    PANEL   = "#141b2d"
    BORDER  = "#2a3a5c"
    ACCENT  = "#4d9fff"
    GREEN   = "#00e676"
    YELLOW  = "#ffb020"
    RED     = "#ff4444"
    TEXT    = "#f0f4ff"
    MUTED   = "#7a8bb5"
    CYAN    = "#00d4ff"
    PINK    = "#ff3e8a"
    PURPLE  = "#a855f7"
    TEAL    = "#00e5a0"
    SURFACE2 = "#1c2541"
    SURFACE3 = "#243052"

    def __init__(self, parent=None):
        if not PYSIDE_AVAILABLE:
            return
        super().__init__(parent)
        self.setWindowTitle("MegaV — First Run Setup")
        self.setFixedSize(680, 560)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog   {{ background:{self.BG}; color:{self.TEXT}; }}
            QLabel    {{ color:{self.TEXT}; }}
            QLineEdit {{
                background:{self.PANEL}; color:{self.TEXT}; border:1px solid {self.BORDER};
                border-radius:6px; padding:8px 12px; font-size:13px;
            }}
            QComboBox {{
                background:{self.PANEL}; color:{self.TEXT}; border:1px solid {self.BORDER};
                border-radius:6px; padding:6px 12px; font-size:12px;
            }}
            QComboBox QAbstractItemView {{
                background:{self.PANEL}; color:{self.TEXT}; selection-background-color:{self.ACCENT};
            }}
            QProgressBar {{
                background:{self.PANEL}; border:1px solid {self.BORDER};
                border-radius:4px; height:12px; text-align:center;
            }}
            QProgressBar::chunk {{ background:{self.ACCENT}; border-radius:3px; }}
            QTextEdit {{
                background:{self.PANEL}; color:{self.TEXT}; border:1px solid {self.BORDER};
                border-radius:6px; font-family:Consolas; font-size:11px;
            }}
        """)

        self._selected_model = "huihui_ai/dolphin3-abliterated"
        self._worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        hdr = QWidget(); hdr.setFixedHeight(64)
        hdr.setStyleSheet(f"background:{self.PANEL}; border-bottom:1px solid {self.BORDER};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 0, 24, 0)
        title_lbl = QLabel("MegaV"); title_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_lbl.setStyleSheet(f"color:{self.CYAN};")
        sub_lbl = QLabel("First-Run Setup Wizard"); sub_lbl.setStyleSheet(f"color:{self.MUTED}; font-size:12px;")
        hl.addWidget(title_lbl); hl.addSpacing(12); hl.addWidget(sub_lbl); hl.addStretch()
        root.addWidget(hdr)

        # Step indicator
        self._step_bar = self._make_step_bar()
        root.addWidget(self._step_bar)

        # Pages
        self._pages = QStackedWidget()
        self._pages.setStyleSheet(f"background:{self.BG};")
        self._pages.addWidget(self._page_welcome())    # 0
        self._pages.addWidget(self._page_ollama())     # 1
        self._pages.addWidget(self._page_model())      # 2
        self._pages.addWidget(self._page_profile())    # 3
        self._pages.addWidget(self._page_done())       # 4
        root.addWidget(self._pages, 1)

        # Nav buttons
        nav = QWidget(); nav.setFixedHeight(64)
        nav.setStyleSheet(f"background:{self.PANEL}; border-top:1px solid {self.BORDER};")
        nl = QHBoxLayout(nav); nl.setContentsMargins(24, 0, 24, 0)
        self._btn_back = self._btn("← Back", self.PANEL, self.MUTED, self._go_back)
        self._btn_next = self._btn("Next →", self.ACCENT, "#0d1117", self._go_next)
        nl.addWidget(self._btn_back); nl.addStretch(); nl.addWidget(self._btn_next)
        root.addWidget(nav)

        self._current_page = 0
        self._update_nav()

        # Skip wizard if Ollama + model already installed
        if is_ollama_installed() and get_installed_models():
            self._pages.setCurrentIndex(3)   # jump to profile
            self._current_page = 3
            self._update_nav()
            self._update_step_indicator()

    # ── Helpers ──────────────────────────────────────
    def _btn(self, text, bg, fg, slot, width=140):
        b = QPushButton(text)
        b.setFixedSize(width, 40)
        b.setFont(QFont("Segoe UI", 11, QFont.Medium))
        b.setStyleSheet(f"""
            QPushButton {{
                background:{bg}; color:{fg}; border:1px solid {self.BORDER};
                border-radius:8px; padding:0 16px;
            }}
            QPushButton:hover {{ background:{self.SURFACE3}; }}
            QPushButton:disabled {{ opacity:0.4; }}
        """)
        b.clicked.connect(slot)
        return b

    def _section(self, title, body_widget):
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(28, 20, 28, 8); v.setSpacing(8)
        lbl = QLabel(title); lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        lbl.setStyleSheet(f"color:{self.TEXT};")
        v.addWidget(lbl)
        v.addWidget(body_widget, 1)
        return w

    def _make_step_bar(self):
        w = QWidget(); w.setFixedHeight(36)
        w.setStyleSheet(f"background:{self.PANEL}; border-bottom:1px solid {self.BORDER};")
        h = QHBoxLayout(w); h.setContentsMargins(24, 0, 24, 0)
        steps = ["Welcome", "Ollama", "Model", "Profile", "Done"]
        self._step_labels = []
        for i, s in enumerate(steps):
            if i:
                sep = QLabel("›"); sep.setStyleSheet(f"color:{self.MUTED}; font-size:14px;")
                h.addWidget(sep)
            lbl = QLabel(f"{i+1}. {s}")
            lbl.setFont(QFont("Segoe UI", 10))
            self._step_labels.append(lbl)
            h.addWidget(lbl)
        h.addStretch()
        return w

    def _update_step_indicator(self):
        for i, lbl in enumerate(self._step_labels):
            if i == self._current_page:
                lbl.setStyleSheet(f"color:{self.ACCENT}; font-weight:bold;")
            elif i < self._current_page:
                lbl.setStyleSheet(f"color:{self.GREEN};")
            else:
                lbl.setStyleSheet(f"color:{self.MUTED};")

    # ── Pages ─────────────────────────────────────────
    def _page_welcome(self):
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(40, 30, 40, 10)
        v.setAlignment(Qt.AlignTop)

        title = QLabel("Welcome to MegaV")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet(f"color:{self.ACCENT};")

        sub = QLabel(
            "Your local AI operator — codes, browses, controls apps, hunts jobs,\n"
            "writes content, and automates any workflow — all running privately on YOUR machine."
        )
        sub.setStyleSheet(f"color:{self.MUTED}; font-size:13px; line-height:1.5;")
        sub.setWordWrap(True)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{self.BORDER};")

        feat_lbl = QLabel("What this setup will do:")
        feat_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))

        feats = QLabel(
            "  ✓  Check if Ollama (local AI engine) is installed\n"
            "  ✓  Install Ollama automatically if missing\n"
            "  ✓  Download your chosen AI model (runs 100% offline)\n"
            "  ✓  Set up your user profile for personalised results\n"
            "  ✓  Launch MegaV — ready to use!"
        )
        feats.setFont(QFont("Segoe UI", 12))
        feats.setStyleSheet(f"color:{self.TEXT}; line-height:2;")

        note = QLabel("No internet required after setup.  No data leaves your machine.  Free forever.")
        note.setStyleSheet(f"color:{self.GREEN}; font-size:11px;")

        for widget in [title, sub, sep, feat_lbl, feats, note]:
            v.addWidget(widget)
            if widget is title or widget is sub:
                v.addSpacing(8)
        v.addStretch()
        return w

    def _page_ollama(self):
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(40, 20, 40, 10)

        self._ollama_status_lbl = QLabel()
        self._ollama_status_lbl.setFont(QFont("Segoe UI", 13))
        self._ollama_status_lbl.setWordWrap(True)

        self._ollama_progress = QProgressBar()
        self._ollama_progress.setRange(0, 0)
        self._ollama_progress.setVisible(False)
        self._ollama_progress.setFixedHeight(12)

        self._ollama_log = QTextEdit()
        self._ollama_log.setReadOnly(True)
        self._ollama_log.setFixedHeight(120)
        self._ollama_log.setVisible(False)

        self._btn_install_ollama = self._btn("Install Ollama", self.ACCENT, "#0d1117",
                                              self._install_ollama, width=180)
        self._btn_skip_ollama = self._btn("Already Installed →", self.PANEL, self.MUTED,
                                           self._skip_ollama_check, width=200)

        for widget in [self._ollama_status_lbl, self._ollama_progress,
                        self._btn_install_ollama, self._btn_skip_ollama, self._ollama_log]:
            v.addWidget(widget)
            v.addSpacing(6)
        v.addStretch()

        # Set initial status
        self._refresh_ollama_status()
        return w

    def _page_model(self):
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(40, 20, 40, 10)

        lbl = QLabel("Choose your AI model:")
        lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        v.addWidget(lbl); v.addSpacing(8)

        self._model_combo = QComboBox()
        self._model_combo.setFixedHeight(40)
        for m in MODELS:
            tag = f"  [{m['tag'].upper()}]" if m["tag"] else ""
            self._model_combo.addItem(f"{m['name']}{tag}", m["id"])
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        v.addWidget(self._model_combo); v.addSpacing(4)

        self._model_size_lbl = QLabel()
        self._model_size_lbl.setStyleSheet(f"color:{self.MUTED}; font-size:11px;")
        v.addWidget(self._model_size_lbl)

        already = get_installed_models()
        if already:
            al = QLabel(f"Already installed: {', '.join(already)}")
            al.setStyleSheet(f"color:{self.GREEN}; font-size:11px;")
            v.addWidget(al)

        v.addSpacing(10)

        self._btn_pull = self._btn("Download & Install Model", self.GREEN, "#0d1117",
                                    self._pull_model, width=240)
        self._model_progress = QProgressBar()
        self._model_progress.setRange(0, 0)
        self._model_progress.setVisible(False)
        self._model_progress.setFixedHeight(12)
        self._model_log = QTextEdit()
        self._model_log.setReadOnly(True)
        self._model_log.setFixedHeight(100)
        self._model_log.setVisible(False)
        self._model_done_lbl = QLabel()
        self._model_done_lbl.setStyleSheet(f"color:{self.GREEN}; font-size:12px;")
        self._model_done_lbl.setVisible(False)

        for widget in [self._btn_pull, self._model_progress, self._model_log, self._model_done_lbl]:
            v.addWidget(widget); v.addSpacing(4)
        v.addStretch()

        self._on_model_changed(0)
        return w

    def _page_profile(self):
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(40, 20, 40, 10)

        lbl = QLabel("Your Profile  (optional — helps personalise results)")
        lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        v.addWidget(lbl); v.addSpacing(12)

        for field_label, attr in [
            ("Full Name",  "_pf_name"),
            ("Email",      "_pf_email"),
            ("Location",   "_pf_location"),
            ("Job Title / Role",  "_pf_title"),
            ("Skills  (comma-separated)",  "_pf_skills"),
        ]:
            row = QHBoxLayout()
            l = QLabel(f"{field_label}:")
            l.setFixedWidth(180)
            l.setStyleSheet(f"color:{self.MUTED}; font-size:12px;")
            inp = QLineEdit()
            inp.setFixedHeight(36)
            setattr(self, attr, inp)
            row.addWidget(l); row.addWidget(inp, 1)
            v.addLayout(row); v.addSpacing(4)

        skip_lbl = QLabel("You can update your profile at any time inside the app.")
        skip_lbl.setStyleSheet(f"color:{self.MUTED}; font-size:11px;")
        v.addSpacing(8); v.addWidget(skip_lbl)
        v.addStretch()
        return w

    def _page_done(self):
        w = QWidget()
        v = QVBoxLayout(w); v.setContentsMargins(40, 40, 40, 10)
        v.setAlignment(Qt.AlignTop)

        done_lbl = QLabel("🎉  Setup Complete!")
        done_lbl.setFont(QFont("Segoe UI", 22, QFont.Bold))
        done_lbl.setStyleSheet(f"color:{self.GREEN};")

        sub = QLabel("MegaV is ready.\nAll AI features are active and running locally on your machine.")
        sub.setFont(QFont("Segoe UI", 13))
        sub.setStyleSheet(f"color:{self.TEXT};")
        sub.setWordWrap(True)

        tips_lbl = QLabel("Quick-start tips:")
        tips_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        tips_lbl.setStyleSheet(f"color:{self.ACCENT};")

        tips = QLabel(
            '  • Type any goal in plain English: "Build me a calculator app"\n'
            '  • Browse the web: "Search for AI jobs on LinkedIn"\n'
            '  • Control your desktop: "Open Notepad and type Hello World"\n'
            '  • Write content: "Write a LinkedIn post about AI productivity"\n'
            '  • Remember data: "Remember my email is me@example.com"'
        )
        tips.setFont(QFont("Segoe UI", 12))
        tips.setStyleSheet(f"color:{self.TEXT};")

        for widget in [done_lbl, sub, tips_lbl, tips]:
            v.addWidget(widget)
            v.addSpacing(10)
        v.addStretch()
        return w

    # ── Navigation ────────────────────────────────────
    def _go_next(self):
        if self._current_page == 4:
            self._finish()
            return
        if self._current_page < self._pages.count() - 1:
            self._current_page += 1
            self._pages.setCurrentIndex(self._current_page)
            self._update_nav()
            self._update_step_indicator()
            self._on_page_enter(self._current_page)

    def _go_back(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._pages.setCurrentIndex(self._current_page)
            self._update_nav()
            self._update_step_indicator()

    def _update_nav(self):
        self._btn_back.setEnabled(self._current_page > 0)
        if self._current_page == 4:
            self._btn_next.setText("Launch MegaV  ▶")
            self._btn_next.setFixedWidth(240)
        else:
            self._btn_next.setText("Next →")
            self._btn_next.setFixedWidth(140)

    def _on_page_enter(self, page: int):
        if page == 1:
            self._refresh_ollama_status()

    def _finish(self):
        # Save profile if filled
        profile = {}
        name  = self._pf_name.text().strip()
        email = self._pf_email.text().strip()
        loc   = self._pf_location.text().strip()
        title = self._pf_title.text().strip()
        skills_raw = self._pf_skills.text().strip()

        if name or email:
            profile = {
                "name": name or "User",
                "location": loc,
                "emails": [email] if email else [],
                "job_titles": [title] if title else [],
                "skills": [s.strip() for s in skills_raw.split(",") if s.strip()],
            }
            # Save profile to user-scoped data dir (never inside the repo)
            try:
                from src.integrations.profile_paths import profile_file
                profile_path = profile_file("user_profile.json")
                existing = {}
                if profile_path.exists():
                    existing = json.loads(profile_path.read_text())
                existing.update(profile)
                profile_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
            except Exception:
                pass

        mark_first_run_complete(profile, self._selected_model)
        self.setup_complete.emit({"model": self._selected_model, "profile": profile})
        self.accept()

    # ── Ollama install ────────────────────────────────
    def _refresh_ollama_status(self):
        if is_ollama_installed():
            running = is_ollama_running()
            models  = get_installed_models()
            if running and models:
                self._ollama_status_lbl.setText(
                    f"✅  Ollama is installed and running.\n"
                    f"Models available: {', '.join(models[:4])}\n\n"
                    "Click Next to choose your model."
                )
                self._ollama_status_lbl.setStyleSheet(f"color:{self.GREEN};")
            elif running:
                self._ollama_status_lbl.setText(
                    "✅  Ollama is running but no models downloaded yet.\n"
                    "Click Next to download a model."
                )
                self._ollama_status_lbl.setStyleSheet(f"color:{self.YELLOW};")
            else:
                self._ollama_status_lbl.setText(
                    "⚠  Ollama is installed but not running.\n"
                    "It will start automatically when you use the app."
                )
                self._ollama_status_lbl.setStyleSheet(f"color:{self.YELLOW};")
            self._btn_install_ollama.setVisible(False)
            self._btn_skip_ollama.setVisible(False)
        else:
            self._ollama_status_lbl.setText(
                "⚠  Ollama is not installed on this machine.\n\n"
                "Ollama is the free, local AI engine that powers MegaV.\n"
                "It runs entirely on your computer — no cloud, no subscription.\n\n"
                "Click Install Ollama to download and set it up automatically."
            )
            self._ollama_status_lbl.setStyleSheet(f"color:{self.YELLOW};")
            self._btn_install_ollama.setVisible(True)
            self._btn_skip_ollama.setVisible(True)

    def _install_ollama(self):
        self._btn_install_ollama.setEnabled(False)
        self._btn_skip_ollama.setEnabled(False)
        self._ollama_progress.setVisible(True)
        self._ollama_log.setVisible(True)

        self._worker = OllamaInstallWorker()
        self._worker.progress.connect(lambda m: self._ollama_log.append(m))
        self._worker.finished.connect(self._on_ollama_install_done)
        self._worker.start()

    def _on_ollama_install_done(self, success: bool, msg: str):
        self._ollama_progress.setVisible(False)
        if success:
            self._ollama_status_lbl.setText(f"✅  {msg}")
            self._ollama_status_lbl.setStyleSheet(f"color:{self.GREEN};")
            self._ollama_log.append(f"✅ {msg}")
        else:
            self._ollama_status_lbl.setText(
                f"❌  Install failed: {msg}\n\n"
                "Please install Ollama manually from:\nhttps://ollama.com/download"
            )
            self._ollama_status_lbl.setStyleSheet(f"color:{self.RED};")
            self._btn_install_ollama.setEnabled(True)
            self._btn_skip_ollama.setEnabled(True)

    def _skip_ollama_check(self):
        self._go_next()

    # ── Model pull ────────────────────────────────────
    def _on_model_changed(self, idx: int):
        m = MODELS[idx] if idx < len(MODELS) else MODELS[0]
        self._selected_model = m["id"]
        self._model_size_lbl.setText(f"Download size: {m['size']}")

    def _pull_model(self):
        if not is_ollama_running():
            # Try to start Ollama first
            try:
                subprocess.Popen(["ollama", "serve"],
                                  creationflags=subprocess.DETACHED_PROCESS)
                import time; time.sleep(2)
            except Exception:
                pass

        model_id = self._selected_model
        already = get_installed_models()
        if any(model_id in m for m in already):
            self._model_done_lbl.setText(f"✅  {model_id} is already installed!")
            self._model_done_lbl.setVisible(True)
            self._btn_pull.setEnabled(False)
            return

        self._btn_pull.setEnabled(False)
        self._model_progress.setVisible(True)
        self._model_log.setVisible(True)

        self._worker = ModelPullWorker(model_id)
        self._worker.progress.connect(lambda m: (self._model_log.append(m),
                                                   self._model_log.ensureCursorVisible()))
        self._worker.finished.connect(self._on_pull_done)
        self._worker.start()

    def _on_pull_done(self, success: bool, msg: str):
        self._model_progress.setVisible(False)
        if success:
            self._model_done_lbl.setText(f"✅  {msg}")
            self._model_done_lbl.setStyleSheet(f"color:{self.GREEN}; font-size:12px;")
        else:
            self._model_done_lbl.setText(f"❌  {msg}")
            self._model_done_lbl.setStyleSheet(f"color:{self.RED}; font-size:12px;")
            self._btn_pull.setEnabled(True)
        self._model_done_lbl.setVisible(True)


# ── Public entry point ───────────────────────────────────────────────────────

def run_setup_wizard_if_needed(app: "QApplication") -> bool:
    """Show setup wizard on first run.  Returns True if user completed or dismissed it.

    NOTE: Regardless of whether the user clicks 'Launch MegaV' or closes the dialog,
    the first-run marker is written so the wizard never re-appears on subsequent launches.
    The main window always opens after this function returns.
    """
    if not is_first_run():
        return True

    if not PYSIDE_AVAILABLE:
        mark_first_run_complete()
        return True

    wizard = SetupWizard()
    wizard.exec()

    # Always mark first-run complete — even if user X-closes or presses Escape.
    # The wizard is informational; it must not block the app from launching.
    if is_first_run():
        mark_first_run_complete()

    return True   # always allow main window to open
