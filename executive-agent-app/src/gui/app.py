"""Main GUI application — MegaV."""

import sys
import os
from pathlib import Path
import datetime

_LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "app_debug.log"
)
os.makedirs(os.path.dirname(_LOG_FILE), exist_ok=True)


def _log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
    except Exception:
        pass
    try:
        print(line, end="", flush=True)
    except Exception:
        pass


_log("DEBUG: app.py module loaded")

# Wire Python's logging module to app_debug.log so megav.* loggers are visible
import logging as _logging
_megav_handler = _logging.FileHandler(_LOG_FILE, encoding="utf-8")
_megav_handler.setFormatter(_logging.Formatter("[%(asctime)s] %(name)s %(levelname)s: %(message)s", "%H:%M:%S"))
_megav_logger = _logging.getLogger("megav")
_megav_logger.setLevel(_logging.DEBUG)
_megav_logger.addHandler(_megav_handler)
_megav_logger.propagate = False


IS_WIN = sys.platform == "win32"

# ── Windows taskbar icon fix ──────────────────────────────────────────────────
# Must be called BEFORE QApplication is created so Windows groups the process
# under our custom icon instead of the generic python.exe icon.
if IS_WIN:
    try:
        import ctypes

        _APP_ID = "MegaV.LocalAI.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)
    except Exception:
        pass

# Check if PySide6 is available
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QIcon

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

from .main_window import MainWindow

# Resolve icon paths relative to this file
_ASSETS = Path(__file__).parent.parent / "assets"
_ICO = _ASSETS / "icon.ico"
_PNG = _ASSETS / "icon_256.png"


def _app_icon() -> "QIcon":
    """Return the best available app icon (multi-resolution)."""
    icon = QIcon()
    # Add all available sizes for crisp rendering at every DPI
    for path in (_ICO, _PNG):
        if path.exists():
            icon = QIcon(str(path))
            break
    return icon


class ExecutiveAgentApp:
    """Main GUI application class."""

    def __init__(self):
        self.app = None
        self.main_window = None

    def run(self) -> int:
        if not PYSIDE_AVAILABLE:
            print("Error: PySide6 not installed. Run: pip install pyside6")
            return 1

        # High-DPI support
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        self.app = QApplication(sys.argv)
        self.app.setApplicationName("MegaV")
        self.app.setApplicationDisplayName("MegaV")
        self.app.setApplicationVersion("2.7.0")
        self.app.setOrganizationName("MegaV")
        self.app.setOrganizationDomain("executive-agent.local")

        # Set icon for the whole app (taskbar, alt-tab, title bar, notification area)
        icon = _app_icon()
        self.app.setWindowIcon(icon)

        # ── Splash screen — shown immediately so user knows app is loading ──
        splash = None
        try:
            from PySide6.QtWidgets import QSplashScreen
            from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
            from PySide6.QtCore import Qt as _Qt
            px = QPixmap(480, 260)
            px.fill(QColor("#0d1117"))
            p = QPainter(px)
            p.setRenderHint(QPainter.Antialiasing)
            # Border
            from PySide6.QtGui import QPen
            p.setPen(QPen(QColor("#1f4e79"), 2))
            p.drawRoundedRect(2, 2, 476, 256, 12, 12)
            # Logo image centred in upper portion
            logo_px = QPixmap(str(_PNG))
            if not logo_px.isNull():
                logo_scaled = logo_px.scaled(
                    110, 110,
                    _Qt.AspectRatioMode.KeepAspectRatio,
                    _Qt.TransformationMode.SmoothTransformation,
                )
                lx = (480 - logo_scaled.width()) // 2
                p.drawPixmap(lx, 30, logo_scaled)
            # App name below logo
            p.setPen(QColor("#4d9fff"))
            p.setFont(QFont("Segoe UI", 22, QFont.Bold))
            p.drawText(0, 155, 480, 36, _Qt.AlignmentFlag.AlignHCenter, "MegaV")
            # Subtitle
            p.setPen(QColor("#8b949e"))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(0, 210, 480, 28, _Qt.AlignmentFlag.AlignHCenter, "Loading… please wait")
            p.end()
            splash = QSplashScreen(px)
            splash.show()
            self.app.processEvents()
            _log("Splash screen shown")
        except Exception as sp_err:
            _log(f"Splash skipped: {sp_err}")

        # First-run setup wizard — installs Ollama, pulls model, collects profile
        # NOTE: wizard dismissal (X / cancel) must NOT block the app from launching.
        # MainWindow always shows regardless of wizard outcome.
        try:
            _log("Before importing setup_wizard...")
            from .setup_wizard import (
                run_setup_wizard_if_needed,
                mark_first_run_complete,
                is_first_run,
            )

            _log("setup_wizard imported, checking if first run...")
            if is_first_run():
                _log("First run detected, calling run_setup_wizard_if_needed...")
                run_setup_wizard_if_needed(self.app)  # result intentionally ignored
                _log(
                    "run_setup_wizard_if_needed returned, marking first run complete..."
                )
                try:
                    mark_first_run_complete()
                except Exception:
                    pass
                _log("First run setup complete")
            else:
                _log("Not first run, skipping wizard")
        except Exception as _wiz_err:
            _log(f"[setup_wizard] skipped: {_wiz_err}")

        _log("Creating MainWindow...")
        try:
            self.main_window = MainWindow()
            _log("MainWindow created, setting icon...")
            self.main_window.setWindowIcon(icon)

            # Center the window on the primary screen
            try:
                screen = self.app.primaryScreen()
                if screen:
                    geo = screen.availableGeometry()
                    x = geo.x() + (geo.width() - self.main_window.width()) // 2
                    y = geo.y() + (geo.height() - self.main_window.height()) // 2
                    self.main_window.move(x, y)
                    _log(f"Window centered at ({x}, {y})")
            except Exception as pos_err:
                _log(f"Centering skipped: {pos_err}")

            # Close splash before showing main window
            if splash:
                try:
                    splash.finish(self.main_window)
                except Exception:
                    try:
                        splash.close()
                    except Exception:
                        pass

            _log("Calling show()...")

            # ── Force window to front using "always on top" trick ──────────
            # Set StayOnTop, show, then remove the flag after 2s.
            # This guarantees the window appears above everything else on launch.
            try:
                self.main_window.setWindowFlags(
                    self.main_window.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
                )
            except Exception:
                pass

            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

            # Windows-specific force-foreground
            if IS_WIN:
                try:
                    import ctypes
                    hwnd = int(self.main_window.winId())
                    # AttachThreadInput trick — makes SetForegroundWindow always work
                    fg_thread = ctypes.windll.user32.GetWindowThreadProcessId(
                        ctypes.windll.user32.GetForegroundWindow(), None)
                    our_thread = ctypes.windll.kernel32.GetCurrentThreadId()
                    if fg_thread != our_thread:
                        ctypes.windll.user32.AttachThreadInput(fg_thread, our_thread, True)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    ctypes.windll.user32.BringWindowToTop(hwnd)
                    if fg_thread != our_thread:
                        ctypes.windll.user32.AttachThreadInput(fg_thread, our_thread, False)
                    _log("Win32 SetForegroundWindow called")
                except Exception as fg_err:
                    _log(f"Win32 foreground failed: {fg_err}")

            # Remove StayOnTop after 2s via Win32 (avoids rebuilding the HWND
            # which setWindowFlags would do and which breaks the close button).
            if IS_WIN:
                def _remove_stay_on_top():
                    try:
                        import ctypes
                        HWND_NOTOPMOST = -2
                        SWP_NOMOVE = 0x0002
                        SWP_NOSIZE = 0x0001
                        hwnd = int(self.main_window.winId())
                        ctypes.windll.user32.SetWindowPos(
                            hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE
                        )
                        _log("StayOnTop removed via SetWindowPos")
                    except Exception:
                        pass

                QTimer.singleShot(2000, _remove_stay_on_top)

            # ── Graceful shutdown — close browser/workflow/email resources ──
            def _graceful_shutdown():
                try:
                    runtime = getattr(self.main_window, "runtime", None) or {}
                except Exception:
                    runtime = {}
                for key in ("browser_tools", "workflow_store", "email_service"):
                    obj = runtime.get(key) if isinstance(runtime, dict) else None
                    if obj is None:
                        continue
                    for method_name in ("close", "shutdown", "flush", "save"):
                        method = getattr(obj, method_name, None)
                        if callable(method):
                            try:
                                method()
                            except Exception:
                                pass
                            break
                _log("Graceful shutdown hook completed")

            try:
                self.app.aboutToQuit.connect(_graceful_shutdown)
            except Exception:
                pass
        except Exception as _mw_err:
            _log(f"ERROR creating MainWindow: {_mw_err}")
            import traceback

            _log(traceback.format_exc())
            return 1

        _log("Entering event loop...")
        ret = self.app.exec()
        _log(f"Event loop exited (code {ret})")
        return ret


def main():
    """Entry point for GUI application."""
    app = ExecutiveAgentApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
