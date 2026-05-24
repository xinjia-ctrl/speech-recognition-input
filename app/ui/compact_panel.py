from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QTextEdit, QVBoxLayout, QWidget


class CompactInputPanel(QWidget):
    toggle_requested = Signal()
    insert_requested = Signal()
    copy_requested = Signal()
    translate_requested = Signal()
    settings_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("语音输入")
        self.setFixedSize(330, 132)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        self.preview_edit = QTextEdit()
        self.preview_edit.setObjectName("compactPreview")
        self.preview_edit.setPlaceholderText("识别结果会显示在这里，可编辑后插入。")
        self.preview_edit.setFixedHeight(74)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)
        self.toggle_button = self._create_icon_button("开始", "开始/停止录音")
        self.toggle_button.clicked.connect(self.toggle_requested.emit)
        self.insert_button = self._create_icon_button("插入", "插入到当前窗口")
        self.insert_button.clicked.connect(self.insert_requested.emit)
        self.copy_button = self._create_icon_button("复制", "复制到剪贴板")
        self.copy_button.clicked.connect(self.copy_requested.emit)
        self.translate_button = self._create_icon_button("中翻英", "翻译当前文本")
        self.translate_button.clicked.connect(self.translate_requested.emit)
        self.settings_button = self._create_icon_button("设置", "打开设置")
        self.settings_button.clicked.connect(self.settings_requested.emit)

        button_layout.addWidget(self.toggle_button)
        button_layout.addWidget(self.insert_button)
        button_layout.addWidget(self.copy_button)
        button_layout.addWidget(self.translate_button)
        button_layout.addWidget(self.settings_button)

        layout.addWidget(self.preview_edit)
        layout.addLayout(button_layout)
        self._apply_styles()

    @staticmethod
    def _create_icon_button(text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tooltip)
        button.setFixedSize(56, 24)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return button

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
                min-height: 22px;
                border-radius: 5px;
                padding: 2px 4px;
                color: #172033;
                background: #edf2f7;
                border: 1px solid #cbd5e1;
                font-size: 13px;
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
        self.translate_button.setToolTip(label)
        self.translate_button.setText(label)
