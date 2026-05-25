from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import Settings
from app.ui.config_check_panel import ConfigCheckPanel
from app.ui.diagnostics_panel import DiagnosticsPanel
from app.ui.settings_panel import SettingsPanel


class MainPanel(QWidget):
    record_requested = Signal()
    tidy_requested = Signal()
    copy_requested = Signal()
    paste_requested = Signal()
    history_item_selected = Signal(str)
    save_settings_requested = Signal()
    refresh_config_checks_requested = Signal()
    refresh_diagnostics_requested = Signal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._build(settings)

    def _build(self, settings: Settings) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        input_page = self._build_input_page()
        history_page = self._build_history_page()

        self.settings_panel = SettingsPanel(settings)
        self.settings_panel.save_requested.connect(self.save_settings_requested)
        self.config_check_panel = ConfigCheckPanel()
        self.config_check_panel.refresh_requested.connect(self.refresh_config_checks_requested)
        self.diagnostics_panel = DiagnosticsPanel()
        self.diagnostics_panel.refresh_requested.connect(self.refresh_diagnostics_requested)

        tabs = QTabWidget()
        tabs.setObjectName("mainTabs")
        tabs.setDocumentMode(True)
        tabs.addTab(input_page, "输入")
        tabs.addTab(history_page, "历史")
        tabs.addTab(self.settings_panel, "设置")
        tabs.addTab(self.config_check_panel, "检查")
        tabs.addTab(self.diagnostics_panel, "诊断")
        layout.addWidget(tabs)

    def _build_input_page(self) -> QWidget:
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        self.mode_badge = QLabel()
        self.mode_badge.setObjectName("badge")
        self.language_badge = QLabel()
        self.language_badge.setObjectName("badge")
        self.connection_badge = QLabel("待机")
        self.connection_badge.setObjectName("badge")
        self.feedback_label = QLabel()
        self.feedback_label.setObjectName("feedbackLabel")
        self.feedback_label.setVisible(False)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(8)

        badge_layout = QHBoxLayout()
        badge_layout.setSpacing(8)
        badge_layout.addWidget(self.mode_badge)
        badge_layout.addWidget(self.language_badge)
        badge_layout.addWidget(self.connection_badge)
        badge_layout.addStretch()
        header_layout.addLayout(badge_layout)
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.feedback_label)

        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("resultEdit")
        self.text_edit.setPlaceholderText("识别结果会显示在这里，也可以手动编辑后复制或插入。")

        self.record_button = QPushButton("开始说话")
        self.record_button.setObjectName("primaryButton")
        self.record_button.setToolTip("开始/停止录音")
        self.record_button.clicked.connect(self.record_requested)
        self.tidy_button = QPushButton("整理文本")
        self.tidy_button.setObjectName("secondaryButton")
        self.tidy_button.clicked.connect(self.tidy_requested)
        self.copy_button = QPushButton("复制")
        self.copy_button.setObjectName("secondaryButton")
        self.copy_button.clicked.connect(self.copy_requested)
        self.paste_button = QPushButton("插入")
        self.paste_button.setObjectName("accentButton")
        self.paste_button.clicked.connect(self.paste_requested)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.record_button)
        button_layout.addWidget(self.tidy_button)
        button_layout.addWidget(self.copy_button)
        button_layout.addWidget(self.paste_button)

        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(12)
        page_layout.addWidget(header)
        page_layout.addWidget(self.text_edit)
        page_layout.addLayout(button_layout)
        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(lambda item: self.history_item_selected.emit(item.text()))
        layout.addWidget(self.history_list)
        return page

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_feedback(self, text: str, is_error: bool = False) -> None:
        self.feedback_label.setText(text)
        self.feedback_label.setVisible(bool(text))
        if is_error:
            self.feedback_label.setStyleSheet("color: #991b1b; background: #fef2f2; border: 1px solid #fecaca;")
        else:
            self.feedback_label.setStyleSheet("")

    def set_recording(self, recording: bool) -> None:
        if recording:
            self.record_button.setText("停止录音")
            self.record_button.setObjectName("recordingButton")
        else:
            self.record_button.setText("开始说话")
            self.record_button.setObjectName("primaryButton")
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)

    def set_result_text(self, text: str) -> None:
        self.text_edit.setPlainText(text)
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

    def current_result_text(self) -> str:
        return self.text_edit.toPlainText()

    def set_actions_enabled(self, enabled: bool) -> None:
        self.tidy_button.setEnabled(enabled)
        self.copy_button.setEnabled(enabled)
        self.paste_button.setEnabled(enabled)

    def set_badges(self, mode: str, language: str) -> None:
        self.mode_badge.setText(f"模式：{mode}")
        self.language_badge.setText(f"语言：{language}")

    def set_connection_state(self, text: str) -> None:
        self.connection_badge.setText(text)

    def connection_state(self) -> str:
        return self.connection_badge.text()

    def set_history_items(self, items: Iterable[str]) -> None:
        self.history_list.clear()
        for text in items:
            self.history_list.addItem(text)
