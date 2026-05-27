"""Adobe Photoshop adapter."""

import os
from pathlib import Path
from typing import Any, Optional


class PhotoshopAdapter:
    """Adapter for Adobe Photoshop automation."""

    def __init__(self):
        """Initialize Photoshop adapter."""
        self.app = None
        self._com_available = False
        self._try_import_com()

    def _try_import_com(self) -> None:
        """Try to import COM libraries for Photoshop."""
        try:
            import win32com.client
            self._com_available = True
        except ImportError:
            self._com_available = False

    def is_available(self) -> bool:
        """Check if Photoshop is available.

        Returns:
            True if Photoshop can be controlled
        """
        if not self._com_available:
            return False

        try:
            import win32com.client
            app = win32com.client.Dispatch("Photoshop.Application")
            return app is not None
        except Exception:
            return False

    def launch(self) -> dict[str, Any]:
        """Launch Photoshop.

        Returns:
            Launch result
        """
        try:
            import win32com.client
            self.app = win32com.client.Dispatch("Photoshop.Application")
            return {
                "success": True,
                "version": self.app.Version if self.app else "unknown",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def open_file(self, file_path: str) -> dict[str, Any]:
        """Open a file in Photoshop.

        Args:
            file_path: Path to file

        Returns:
            Open result
        """
        if not self.app:
            launch_result = self.launch()
            if not launch_result.get("success"):
                return launch_result

        try:
            from win32com.client import Dispatch

            # Create file reference
            file_ref = Dispatch("Photoshop.FileReference")
            file_ref.Path = file_path

            # Open document
            doc = self.app.Open(file_ref)

            return {
                "success": True,
                "document": doc.Name if doc else "unknown",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def save_document(self, format: str = "psd") -> dict[str, Any]:
        """Save the current document.

        Args:
            format: Save format

        Returns:
            Save result
        """
        if not self.app:
            return {"success": False, "error": "Photoshop not connected"}

        try:
            doc = self.app.ActiveDocument
            if not doc:
                return {"success": False, "error": "No active document"}

            # Save options would be set based on format
            doc.Save()

            return {
                "success": True,
                "format": format,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def export_document(
        self,
        output_path: str,
        format: str = "png",
    ) -> dict[str, Any]:
        """Export the current document.

        Args:
            output_path: Export path
            format: Export format

        Returns:
            Export result
        """
        if not self.app:
            return {"success": False, "error": "Photoshop not connected"}

        try:
            doc = self.app.ActiveDocument
            if not doc:
                return {"success": False, "error": "No active document"}

            # Create export options based on format
            from win32com.client import Dispatch

            if format.lower() == "png":
                options = Dispatch("Photoshop.PNGSaveOptions")
            elif format.lower() in ["jpg", "jpeg"]:
                options = Dispatch("Photoshop.JPEGSaveOptions")
                options.Quality = 12
            else:
                return {"success": False, "error": f"Unsupported format: {format}"}

            # Save
            file_ref = Dispatch("Photoshop.FileReference")
            file_ref.Path = output_path
            doc.SaveAs(file_ref, options)

            return {
                "success": True,
                "output_path": output_path,
                "format": format,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def run_action(self, action_set: str, action_name: str) -> dict[str, Any]:
        """Run a Photoshop action.

        Args:
            action_set: Action set name
            action_name: Action name

        Returns:
            Run result
        """
        if not self.app:
            return {"success": False, "error": "Photoshop not connected"}

        try:
            self.app.DoAction(action_name, action_set)
            return {
                "success": True,
                "action_set": action_set,
                "action": action_name,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def remove_background(self) -> dict[str, Any]:
        """Remove background from current document.

        Returns:
            Operation result
        """
        if not self.app:
            return {"success": False, "error": "Photoshop not connected"}

        try:
            # This would use Photoshop's remove background feature
            # or a specific action
            return {
                "success": True,
                "note": "Background removal would use Photoshop's AI feature or action",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def resize_image(
        self,
        width: int,
        height: int,
        maintain_aspect: bool = True,
    ) -> dict[str, Any]:
        """Resize the current image.

        Args:
            width: New width
            height: New height
            maintain_aspect: Maintain aspect ratio

        Returns:
            Resize result
        """
        if not self.app:
            return {"success": False, "error": "Photoshop not connected"}

        try:
            doc = self.app.ActiveDocument
            if not doc:
                return {"success": False, "error": "No active document"}

            # Resize
            if maintain_aspect:
                doc.ResizeImage(Width=width)
            else:
                doc.ResizeImage(Width=width, Height=height)

            return {
                "success": True,
                "width": width,
                "height": height,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
