#!/usr/bin/env python3
"""MegaV — Main Launcher.

Cross-platform single-instance guard via PID-file lock.
Windows-specific zombie-window detection runs only on Windows.
"""

import sys
import os
import datetime
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(_HERE)
sys.path.insert(0, _HERE)

IS_WIN = sys.platform == "win32"

_LOG_DIR  = os.path.join(_HERE, "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "startup.log")
os.makedirs(_LOG_DIR, exist_ok=True)

# Global Windows mutex handle — must stay alive for the process lifetime
_MUTEX_HANDLE = None

# PID file for cross-platform single-instance detection
_PID_FILE = os.path.join(os.path.expanduser("~"), ".megav", "megav.pid")


def _log(msg: str):
    ts   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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


def _write_pid():
    try:
        os.makedirs(os.path.dirname(_PID_FILE), exist_ok=True)
        with open(_PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def _read_pid():
    try:
        with open(_PID_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return None


def _delete_pid():
    try:
        os.remove(_PID_FILE)
    except Exception:
        pass


def _pid_alive(pid: int) -> bool:
    """Strong liveness check — verifies the PID is actually a running MegaV.

    Returns True only if:
      1. A process with this PID exists, AND
      2. Its executable is python/pythonw (not a system service that reused the PID), AND
      3. Its command line includes 'run.py' or 'megav'.

    Without (2) + (3), low PIDs that get recycled to svchost/lsass/etc. would
    permanently lock out MegaV launches.
    """
    if pid <= 0:
        return False
    try:
        import psutil  # type: ignore
        if not psutil.pid_exists(pid):
            return False
        try:
            p = psutil.Process(pid)
            name = (p.name() or "").lower()
            if name not in ("pythonw.exe", "python.exe", "pythonw", "python"):
                return False
            try:
                cmdline = " ".join(p.cmdline()).lower()
            except (psutil.AccessDenied, Exception):
                cmdline = ""
            return "run.py" in cmdline or "megav" in cmdline
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    except ImportError:
        pass
    # No psutil — best-effort fallback that cannot verify identity.
    # Treat unknown PID as DEAD to avoid the lock-out bug; worst case the user
    # gets an extra MegaV instance, which is recoverable. Locking them out is not.
    if IS_WIN:
        return False
    try:
        os.kill(pid, 0)
        return False  # cannot verify identity → assume dead
    except (ProcessLookupError, PermissionError):
        return False
    except Exception:
        return False


def _kill_pid(pid: int) -> bool:
    """Graceful terminate, then hard kill after timeout."""
    if pid <= 0:
        return False
    try:
        import psutil  # type: ignore
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
            return True
        except psutil.NoSuchProcess:
            return True
        except Exception:
            return False
    except ImportError:
        pass
    if IS_WIN:
        try:
            import ctypes
            PROCESS_TERMINATE = 1
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle:
                ctypes.windll.kernel32.TerminateProcess(handle, 0)
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
        except Exception:
            pass
        return False
    try:
        import signal
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            time.sleep(0.1)
            if not _pid_alive(pid):
                return True
        os.kill(pid, signal.SIGKILL)
        return True
    except Exception:
        return False


def _acquire_mutex() -> bool:
    """Cross-platform single-instance guard.

    Strategy:
      1. If PID file exists and the recorded PID is alive, refuse to launch.
      2. Otherwise (no PID file, stale PID), claim the slot.
      3. On Windows, additionally hold a named kernel mutex to block races
         between the moment we read the PID file and the moment we write it.
    """
    global _MUTEX_HANDLE

    if IS_WIN:
        try:
            import ctypes
            _MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(
                None, True, "Global\\MegaV_SingleInstance_v2"
            )
            err = ctypes.windll.kernel32.GetLastError()
            if err == 183:  # ERROR_ALREADY_EXISTS
                # Another live process owns the named mutex.
                return False
        except Exception:
            # Mutex unavailable — fall through to PID check only
            _MUTEX_HANDLE = None

    old_pid = _read_pid()
    if old_pid and old_pid != os.getpid():
        if _pid_alive(old_pid):
            return False
        # Stale PID file (process exited or PID was reused by a non-MegaV process)
        _log(f"Removing stale PID file (PID={old_pid} not a live MegaV)")
        _delete_pid()
    return True


def _find_megav_window():
    """Windows-only: return hwnd of a live MegaV window, or None.

    Filters by process owner (must be pythonw/python.exe) so browser tabs
    or editor windows containing 'MegaV' in their titles do not match.
    """
    if not IS_WIN:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        # Build set of valid owner PIDs: any python/pythonw process running run.py
        valid_pids = set()
        try:
            import psutil  # type: ignore
            for p in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    name = (p.info.get("name") or "").lower()
                    if name not in ("pythonw.exe", "python.exe"):
                        continue
                    cmd = " ".join(p.info.get("cmdline") or []).lower()
                    if "run.py" in cmd or "megav" in cmd:
                        valid_pids.add(p.info["pid"])
                except Exception:
                    continue
        except ImportError:
            pass

        CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        candidates = []
        def _cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            owner_pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
            # If we have a known valid PID set, restrict to it. Otherwise
            # fall back to title check (best-effort if psutil missing).
            if valid_pids and owner_pid.value not in valid_pids:
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                title = buf.value
                tlow = title.lower()
                # Tight match: window title must START with "megav" (the Qt
                # window sets it to "MegaV v2.7"). Browser tab titles like
                # "MegaV App Audit - Google Chrome" still wouldn't pass the
                # PID filter, but we also tighten this for the no-psutil case.
                if tlow.startswith("megav") and ".xlsx" not in tlow and ".csv" not in tlow:
                    candidates.append(hwnd)
            return True
        user32.EnumWindows(CB(_cb), 0)
        for hwnd in candidates:
            res = ctypes.c_ulong(0)
            sent = user32.SendMessageTimeoutW(hwnd, 0, 0, 0, 0x0002, 1500,
                                              ctypes.byref(res))
            if sent != 0:
                return hwnd
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            _log(f"Closed zombie MegaV window hwnd={hwnd}")
        return None
    except Exception:
        return None


def _raise_megav_window(hwnd):
    if not IS_WIN:
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        u.ShowWindow(hwnd, 9)          # SW_RESTORE
        u.SetForegroundWindow(hwnd)
        u.BringWindowToTop(hwnd)
    except Exception:
        pass


def show_error(title: str, message: str):
    _log(f"ERROR: {title} — {message}")
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        _app = QApplication.instance() or QApplication(sys.argv)
        box  = QMessageBox()
        box.setWindowTitle(title)
        box.setText(message)
        box.setIcon(QMessageBox.Critical)
        box.exec()
        return
    except Exception:
        pass
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        except Exception:
            pass
    else:
        sys.stderr.write(f"{title}: {message}\n")


def main() -> int:
    _log("=" * 60)
    _log("MegaV starting up")
    _log(f"Python: {sys.version}")
    _log(f"Executable: {sys.executable}")
    _log(f"Working dir: {os.getcwd()}")
    _log(f"Platform: {sys.platform}")

    # ── Single-instance guard (cross-platform PID lock) ───────────
    if not _acquire_mutex():
        _log("Another instance is running — checking for existing window")
        if IS_WIN:
            for _ in range(6):
                hwnd = _find_megav_window()
                if hwnd:
                    _raise_megav_window(hwnd)
                    _log(f"Raised existing window hwnd={hwnd}")
                    return 0
                time.sleep(0.5)

            old_pid = _read_pid()
            if old_pid and old_pid != os.getpid() and _pid_alive(old_pid):
                _log(f"Zombie MegaV (PID={old_pid}) alive but window-less — killing and relaunching")
                _kill_pid(old_pid)
                _delete_pid()
                time.sleep(1.0)
                import subprocess
                script = os.path.join(_HERE, "run.py")
                subprocess.Popen([sys.executable, script])
                return 0
            if old_pid and old_pid != os.getpid():
                _log(f"Stale PID file (PID={old_pid}) — clearing and relaunching")
                _delete_pid()
                time.sleep(1.0)
                import subprocess
                script = os.path.join(_HERE, "run.py")
                subprocess.Popen([sys.executable, script])
                return 0
        else:
            _log("Another MegaV instance detected — exiting")
            return 0

    _write_pid()
    import atexit
    atexit.register(_delete_pid)

    # ── Check PySide6 ─────────────────────────────────────────────
    try:
        import PySide6  # noqa: F401
    except ImportError:
        show_error(
            "MegaV — Missing Dependencies",
            "PySide6 is not installed.\n\nDouble-click:\n  Install Dependencies.bat\n\nThen launch again."
        )
        return 1

    # ── Launch GUI ────────────────────────────────────────────────
    try:
        _log("Loading GUI…")
        from src.gui.app import main as gui_main
        _log("Launching window…")
        code = gui_main()
        _log(f"App exited (code {code})")
        return code
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        _log(f"FATAL CRASH:\n{tb}")
        show_error("MegaV — Startup Error", f"Failed to start:\n\n{exc}\n\nSee logs/startup.log")
        return 1


if __name__ == "__main__":
    sys.exit(main())
