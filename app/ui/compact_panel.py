from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget


class CompactInputPanel(QWidget):
    toggle_requested = Signal()
    insert_requested = Signal()
    copy_requested = Signal()
    translate_requested = Signal()
    settings_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("语音输入")
        self.setFixedSize(360, 170)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.preview_edit = QTextEdit()
        self.preview_edit.setObjectName("compactPreview")
        self.preview_edit.setPlaceholderText("识别结果会显示在这里，可编辑后插入。")
        self.preview_edit.setFixedHeight(92)

        button_layout = QHBoxLayout()
        self.toggle_button = QPushButton("开始")
        self.toggle_button.clicked.connect(self.toggle_requested.emit)
        self.insert_button = QPushButton("插入")
        self.insert_button.clicked.connect(self.insert_requested.emit)
        self.copy_button = QPushButton("复制")
        self.copy_button.clicked.connect(self.copy_requested.emit)
        self.translate_button = QPushButton("中翻英")
        self.translate_button.clicked.connect(self.translate_requested.emit)
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.settings_requested.emit)

        button_layout.addWidget(self.toggle_button)
        button_layout.addWidget(self.insert_button)
        button_layout.addWidget(self.copy_button)
        button_layout.addWidget(self.translate_button)
        button_layout.addWidget(self.settings_button)

        layout.addWidget(self.preview_edit)
        layout.addLayout(button_layout)
        self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #ffffff;
                border: 1px solid #cfd7e3;
                border-radius: 8px;
            }
            QTextEdit#compactPreview {
                border: 1px solid #d4dbe6;
                border-radius: 6px;
                padding: 8px;
                font-size: 14px;
                color: #172033;
                background: #f8fafc;
            }
            QPushButton {
                min-height: 28px;
                border-radius: 6px;
                padding: 5px 9px;
                color: #172033;
                background: #edf2f7;
                border: 1px solid #cbd5e1;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
            """
        )

    def set_text(self, text: str) -> None:
        if self.preview_edit.toPlainText() == text:
            return
        self.preview_edit.setPlainText(text)
        self.preview_edit.moveCursor(QTextCursor.MoveOperation.End)

    def text(self) -> str:
        return self.preview_edit.toPlainText()

    def set_recording(self, recording: bool) -> None:
        self.toggle_button.setText("停止" if recording else "开始")

    def set_translation_label(self, label: str) -> None:
        self.translate_button.setText(label)
