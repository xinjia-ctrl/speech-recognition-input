from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.config_check import ConfigCheckItem


class ConfigCheckPanel(QScrollArea):
    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.rows: dict[str, tuple[QFrame, QLabel, QLabel, QLabel]] = {}

        page = QWidget()
        page.setObjectName("configCheckPage")
        self.setWidget(page)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title = QLabel("配置检查")
        title.setObjectName("checkPageTitle")
        refresh_button = QPushButton("刷新检查")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(refresh_button)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("checkSummaryLabel")
        self.summary_label.setWordWrap(True)

        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(8)

        layout.addLayout(header_layout)
        layout.addWidget(self.summary_label)
        layout.addLayout(self.items_layout)
        layout.addStretch()

    def set_items(self, items: list[ConfigCheckItem]) -> None:
        existing_keys = set(self.rows)
        incoming_keys = {item.key for item in items}
        for key in existing_keys - incoming_keys:
            frame, *_labels = self.rows.pop(key)
            frame.setParent(None)

        for item in items:
            if item.key not in self.rows:
                self.rows[item.key] = self._create_row()
            frame, status_label, title_label, detail_label = self.rows[item.key]
            frame.setProperty("status", item.status)
            frame.style().unpolish(frame)
            frame.style().polish(frame)
            status_label.setText(self._status_text(item.status))
            title_label.setText(f"{item.title}：{item.message}")
            detail_label.setText(item.detail)
            detail_label.setVisible(bool(item.detail))

        self.summary_label.setText(self._summary_text(items))

    def _create_row(self) -> tuple[QFrame, QLabel, QLabel, QLabel]:
        frame = QFrame()
        frame.setObjectName("configCheckItem")
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(12, 10, 12, 10)
        frame_layout.setSpacing(10)

        status_label = QLabel("")
        status_label.setObjectName("checkStatusLabel")
        status_label.setFixedWidth(48)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        title_label = QLabel("")
        title_label.setObjectName("checkTitleLabel")
        detail_label = QLabel("")
        detail_label.setObjectName("checkDetailLabel")
        detail_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(detail_label)

        frame_layout.addWidget(status_label)
        frame_layout.addLayout(text_layout, 1)
        self.items_layout.addWidget(frame)
        return frame, status_label, title_label, detail_label

    @staticmethod
    def _status_text(status: str) -> str:
        if status == "ok":
            return "通过"
        if status == "error":
            return "错误"
        return "提醒"

    @staticmethod
    def _summary_text(items: list[ConfigCheckItem]) -> str:
        error_count = sum(1 for item in items if item.status == "error")
        warning_count = sum(1 for item in items if item.status == "warning")
        if error_count:
            return f"发现 {error_count} 个阻塞问题、{warning_count} 个提醒。建议先修复错误项再录音。"
        if warning_count:
            return f"核心功能可继续使用，另有 {warning_count} 个配置提醒可按需完善。"
        return "所有关键配置看起来都正常，可以开始使用。"
