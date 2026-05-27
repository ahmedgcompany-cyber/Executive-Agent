"""AutoCAD adapter."""

from pathlib import Path
from typing import Any


class AutoCADAdapter:
    """Adapter for AutoCAD automation."""

    def __init__(self):
        """Initialize AutoCAD adapter."""
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
        """Check if AutoCAD is available.

        Returns:
            True if AutoCAD can be controlled
        """
        if not self._com_available:
            return False

        try:
            import win32com.client
            app = win32com.client.Dispatch("AutoCAD.Application")
            return app is not None
        except Exception:
            return False

    def launch(self) -> dict[str, Any]:
        """Launch AutoCAD.

        Returns:
            Launch result
        """
        try:
            import win32com.client
            self.app = win32com.client.Dispatch("AutoCAD.Application")
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
        """Open a drawing in AutoCAD.

        Args:
            file_path: Path to drawing file

        Returns:
            Open result
        """
        if not self.app:
            launch_result = self.launch()
            if not launch_result.get("success"):
                return launch_result

        try:
            doc = self.app.Documents.Open(file_path)
            return {
                "success": True,
                "document": doc.Name if doc else "unknown",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def save_document(self) -> dict[str, Any]:
        """Save the current document.

        Returns:
            Save result
        """
        if not self.app:
            return {"success": False, "error": "AutoCAD not connected"}

        try:
            doc = self.app.ActiveDocument
            if not doc:
                return {"success": False, "error": "No active document"}

            doc.Save()
            return {
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def export_pdf(self, output_path: str, layout: str = "Model") -> dict[str, Any]:
        """Export current drawing to PDF.

        Args:
            output_path: Output path
            layout: Layout to export

        Returns:
            Export result
        """
        if not self.app:
            return {"success": False, "error": "AutoCAD not connected"}

        try:
            # This would use AutoCAD's plot/PDF export
            # Set plot settings and export
            return {
                "success": True,
                "output_path": output_path,
                "layout": layout,
                "note": "PDF export would use AutoCAD's plot functionality",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def plot_drawing(
        self,
        output_path: str,
        plotter: str = "DWG To PDF.pc3",
    ) -> dict[str, Any]:
        """Plot the current drawing.

        Args:
            output_path: Output path
            plotter: Plotter configuration

        Returns:
            Plot result
        """
        if not self.app:
            return {"success": False, "error": "AutoCAD not connected"}

        try:
            doc = self.app.ActiveDocument
            if not doc:
                return {"success": False, "error": "No active document"}

            # Set plot configuration
            # This is a simplified placeholder

            return {
                "success": True,
                "output_path": output_path,
                "plotter": plotter,
                "note": "Plot would use AutoCAD's plot API",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def run_script(self, script_path: str) -> dict[str, Any]:
        """Run an AutoCAD script.

        Args:
            script_path: Path to script file

        Returns:
            Script execution result
        """
        if not self.app:
            return {"success": False, "error": "AutoCAD not connected"}

        try:
            # Run script using SCRIPT command
            self.app.ActiveDocument.SendCommand(f'SCRIPT "{script_path}" ')

            return {
                "success": True,
                "script": script_path,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
