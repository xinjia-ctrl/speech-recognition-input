from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QWidget


DIAGNOSTIC_FIELDS = (
    ("provider", "当前模式"),
    ("language", "识别语言"),
    ("api_key", "HTTP API Key"),
    ("translation_key", "翻译 API Key"),
    ("translation_url", "翻译 API 地址"),
    ("websocket_key", "WebSocket Key"),
    ("websocket_url", "WebSocket 地址"),
    ("state", "当前状态"),
    ("first_text_latency", "首字延迟"),
    ("tail_latency", "停止后收尾"),
    ("total_elapsed", "总耗时"),
    ("last_error", "最近错误"),
)


class DiagnosticsPanel(QWidget):
    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        self.labels: dict[str, QLabel] = {}

        for key, label in DIAGNOSTIC_FIELDS:
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.labels[key] = value_label
            layout.addRow(label, value_label)

        refresh_button = QPushButton("刷新诊断信息")
        refresh_button.clicked.connect(self.refresh_requested)
        layout.addRow(refresh_button)

    def set_values(self, values: Mapping[str, str]) -> None:
        for key, value in values.items():
            if key in self.labels:
                self.labels[key].setText(value)
