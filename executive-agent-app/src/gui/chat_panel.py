"""Chat panel for the GUI.

PySide6 is required for the real implementation. When unavailable,
a stub class is exported so importers don't crash at module load.
"""

from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout,
        QTextEdit, QLineEdit, QPushButton,
        QLabel, QScrollArea, QFrame,
    )
    from PySide6.QtCore import Qt, Signal
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


if PYSIDE_AVAILABLE:

    class ChatPanel(QWidget):
        """Chat panel widget."""

        message_sent = Signal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._setup_ui()

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 10, 10, 10)

            header = QLabel("Chat")
            header.setStyleSheet("font-size: 16px; font-weight: bold;")
            layout.addWidget(header)

            self.chat_history = QTextEdit()
            self.chat_history.setReadOnly(True)
            self.chat_history.setStyleSheet("""
                QTextEdit {
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 10px;
                }
            """)
            layout.addWidget(self.chat_history)

            input_layout = QHBoxLayout()

            self.message_input = QLineEdit()
            self.message_input.setPlaceholderText("Type your message...")
            self.message_input.returnPressed.connect(self.send_message)
            self.message_input.setStyleSheet("""
                QLineEdit {
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                }
            """)
            input_layout.addWidget(self.message_input)

            self.send_button = QPushButton("Send")
            self.send_button.clicked.connect(self.send_message)
            self.send_button.setStyleSheet("""
                QPushButton {
                    padding: 10px 20px;
                    background-color: #007bff;
                    color: white;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #0056b3;
                }
            """)
            input_layout.addWidget(self.send_button)

            layout.addLayout(input_layout)

        def send_message(self):
            message = self.message_input.text().strip()
            if message:
                self.add_user_message(message)
                self.message_sent.emit(message)
                self.message_input.clear()

        def add_user_message(self, message: str):
            self.chat_history.append(
                f'<div style="margin: 10px 0;">'
                f'<b style="color: #007bff;">You:</b> '
                f'<span style="background-color: #e3f2fd; padding: 5px 10px; border-radius: 10px;">'
                f'{message}</span></div>'
            )

        def add_agent_message(self, message: str, agent_name: str = "Agent"):
            self.chat_history.append(
                f'<div style="margin: 10px 0;">'
                f'<b style="color: #28a745;">{agent_name}:</b> '
                f'<span style="background-color: #e8f5e9; padding: 5px 10px; border-radius: 10px;">'
                f'{message}</span></div>'
            )

        def add_system_message(self, message: str):
            self.chat_history.append(
                f'<div style="margin: 10px 0; color: #6c757d; font-style: italic;">'
                f'{message}</div>'
            )

        def clear_chat(self):
            self.chat_history.clear()

else:

    class ChatPanel:
        """Stub when PySide6 is unavailable."""

        message_sent = None

        def __init__(self, *args, **kwargs):
            pass

        def send_message(self):
            pass

        def add_user_message(self, message: str):
            pass

        def add_agent_message(self, message: str, agent_name: str = "Agent"):
            pass

        def add_system_message(self, message: str):
            pass

        def clear_chat(self):
            pass
