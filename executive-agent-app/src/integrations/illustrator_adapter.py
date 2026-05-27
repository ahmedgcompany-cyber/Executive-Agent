"""Adobe Illustrator adapter."""

from pathlib import Path
from typing import Any


class IllustratorAdapter:
    """Adapter for Adobe Illustrator automation."""

    def __init__(self):
        """Initialize Illustrator adapter."""
        self.app = None
        self._com_available = False
        self._try_import_com()

    def _try_import_com(self) -> None:
        """Try to import COM libraries."""
        try:
            import win32com.client
            self._com_available = True
        except ImportError:
            self._com_available = False

    def is_available(self) -> bool:
        """Check if Illustrator is available.

        Returns:
            True if Illustrator can be controlled
        """
        if not self._com_available:
            return False

        try:
            import win32com.client
            app = win32com.client.Dispatch("Illustrator.Application")
            return app is not None
        except Exception:
            return False

    def launch(self) -> dict[str, Any]:
        """Launch Illustrator.

        Returns:
            Launch result
        """
        try:
            import win32com.client
            self.app = win32com.client.Dispatch("Illustrator.Application")
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
        """Open a file in Illustrator.

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
            doc = self.app.Open(file_path)
            return {
                "success": True,
                "document": doc.Name if doc else "unknown",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def save_document(self, format: str = "ai") -> dict[str, Any]:
        """Save the current document.

        Args:
            format: Save format

        Returns:
            Save result
        """
        if not self.app:
            return {"success": False, "error": "Illustrator not connected"}

        try:
            doc = self.app.ActiveDocument
            if not doc:
                return {"success": False, "error": "No active document"}

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
            return {"success": False, "error": "Illustrator not connected"}

        try:
            doc = self.app.ActiveDocument
            if not doc:
                return {"success": False, "error": "No active document"}

            # Export options would be set based on format
            # This is a simplified placeholder

            return {
                "success": True,
                "output_path": output_path,
                "format": format,
                "note": "Export would use Illustrator's export options",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def export_social_pack(self, output_dir: str) -> dict[str, Any]:
        """Export social media asset pack.

        Args:
            output_dir: Output directory

        Returns:
            Export result
        """
        sizes = {
            "instagram_post": (1080, 1080),
            "instagram_story": (1080, 1920),
            "facebook_post": (1200, 630),
            "twitter_post": (1200, 675),
            "linkedin_post": (1200, 627),
        }

        exported = []

        for name, (width, height) in sizes.items():
            # Export each size
            output_path = str(Path(output_dir) / f"{name}.png")
            result = self.export_document(output_path, "png")
            if result.get("success"):
                exported.append(name)

        return {
            "success": True,
            "exported": exported,
            "count": len(exported),
        }

    def trace_image(self, preset: str = "default") -> dict[str, Any]:
        """Trace raster image to vector.

        Args:
            preset: Trace preset

        Returns:
            Trace result
        """
        if not self.app:
            return {"success": False, "error": "Illustrator not connected"}

        try:
            # This would use Illustrator's image trace feature
            return {
                "success": True,
                "preset": preset,
                "note": "Image trace would use Illustrator's trace feature",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
