"""Desktop automation tools for app and UI control."""

import subprocess
import time
from typing import Any, Optional


class DesktopTools:
    """Desktop application and UI control tools."""

    def __init__(self):
        """Initialize desktop tools."""
        self.active_window: Optional[str] = None
        self._pyautogui = None
        self._pywinauto = None

    def _ensure_pyautogui(self) -> Any:
        """Ensure pyautogui is imported."""
        if self._pyautogui is None:
            try:
                import pyautogui
                pyautogui.FAILSAFE = True
                self._pyautogui = pyautogui
            except ImportError:
                raise ImportError("pyautogui not installed. Run: pip install pyautogui")
        return self._pyautogui

    def _ensure_pywinauto(self) -> Any:
        """Ensure pywinauto is imported."""
        if self._pywinauto is None:
            try:
                from pywinauto import Desktop
                self._pywinauto = Desktop
            except ImportError:
                raise ImportError("pywinauto not installed. Run: pip install pywinauto")
        return self._pywinauto

    # Map friendly names → Windows executables / shell commands
    _APP_ALIASES: dict[str, str] = {
        "notepad":       "notepad.exe",
        "calculator":    "calc.exe",
        "calc":          "calc.exe",
        "paint":         "mspaint.exe",
        "explorer":      "explorer.exe",
        "cmd":           "cmd.exe",
        "command prompt":"cmd.exe",
        "terminal":      "cmd.exe",
        "powershell":    "powershell.exe",
        "task manager":  "taskmgr.exe",
        "taskmgr":       "taskmgr.exe",
        "word":          "winword.exe",
        "winword":       "winword.exe",
        "excel":         "excel.exe",
        "powerpoint":    "powerpnt.exe",
        "outlook":       "outlook.exe",
        "chrome":        "chrome.exe",
        "google chrome": "chrome.exe",
        "firefox":       "firefox.exe",
        "edge":          "msedge.exe",
        "microsoft edge":"msedge.exe",
        "vlc":           "vlc.exe",
        "spotify":       "spotify.exe",
        "vscode":        "code.exe",
        "vs code":       "code.exe",
        "visual studio code": "code.exe",
        "blender":       "blender.exe",
        "photoshop":     "photoshop.exe",
        "illustrator":   "illustrator.exe",
        "discord":       "discord.exe",
        "slack":         "slack.exe",
        "zoom":          "zoom.exe",
        "teams":         "teams.exe",
        "microsoft teams": "teams.exe",
        "snipping tool": "SnippingTool.exe",
        "snip":          "SnippingTool.exe",
        "settings":      "ms-settings:",
        "control panel": "control.exe",
        "device manager":"devmgmt.msc",
        "regedit":       "regedit.exe",
    }

    def launch_application(self, app_name: str, args: Optional[list[str]] = None) -> dict[str, Any]:
        """Launch an application by name, alias, or executable path.

        Args:
            app_name: Application name, alias, or executable
            args: Optional command line arguments

        Returns:
            Launch result
        """
        import shutil

        # Resolve alias
        resolved = self._APP_ALIASES.get(app_name.lower().strip(), app_name)

        # Special: ms-settings: URI → use start command
        if resolved.startswith("ms-") or resolved.endswith(".msc"):
            try:
                subprocess.Popen(["start", "", resolved], shell=True)
                time.sleep(1)
                return {"success": True, "app": resolved, "pid": None,
                        "summary": f"Launched '{app_name}' via Windows shell."}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # Build command — do NOT capture stdout/stderr (breaks GUI apps)
        cmd = [resolved] + (args or [])

        # Try direct launch first
        try:
            process = subprocess.Popen(
                cmd,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            time.sleep(1.5)
            return {
                "success": True,
                "app": resolved,
                "pid": process.pid,
                "summary": f"Launched '{app_name}' (pid {process.pid}).",
            }
        except FileNotFoundError:
            pass
        except Exception as e:
            return {"success": False, "error": str(e)}

        # Try Windows START shell command as fallback (finds apps in PATH + registry)
        try:
            full_cmd = " ".join([resolved] + (args or []))
            subprocess.Popen(f'start "" {full_cmd}', shell=True)
            time.sleep(1.5)
            return {
                "success": True,
                "app": resolved,
                "pid": None,
                "summary": f"Launched '{app_name}' via Windows shell.",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Could not launch '{app_name}': {e}. "
                         f"Make sure the application is installed.",
            }

    def list_windows(self) -> dict[str, Any]:
        """List all visible windows.

        Returns:
            List of windows
        """
        try:
            Desktop = self._ensure_pywinauto()
            desktop = Desktop(backend="uia")

            windows = []
            for window in desktop.windows():
                try:
                    title = window.window_text()
                    if title:
                        windows.append({
                            "title": title,
                            "handle": window.handle,
                            "rectangle": window.rectangle().__dict__ if window.rectangle() else None,
                            "is_visible": window.is_visible(),
                            "is_enabled": window.is_enabled(),
                        })
                except Exception:
                    continue

            return {"success": True, "windows": windows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def focus_window(self, title: str) -> dict[str, Any]:
        """Focus a window by title.

        Args:
            title: Window title (partial match)

        Returns:
            Focus result
        """
        try:
            Desktop = self._ensure_pywinauto()
            desktop = Desktop(backend="uia")

            for window in desktop.windows():
                try:
                    if title.lower() in window.window_text().lower():
                        window.set_focus()
                        self.active_window = window.window_text()
                        return {
                            "success": True,
                            "title": window.window_text(),
                            "handle": window.handle,
                        }
                except Exception:
                    continue

            return {"success": False, "error": f"Window not found: {title}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_controls(self, window_title: Optional[str] = None) -> dict[str, Any]:
        """List controls in the active or specified window.

        Args:
            window_title: Optional window title to inspect

        Returns:
            List of controls
        """
        try:
            Desktop = self._ensure_pywinauto()
            desktop = Desktop(backend="uia")

            target_window = None
            search_title = window_title or self.active_window

            for window in desktop.windows():
                try:
                    if search_title and search_title.lower() in window.window_text().lower():
                        target_window = window
                        break
                except Exception:
                    continue

            if not target_window:
                return {"success": False, "error": "Window not found"}

            controls = []
            for control in target_window.descendants():
                try:
                    controls.append({
                        "control_type": control.element_info.control_type,
                        "name": control.element_info.name,
                        "automation_id": control.element_info.automation_id,
                        "class_name": control.element_info.class_name,
                        "rectangle": control.rectangle().__dict__ if control.rectangle() else None,
                    })
                except Exception:
                    continue

            return {"success": True, "controls": controls}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def click_control(self, name: Optional[str] = None, automation_id: Optional[str] = None) -> dict[str, Any]:
        """Click a control by name or automation ID.

        Args:
            name: Control name
            automation_id: Control automation ID

        Returns:
            Click result
        """
        try:
            Desktop = self._ensure_pywinauto()
            desktop = Desktop(backend="uia")

            for window in desktop.windows():
                try:
                    if self.active_window and self.active_window.lower() not in window.window_text().lower():
                        continue

                    for control in window.descendants():
                        try:
                            if name and name in control.element_info.name:
                                control.click()
                                return {"success": True, "control": name}
                            if automation_id and automation_id == control.element_info.automation_id:
                                control.click()
                                return {"success": True, "automation_id": automation_id}
                        except Exception:
                            continue
                except Exception:
                    continue

            return {"success": False, "error": "Control not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def type_into_control(
        self,
        text: str,
        name: Optional[str] = None,
        automation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Type text into a control.

        Args:
            text: Text to type
            name: Control name
            automation_id: Control automation ID

        Returns:
            Type result
        """
        try:
            Desktop = self._ensure_pywinauto()
            desktop = Desktop(backend="uia")

            for window in desktop.windows():
                try:
                    if self.active_window and self.active_window.lower() not in window.window_text().lower():
                        continue

                    for control in window.descendants():
                        try:
                            if (name and name in control.element_info.name) or \
                               (automation_id and automation_id == control.element_info.automation_id):
                                control.type_keys(text, with_spaces=True)
                                return {"success": True, "text": text}
                        except Exception:
                            continue
                except Exception:
                    continue

            return {"success": False, "error": "Control not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_hotkey(self, keys: list[str]) -> dict[str, Any]:
        """Send keyboard hotkey combination.

        Args:
            keys: List of keys to press together

        Returns:
            Hotkey result
        """
        try:
            pyautogui = self._ensure_pyautogui()
            pyautogui.hotkey(*keys)
            return {"success": True, "keys": keys}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_keys(self, text: str) -> dict[str, Any]:
        """Send keystrokes.

        Args:
            text: Text to type

        Returns:
            Type result
        """
        try:
            pyautogui = self._ensure_pyautogui()
            pyautogui.typewrite(text, interval=0.01)
            return {"success": True, "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def capture_window(self, output_path: Optional[str] = None) -> dict[str, Any]:
        """Capture screenshot of active window.

        Args:
            output_path: Optional path to save screenshot

        Returns:
            Screenshot result
        """
        try:
            pyautogui = self._ensure_pyautogui()

            if output_path is None:
                output_path = f"window_capture_{int(time.time())}.png"

            screenshot = pyautogui.screenshot()
            screenshot.save(output_path)

            return {"success": True, "path": output_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def capture_screen_region(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        output_path: Optional[str] = None,
    ) -> dict[str, Any]:
        """Capture a region of the screen.

        Args:
            left: Left coordinate
            top: Top coordinate
            width: Region width
            height: Region height
            output_path: Optional path to save screenshot

        Returns:
            Screenshot result
        """
        try:
            pyautogui = self._ensure_pyautogui()

            if output_path is None:
                output_path = f"region_capture_{int(time.time())}.png"

            screenshot = pyautogui.screenshot(region=(left, top, width, height))
            screenshot.save(output_path)

            return {"success": True, "path": output_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_window_title(self) -> dict[str, Any]:
        """Get the title of the active window.

        Returns:
            Window title
        """
        try:
            import win32gui
            window = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(window)
            return {"success": True, "title": title}
        except ImportError:
            return {"success": False, "error": "win32gui not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def minimize_window(self, title: Optional[str] = None) -> dict[str, Any]:
        """Minimize a window.

        Args:
            title: Optional window title (uses active if not specified)

        Returns:
            Minimize result
        """
        try:
            Desktop = self._ensure_pywinauto()
            desktop = Desktop(backend="uia")

            search_title = title or self.active_window

            for window in desktop.windows():
                try:
                    if search_title and search_title.lower() in window.window_text().lower():
                        window.minimize()
                        return {"success": True, "title": window.window_text()}
                except Exception:
                    continue

            return {"success": False, "error": "Window not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def maximize_window(self, title: Optional[str] = None) -> dict[str, Any]:
        """Maximize a window.

        Args:
            title: Optional window title (uses active if not specified)

        Returns:
            Maximize result
        """
        try:
            Desktop = self._ensure_pywinauto()
            desktop = Desktop(backend="uia")

            search_title = title or self.active_window

            for window in desktop.windows():
                try:
                    if search_title and search_title.lower() in window.window_text().lower():
                        window.maximize()
                        return {"success": True, "title": window.window_text()}
                except Exception:
                    continue

            return {"success": False, "error": "Window not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
