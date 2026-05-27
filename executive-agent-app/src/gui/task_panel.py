"""Task panel for the GUI.

PySide6 is required for the real implementation. When unavailable,
a stub class is exported so importers don't crash at module load.
"""

from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout,
        QListWidget, QListWidgetItem, QPushButton,
        QLabel, QProgressBar, QMenu,
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QAction
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


if PYSIDE_AVAILABLE:

    class TaskPanel(QWidget):
        """Task panel widget."""

        task_selected = Signal(str)
        task_cancelled = Signal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.tasks: dict = {}
            self._setup_ui()

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 10, 10, 10)

            header_layout = QHBoxLayout()
            header = QLabel("Active Tasks")
            header.setStyleSheet("font-size: 16px; font-weight: bold;")
            header_layout.addWidget(header)

            clear_btn = QPushButton("Clear Completed")
            clear_btn.clicked.connect(self.clear_completed)
            header_layout.addWidget(clear_btn)

            layout.addLayout(header_layout)

            self.progress_bar = QProgressBar()
            self.progress_bar.setVisible(False)
            layout.addWidget(self.progress_bar)

            self.task_list = QListWidget()
            self.task_list.setContextMenuPolicy(Qt.CustomContextMenu)
            self.task_list.customContextMenuRequested.connect(self.show_context_menu)
            self.task_list.itemClicked.connect(self.on_task_selected)
            layout.addWidget(self.task_list)

        def add_task(self, task_id: str, description: str, status: str = "pending"):
            self.tasks[task_id] = {"description": description, "status": status}
            item = QListWidgetItem(f"[{status.upper()}] {description}")
            item.setData(Qt.UserRole, task_id)
            self._set_item_color(item, status)
            self.task_list.addItem(item)

        def update_task(self, task_id: str, status: str, progress: int | None = None):
            if task_id not in self.tasks:
                return

            self.tasks[task_id]["status"] = status

            for i in range(self.task_list.count()):
                item = self.task_list.item(i)
                if item.data(Qt.UserRole) == task_id:
                    description = self.tasks[task_id]["description"]
                    item.setText(f"[{status.upper()}] {description}")
                    self._set_item_color(item, status)
                    break

            if progress is not None:
                self.set_progress(progress)

        def set_progress(self, value: int):
            """Update progress bar; hide once complete."""
            value = max(0, min(100, int(value)))
            self.progress_bar.setValue(value)
            self.progress_bar.setVisible(value < 100)

        def remove_task(self, task_id: str):
            if task_id in self.tasks:
                del self.tasks[task_id]

            for i in range(self.task_list.count()):
                item = self.task_list.item(i)
                if item.data(Qt.UserRole) == task_id:
                    self.task_list.takeItem(i)
                    break

        def _set_item_color(self, item, status: str):
            colors = {
                "pending": "#ffc107",
                "running": "#007bff",
                "completed": "#28a745",
                "failed": "#dc3545",
                "cancelled": "#6c757d",
            }
            color = colors.get(status, "#000000")
            item.setForeground(color)

        def on_task_selected(self, item):
            task_id = item.data(Qt.UserRole)
            self.task_selected.emit(task_id)

        def show_context_menu(self, position):
            item = self.task_list.itemAt(position)
            if not item:
                return

            menu = QMenu()

            cancel_action = QAction("Cancel Task", self)
            cancel_action.triggered.connect(lambda: self.cancel_task(item))
            menu.addAction(cancel_action)

            remove_action = QAction("Remove", self)
            remove_action.triggered.connect(lambda: self.remove_task_item(item))
            menu.addAction(remove_action)

            menu.exec(self.task_list.mapToGlobal(position))

        def cancel_task(self, item):
            task_id = item.data(Qt.UserRole)
            self.update_task(task_id, "cancelled")
            self.task_cancelled.emit(task_id)

        def remove_task_item(self, item):
            task_id = item.data(Qt.UserRole)
            self.remove_task(task_id)

        def clear_completed(self):
            to_remove = [
                task_id for task_id, task in self.tasks.items()
                if task["status"] in ("completed", "failed", "cancelled")
            ]
            for task_id in to_remove:
                self.remove_task(task_id)

        def clear_all(self):
            self.task_list.clear()
            self.tasks.clear()
            self.progress_bar.setVisible(False)

else:

    class TaskPanel:
        """Stub when PySide6 is unavailable."""

        task_selected = None
        task_cancelled = None

        def __init__(self, *args, **kwargs):
            self.tasks: dict = {}

        def add_task(self, *args, **kwargs):
            pass

        def update_task(self, *args, **kwargs):
            pass

        def set_progress(self, value: int):
            pass

        def remove_task(self, *args, **kwargs):
            pass

        def clear_completed(self):
            pass

        def clear_all(self):
            pass
