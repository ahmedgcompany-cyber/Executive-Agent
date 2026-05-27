"""Microsoft Office adapter."""

from pathlib import Path
from typing import Any


class OfficeAdapter:
    """Adapter for Microsoft Office automation."""

    def __init__(self):
        """Initialize Office adapter."""
        self._com_available = False
        self._try_import_com()

    def _try_import_com(self) -> None:
        """Try to import COM libraries."""
        try:
            import win32com.client
            self._com_available = True
        except ImportError:
            self._com_available = False

    def is_word_available(self) -> bool:
        """Check if Word is available."""
        if not self._com_available:
            return False
        try:
            import win32com.client
            app = win32com.client.Dispatch("Word.Application")
            return app is not None
        except Exception:
            return False

    def is_excel_available(self) -> bool:
        """Check if Excel is available."""
        if not self._com_available:
            return False
        try:
            import win32com.client
            app = win32com.client.Dispatch("Excel.Application")
            return app is not None
        except Exception:
            return False

    def is_powerpoint_available(self) -> bool:
        """Check if PowerPoint is available."""
        if not self._com_available:
            return False
        try:
            import win32com.client
            app = win32com.client.Dispatch("PowerPoint.Application")
            return app is not None
        except Exception:
            return False

    def open_word_document(self, file_path: str) -> dict[str, Any]:
        """Open a Word document.

        Args:
            file_path: Path to document

        Returns:
            Open result
        """
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = True
            doc = word.Documents.Open(file_path)

            return {
                "success": True,
                "document": doc.Name,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def save_word_document(self, output_path: Optional[str] = None) -> dict[str, Any]:
        """Save the active Word document.

        Args:
            output_path: Optional output path

        Returns:
            Save result
        """
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            doc = word.ActiveDocument

            if output_path:
                doc.SaveAs(output_path)
            else:
                doc.Save()

            return {
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def export_word_to_pdf(self, output_path: str) -> dict[str, Any]:
        """Export Word document to PDF.

        Args:
            output_path: Output PDF path

        Returns:
            Export result
        """
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            doc = word.ActiveDocument

            # Export as PDF (format 17)
            doc.SaveAs(output_path, FileFormat=17)

            return {
                "success": True,
                "output_path": output_path,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def open_excel_workbook(self, file_path: str) -> dict[str, Any]:
        """Open an Excel workbook.

        Args:
            file_path: Path to workbook

        Returns:
            Open result
        """
        try:
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = True
            wb = excel.Workbooks.Open(file_path)

            return {
                "success": True,
                "workbook": wb.Name,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def create_excel_chart(
        self,
        data_range: str,
        chart_type: str = "xlColumnClustered",
    ) -> dict[str, Any]:
        """Create a chart in Excel.

        Args:
            data_range: Data range
            chart_type: Chart type

        Returns:
            Chart creation result
        """
        try:
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            sheet = excel.ActiveSheet

            # Create chart
            chart = sheet.Shapes.AddChart2(-1, getattr(excel.constants, chart_type, 51))
            chart.Chart.SetSourceData(sheet.Range(data_range))

            return {
                "success": True,
                "chart_type": chart_type,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def export_excel_to_pdf(self, output_path: str) -> dict[str, Any]:
        """Export Excel workbook to PDF.

        Args:
            output_path: Output PDF path

        Returns:
            Export result
        """
        try:
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            wb = excel.ActiveWorkbook

            # Export as PDF
            wb.ExportAsFixedFormat(0, output_path)

            return {
                "success": True,
                "output_path": output_path,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def open_powerpoint_presentation(self, file_path: str) -> dict[str, Any]:
        """Open a PowerPoint presentation.

        Args:
            file_path: Path to presentation

        Returns:
            Open result
        """
        try:
            import win32com.client
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            ppt.Visible = True
            presentation = ppt.Presentations.Open(file_path)

            return {
                "success": True,
                "presentation": presentation.Name,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def export_powerpoint_to_pdf(self, output_path: str) -> dict[str, Any]:
        """Export PowerPoint to PDF.

        Args:
            output_path: Output PDF path

        Returns:
            Export result
        """
        try:
            import win32com.client
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            presentation = ppt.ActivePresentation

            # Export as PDF (format 32)
            presentation.SaveAs(output_path, 32)

            return {
                "success": True,
                "output_path": output_path,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def start_presentation(self) -> dict[str, Any]:
        """Start slideshow from current presentation.

        Returns:
            Start result
        """
        try:
            import win32com.client
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            presentation = ppt.ActivePresentation

            # Start slideshow
            presentation.SlideShowSettings.Run()

            return {
                "success": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
