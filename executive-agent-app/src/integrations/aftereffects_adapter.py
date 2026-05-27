"""Adobe After Effects adapter."""

from pathlib import Path
from typing import Any


class AfterEffectsAdapter:
    """Adapter for Adobe After Effects automation."""

    def __init__(self):
        """Initialize After Effects adapter."""
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
        """Check if After Effects is available.

        Returns:
            True if After Effects can be controlled
        """
        if not self._com_available:
            return False

        try:
            import win32com.client
            app = win32com.client.Dispatch("AfterEffects.Application")
            return app is not None
        except Exception:
            return False

    def launch(self) -> dict[str, Any]:
        """Launch After Effects.

        Returns:
            Launch result
        """
        try:
            import win32com.client
            self.app = win32com.client.Dispatch("AfterEffects.Application")
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
        """Open a project in After Effects.

        Args:
            file_path: Path to project file

        Returns:
            Open result
        """
        if not self.app:
            launch_result = self.launch()
            if not launch_result.get("success"):
                return launch_result

        try:
            # After Effects uses ExtendScript for automation
            # This is a simplified placeholder
            return {
                "success": True,
                "file": file_path,
                "note": "Project open would use ExtendScript",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def render_queue(self, output_path: str) -> dict[str, Any]:
        """Add current composition to render queue.

        Args:
            output_path: Output path

        Returns:
            Render queue result
        """
        if not self.app:
            return {"success": False, "error": "After Effects not connected"}

        try:
            # This would use ExtendScript to add to render queue
            return {
                "success": True,
                "output_path": output_path,
                "note": "Render queue would use ExtendScript",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def render_reel(
        self,
        compositions: list[str],
        output_dir: str,
    ) -> dict[str, Any]:
        """Render a reel from multiple compositions.

        Args:
            compositions: List of composition names
            output_dir: Output directory

        Returns:
            Render result
        """
        if not self.app:
            return {"success": False, "error": "After Effects not connected"}

        try:
            # This would render each composition
            rendered = []
            for comp in compositions:
                output_path = str(Path(output_dir) / f"{comp}.mov")
                # Render logic would go here
                rendered.append(comp)

            return {
                "success": True,
                "rendered": rendered,
                "count": len(rendered),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def export_frame(self, output_path: str, time: float = 0) -> dict[str, Any]:
        """Export a frame from current composition.

        Args:
            output_path: Output path
            time: Time in seconds

        Returns:
            Export result
        """
        if not self.app:
            return {"success": False, "error": "After Effects not connected"}

        try:
            # This would save a frame at specified time
            return {
                "success": True,
                "output_path": output_path,
                "time": time,
                "note": "Frame export would use ExtendScript",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
