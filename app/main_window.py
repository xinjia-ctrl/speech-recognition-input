from __future__ import annotations

import time

from PySide6.QtCore import QPoint, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QPainter, QPen, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.asr import (
    AsrEngine,
    RealtimeAsrConfig,
    TranscriptionResult,
    WebSocketRealtimeAsrClient,
)
from app.audio import Recorder, RecordingError
from app.config import Settings, SettingsStore
from app.history import HistoryStore
from app.input import GlobalHotkey, InputInjector
from app.text_postprocess import postprocess_text
from app.text_tools import redact_secret, tidy_text


class TranscribeWorker(QThread):
    partial = Signal(str)
    finished = Signal(object)

    def __init__(self, engine: AsrEngine, audio_path: str) -> None:
        super().__init__()
        self.engine = engine
        self.audio_path = audio_path

    def run(self) -> None:
        self.finished.emit(self.engine.transcribe(self.audio_path, on_partial=self.partial.emit))


class RealtimeWebSocketWorker(QThread):
    partial = Signal(str)
    final = Signal(str)
    error = Signal(str)
    level = Signal(float)

    def __init__(self, config: RealtimeAsrConfig) -> None:
        super().__init__()
        self.client = WebSocketRealtimeAsrClient(config)

    def run(self) -> None:
        self.client.run(
            on_partial=self.partial.emit,
            on_final=self.final.emit,
            on_error=self.error.emit,
            on_level=self.level.emit,
        )

    def stop(self) -> None:
        self.client.stop()


class FloatingVoiceBall(QWidget):
    toggle_requested = Signal()
    panel_requested = Signal()
    insert_requested = Signal()
    quit_requested = Signal()
    moved = Signal()
    COLORS = {
        "idle": "#AAAAAA",
        "listening": "#FF4136",
        "processing": "#FF851B",
        "error": "#FFDC00",
        "success": "#2ECC40",
    }

    def __init__(self) -> None:
        super().__init__()
        self._drag_start: QPoint | None = None
        self._dragging = False
        self._state = "idle"
        self._level = 0.0
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.toggle_requested.emit)
        self.setWindowTitle("语音输入器")
        self.setFixedSize(92, 92)
        self.setToolTip("单击开始/停止录音，拖动移动，右键打开菜单")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("floatingVoiceBall")
        self._build_ui()
        self.set_state("idle", "待机", "点击开始语音输入")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        self.state_label = QLabel("待机")
        self.state_label.setObjectName("ballStateLabel")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.state_label)
        self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QLabel#ballStateLabel {
                color: #111827;
                font-size: 15px;
                font-weight: 700;
            }
            """
        )

    def set_state(
        self,
        state: str,
        title: str,
        preview: str,
        can_insert: bool = False,
    ) -> None:
        self._state = state
        self.state_label.setText(title)
        self.update()

    def set_audio_level(self, level: float) -> None:
        self._level = min(max(level, 0.0), 1.0)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(self.COLORS.get(self._state, self.COLORS["idle"])))
        painter.setPen(QPen(QColor("#111827"), 4))
        rect = self.rect().adjusted(3, 3, -3, -3)
        painter.drawEllipse(rect)
        if self._state in {"listening", "success"}:
            self._draw_waveform(painter)

    def _draw_waveform(self, painter: QPainter) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#111827"))
        center_x = self.width() // 2
        base_y = 63
        bar_width = 5
        gap = 4
        levels = [0.45, 0.75, 1.0, 0.75, 0.45]
        for index, factor in enumerate(levels):
            height = 6 + int(self._level * 24 * factor)
            x = center_x - 2 * (bar_width + gap) + index * (bar_width + gap)
            y = base_y - height // 2
            painter.drawRoundedRect(x, y, bar_width, height, 2, 2)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_start is not None:
            self._dragging = True
            self.move(event.globalPosition().toPoint() - self._drag_start)
            self.moved.emit()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._dragging:
            self._drag_start = None
            self._click_timer.start(180)
            event.accept()
            return
        self._drag_start = None
        self._dragging = False
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        show_action = menu.addAction("打开面板")
        record_action = menu.addAction("开始/停止录音")
        insert_action = menu.addAction("插入预览文本")
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        action = menu.exec(event.globalPos())
        if action == show_action:
            self.panel_requested.emit()
        elif action == record_action:
            self.toggle_requested.emit()
        elif action == insert_action:
            self.insert_requested.emit()
        elif action == quit_action:
            self.quit_requested.emit()


class CompactInputPanel(QWidget):
    toggle_requested = Signal()
    insert_requested = Signal()
    copy_requested = Signal()
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
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.settings_requested.emit)

        button_layout.addWidget(self.toggle_button)
        button_layout.addWidget(self.insert_button)
        button_layout.addWidget(self.copy_button)
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


class FloatingInputWindow(QMainWindow):
    hotkey_pressed = Signal()

    def __init__(self, settings_store: SettingsStore) -> None:
        super().__init__()
        self.settings_store = settings_store
        self.settings = settings_store.load()
        self.recorder = Recorder(sample_rate=self.settings.sample_rate)
        self.injector = InputInjector()
        self.history = HistoryStore(limit=self.settings.history_limit)
        self.asr_engine = self._build_engine()
        self.worker: TranscribeWorker | None = None
        self.realtime_worker: RealtimeWebSocketWorker | None = None
        self.realtime_failed = False
        self.preview_text = ""
        self._diagnostic_started_at: float | None = None
        self._diagnostic_first_text_at: float | None = None
        self._diagnostic_stop_at: float | None = None
        self._diagnostic_finished_at: float | None = None
        self._diagnostic_last_error = ""
        self._close_tip_shown = False
        self.hotkey_pressed.connect(self.toggle_compact_recording)
        self.hotkey = GlobalHotkey(self.settings.hotkey, self.hotkey_pressed.emit)

        self.setWindowTitle("语音输入器")
        self.setMinimumSize(520, 420)
        self._build_ui()
        self._build_tray()
        self._build_floating_bar()
        self._build_compact_panel()
        self._refresh_history()

        if not self.hotkey.start():
            self._set_status("待机：全局快捷键依赖未安装，可使用窗口按钮")
        else:
            self._set_status(f"待机：按 {self.settings.hotkey} 开始/停止录音")

    def _build_engine(self) -> AsrEngine:
        return AsrEngine(
            provider=self.settings.asr_provider,
            model_size=self.settings.model_size,
            model_path=self.settings.model_path,
            language=self.settings.language,
            beam_size=self.settings.local_beam_size,
            api_base_url=self.settings.api_base_url,
            api_key=self.settings.api_key,
            api_model=self.settings.api_model,
        )

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

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
        self.record_button.clicked.connect(lambda: self.toggle_recording(show_panel=True))
        self.tidy_button = QPushButton("整理文本")
        self.tidy_button.setObjectName("secondaryButton")
        self.tidy_button.clicked.connect(self.tidy_current_text)
        self.copy_button = QPushButton("复制")
        self.copy_button.setObjectName("secondaryButton")
        self.copy_button.clicked.connect(self.copy_text)
        self.paste_button = QPushButton("插入")
        self.paste_button.setObjectName("accentButton")
        self.paste_button.clicked.connect(self.paste_text)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.record_button)
        button_layout.addWidget(self.tidy_button)
        button_layout.addWidget(self.copy_button)
        button_layout.addWidget(self.paste_button)

        input_page = QWidget()
        input_layout = QVBoxLayout(input_page)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(12)
        input_layout.addWidget(header)
        input_layout.addWidget(self.text_edit)
        input_layout.addLayout(button_layout)

        history_page = QWidget()
        history_layout = QVBoxLayout(history_page)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(
            lambda item: self._set_result_text(item.text())
        )
        history_layout.addWidget(self.history_list)

        settings_page = QWidget()
        form = QFormLayout(settings_page)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["local", "api", "websocket"])
        self.provider_combo.setCurrentText(self.settings.asr_provider)
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small"])
        if self.settings.model_size not in {"tiny", "base", "small"}:
            self.model_combo.addItem(self.settings.model_size)
        self.model_combo.setCurrentText(self.settings.model_size)
        self.model_path_input = QLineEdit(self.settings.model_path)
        self.model_path_input.setPlaceholderText("更大模型请填写已下载的本地模型目录")
        self.language_input = QComboBox()
        self.language_input.addItems(["zh", "en"])
        self.language_input.setCurrentText(self.settings.language if self.settings.language in {"zh", "en"} else "zh")
        self.api_base_url_input = QLineEdit(self.settings.api_base_url)
        self.api_base_url_input.setPlaceholderText("https://example.com/v1/audio/transcriptions")
        self.api_key_input = QLineEdit(self.settings.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("云端 API Key，settings.json 已被忽略")
        self.api_model_input = QLineEdit(self.settings.api_model)
        self.api_model_input.setPlaceholderText("例如 whisper-1 或服务商模型名")
        self.local_beam_size_input = QSpinBox()
        self.local_beam_size_input.setRange(1, 5)
        self.local_beam_size_input.setValue(self.settings.local_beam_size)
        self.local_beam_size_input.setToolTip("数值越小越快，输入法场景建议保持 1")
        self.websocket_url_input = QLineEdit(self.settings.websocket_url)
        self.websocket_url_input.setPlaceholderText("wss://example.com/realtime/asr")
        self.websocket_api_key_input = QLineEdit(self.settings.websocket_api_key)
        self.websocket_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.websocket_api_key_input.setPlaceholderText("实时识别 API Key，留空则尝试使用 API Key")
        self.websocket_model_input = QLineEdit(self.settings.websocket_model)
        self.websocket_model_input.setPlaceholderText("实时识别模型名，按服务商要求填写")
        self.realtime_chunk_input = QSpinBox()
        self.realtime_chunk_input.setRange(50, 2000)
        self.realtime_chunk_input.setSingleStep(50)
        self.realtime_chunk_input.setValue(self.settings.realtime_chunk_ms)
        self.websocket_final_wait_input = QSpinBox()
        self.websocket_final_wait_input.setRange(100, 5000)
        self.websocket_final_wait_input.setSingleStep(100)
        self.websocket_final_wait_input.setValue(self.settings.websocket_final_wait_ms)
        self.websocket_final_wait_input.setToolTip("停止录音后等待最终结果的时间，越短响应越快")
        self.hotkey_input = QLineEdit(self.settings.hotkey)
        self.auto_insert_check = QCheckBox()
        self.auto_insert_check.setChecked(self.settings.auto_insert)
        self.preview_before_insert_check = QCheckBox()
        self.preview_before_insert_check.setChecked(self.settings.preview_before_insert)
        self.postprocess_check = QCheckBox()
        self.postprocess_check.setChecked(self.settings.postprocess_enabled)
        self.postprocess_mode_combo = QComboBox()
        self.postprocess_mode_combo.addItems(["chat", "document", "code"])
        if self.settings.postprocess_mode not in {"chat", "document", "code"}:
            self.postprocess_mode_combo.addItem(self.settings.postprocess_mode)
        self.postprocess_mode_combo.setCurrentText(self.settings.postprocess_mode)
        self.history_limit_input = QSpinBox()
        self.history_limit_input.setRange(1, 100)
        self.history_limit_input.setValue(self.settings.history_limit)
        self.save_settings_button = QPushButton("保存设置")
        self.save_settings_button.clicked.connect(self.save_settings)
        form.addRow("识别模式", self.provider_combo)
        form.addRow("本地模型大小", self.model_combo)
        form.addRow("本地模型路径", self.model_path_input)
        form.addRow("识别语言", self.language_input)
        form.addRow("API 地址", self.api_base_url_input)
        form.addRow("API Key", self.api_key_input)
        form.addRow("API 模型", self.api_model_input)
        form.addRow("本地搜索宽度", self.local_beam_size_input)
        form.addRow("WebSocket 地址", self.websocket_url_input)
        form.addRow("WebSocket API Key", self.websocket_api_key_input)
        form.addRow("WebSocket 模型", self.websocket_model_input)
        form.addRow("实时音频块(ms)", self.realtime_chunk_input)
        form.addRow("实时收尾等待(ms)", self.websocket_final_wait_input)
        form.addRow("全局快捷键", self.hotkey_input)
        form.addRow("识别后自动插入", self.auto_insert_check)
        form.addRow("插入前预览确认", self.preview_before_insert_check)
        form.addRow("规则后处理", self.postprocess_check)
        form.addRow("文本场景模式", self.postprocess_mode_combo)
        form.addRow("历史记录条数", self.history_limit_input)
        form.addRow(self.save_settings_button)

        diagnostics_page = QWidget()
        diagnostics_form = QFormLayout(diagnostics_page)
        self.diagnostic_labels: dict[str, QLabel] = {}
        for key, label in (
            ("provider", "当前模式"),
            ("language", "识别语言"),
            ("api_key", "HTTP API Key"),
            ("websocket_key", "WebSocket Key"),
            ("websocket_url", "WebSocket 地址"),
            ("state", "当前状态"),
            ("first_text_latency", "首字延迟"),
            ("tail_latency", "停止后收尾"),
            ("total_elapsed", "总耗时"),
            ("last_error", "最近错误"),
        ):
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.diagnostic_labels[key] = value_label
            diagnostics_form.addRow(label, value_label)
        refresh_diagnostics_button = QPushButton("刷新诊断信息")
        refresh_diagnostics_button.clicked.connect(self._refresh_diagnostics)
        diagnostics_form.addRow(refresh_diagnostics_button)

        tabs = QTabWidget()
        tabs.setObjectName("mainTabs")
        tabs.addTab(input_page, "输入")
        tabs.addTab(history_page, "历史")
        tabs.addTab(settings_page, "设置")
        tabs.addTab(diagnostics_page, "诊断")
        layout.addWidget(tabs)
        self.setCentralWidget(root)
        self._apply_styles()
        self._update_context_badges()
        self._refresh_diagnostics()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f4f6f8;
            }
            QTabWidget::pane {
                border: 1px solid #d9dee7;
                border-radius: 8px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                min-width: 76px;
                padding: 8px 14px;
                color: #5d6675;
                background: #e9edf3;
                border: 1px solid #d9dee7;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                color: #172033;
                background: #ffffff;
            }
            QFrame#header {
                border: 1px solid #d9dee7;
                border-radius: 8px;
                background: #fbfcfe;
            }
            QLabel#statusLabel {
                color: #172033;
                font-size: 15px;
                font-weight: 600;
            }
            QLabel#feedbackLabel {
                color: #0f766e;
                background: #e8f7f4;
                border: 1px solid #b8e3dc;
                border-radius: 6px;
                padding: 6px 8px;
            }
            QLabel#badge {
                color: #384153;
                background: #eef2f7;
                border: 1px solid #d8dee9;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QTextEdit#resultEdit {
                border: 1px solid #d4dbe6;
                border-radius: 8px;
                padding: 10px;
                font-size: 15px;
                color: #172033;
                background: #ffffff;
                selection-background-color: #bfd7ff;
            }
            QPushButton {
                min-height: 34px;
                border-radius: 7px;
                padding: 7px 12px;
                font-weight: 600;
            }
            QPushButton#primaryButton {
                color: #ffffff;
                background: #2563eb;
                border: 1px solid #1d4ed8;
            }
            QPushButton#primaryButton:hover {
                background: #1d4ed8;
            }
            QPushButton#recordingButton {
                color: #ffffff;
                background: #dc2626;
                border: 1px solid #b91c1c;
            }
            QPushButton#recordingButton:hover {
                background: #b91c1c;
            }
            QPushButton#accentButton {
                color: #ffffff;
                background: #0f766e;
                border: 1px solid #0f6a62;
            }
            QPushButton#accentButton:hover {
                background: #0d625b;
            }
            QPushButton#secondaryButton {
                color: #243044;
                background: #ffffff;
                border: 1px solid #cfd7e3;
            }
            QPushButton#secondaryButton:hover {
                background: #f2f5f9;
            }
            QPushButton:disabled {
                color: #8a94a6;
                background: #edf1f5;
                border: 1px solid #d7dee8;
            }
            QLineEdit, QComboBox, QSpinBox {
                min-height: 28px;
                border: 1px solid #cfd7e3;
                border-radius: 6px;
                padding: 4px 7px;
                background: #ffffff;
            }
            QListWidget {
                border: 1px solid #d4dbe6;
                border-radius: 8px;
                background: #ffffff;
            }
            """
        )

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray.activated.connect(self.on_tray_activated)
        menu = QMenu(self)

        show_action = QAction("显示输入框", self)
        show_action.triggered.connect(self.show_compact_panel)
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.show_window)
        record_action = QAction("开始/停止录音", self)
        record_action.triggered.connect(self.toggle_compact_recording)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action)
        menu.addAction(settings_action)
        menu.addAction(record_action)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _build_floating_bar(self) -> None:
        self.floating_bar = FloatingVoiceBall()
        self.floating_bar.toggle_requested.connect(self.toggle_compact_recording)
        self.floating_bar.panel_requested.connect(self.show_compact_panel)
        self.floating_bar.insert_requested.connect(self.insert_preview_text)
        self.floating_bar.quit_requested.connect(self.quit_app)
        self.floating_bar.moved.connect(self._position_compact_panel)
        self.floating_bar.move(80, 160)
        self.floating_bar.show()

    def _build_compact_panel(self) -> None:
        self.compact_panel = CompactInputPanel()
        self.compact_panel.toggle_requested.connect(self.toggle_compact_recording)
        self.compact_panel.insert_requested.connect(self.insert_preview_text)
        self.compact_panel.copy_requested.connect(self.copy_text)
        self.compact_panel.settings_requested.connect(self.show_window)

    def _position_compact_panel(self) -> None:
        if not hasattr(self, "compact_panel") or not hasattr(self, "floating_bar"):
            return
        if not self.compact_panel.isVisible():
            return
        ball_rect = self.floating_bar.geometry()
        self.compact_panel.move(ball_rect.right(), ball_rect.top())

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self._refresh_diagnostics()

    def _set_feedback(self, text: str, is_error: bool = False) -> None:
        self.feedback_label.setText(text)
        self.feedback_label.setVisible(bool(text))
        if is_error:
            self.feedback_label.setStyleSheet(
                "color: #991b1b; background: #fef2f2; border: 1px solid #fecaca;"
            )
        else:
            self.feedback_label.setStyleSheet("")

    def _set_record_button_state(self, recording: bool) -> None:
        if recording:
            self.record_button.setText("停止录音")
            self.record_button.setObjectName("recordingButton")
        else:
            self.record_button.setText("开始说话")
            self.record_button.setObjectName("primaryButton")
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        if hasattr(self, "compact_panel"):
            self.compact_panel.set_recording(recording)

    def _set_result_text(self, text: str) -> None:
        self.text_edit.setPlainText(text)
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
        if hasattr(self, "compact_panel"):
            self.compact_panel.set_text(text)

    def _clear_result_text(self) -> None:
        self._set_result_text("")

    def _current_result_text(self) -> str:
        if hasattr(self, "compact_panel") and self.compact_panel.isVisible():
            return self.compact_panel.text()
        return self.text_edit.toPlainText()

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.tidy_button.setEnabled(enabled)
        self.copy_button.setEnabled(enabled)
        self.paste_button.setEnabled(enabled)

    def _update_context_badges(self) -> None:
        if not hasattr(self, "mode_badge"):
            return
        self.mode_badge.setText(f"模式：{self._provider_label()}")
        self.language_badge.setText(f"语言：{self._language_label()}")

    def _set_connection_state(self, text: str) -> None:
        self.connection_badge.setText(text)
        self._refresh_diagnostics()

    def _set_floating_bar_state(
        self,
        state: str,
        title: str,
        preview: str = "",
        can_insert: bool = False,
    ) -> None:
        if hasattr(self, "floating_bar"):
            self.floating_bar.set_state(state, title, preview, can_insert)
        if hasattr(self, "compact_panel") and state == "idle":
            self.compact_panel.hide()

    @Slot(float)
    def on_audio_level(self, level: float) -> None:
        if hasattr(self, "floating_bar"):
            self.floating_bar.set_audio_level(level)

    def _postprocess_text(self, text: str) -> str:
        return postprocess_text(
            text,
            mode=self.settings.postprocess_mode,
            enabled=self.settings.postprocess_enabled,
        )

    @staticmethod
    def _format_diagnostic_duration(seconds: float | None) -> str:
        if seconds is None:
            return "-"
        return f"{seconds * 1000:.0f} ms"

    @staticmethod
    def _configured(value: str) -> str:
        return "已配置" if value.strip() else "未配置"

    def _mark_diagnostic_start(self) -> None:
        now = time.perf_counter()
        self._diagnostic_started_at = now
        self._diagnostic_first_text_at = None
        self._diagnostic_stop_at = None
        self._diagnostic_finished_at = None
        self._diagnostic_last_error = ""
        self._refresh_diagnostics()

    def _mark_diagnostic_first_text(self) -> None:
        if self._diagnostic_started_at is not None and self._diagnostic_first_text_at is None:
            self._diagnostic_first_text_at = time.perf_counter()
            self._refresh_diagnostics()

    def _mark_diagnostic_stop(self) -> None:
        if self._diagnostic_started_at is not None and self._diagnostic_stop_at is None:
            self._diagnostic_stop_at = time.perf_counter()
            self._refresh_diagnostics()

    def _mark_diagnostic_finish(self) -> None:
        if self._diagnostic_started_at is not None:
            self._diagnostic_finished_at = time.perf_counter()
            self._refresh_diagnostics()

    def _set_diagnostic_error(self, message: str) -> None:
        self._diagnostic_last_error = redact_secret(message)
        self._refresh_diagnostics()

    def _refresh_diagnostics(self) -> None:
        if not hasattr(self, "diagnostic_labels"):
            return

        first_text_latency = None
        tail_latency = None
        total_elapsed = None
        if self._diagnostic_started_at is not None and self._diagnostic_first_text_at is not None:
            first_text_latency = self._diagnostic_first_text_at - self._diagnostic_started_at
        if self._diagnostic_stop_at is not None and self._diagnostic_finished_at is not None:
            tail_latency = self._diagnostic_finished_at - self._diagnostic_stop_at
        if self._diagnostic_started_at is not None and self._diagnostic_finished_at is not None:
            total_elapsed = self._diagnostic_finished_at - self._diagnostic_started_at

        values = {
            "provider": self._provider_label(),
            "language": self._language_label(),
            "api_key": self._configured(self.settings.api_key),
            "websocket_key": self._configured(self.settings.websocket_api_key or self.settings.api_key),
            "websocket_url": self._configured(self.settings.websocket_url),
            "state": self.connection_badge.text() if hasattr(self, "connection_badge") else "-",
            "first_text_latency": self._format_diagnostic_duration(first_text_latency),
            "tail_latency": self._format_diagnostic_duration(tail_latency),
            "total_elapsed": self._format_diagnostic_duration(total_elapsed),
            "last_error": self._diagnostic_last_error or "无",
        }
        for key, value in values.items():
            self.diagnostic_labels[key].setText(value)

    @Slot()
    def toggle_compact_recording(self) -> None:
        self.show_compact_panel()
        self.toggle_recording(show_panel=False)

    def show_compact_panel(self) -> None:
        if not hasattr(self, "compact_panel"):
            return
        self.compact_panel.show()
        self._position_compact_panel()
        self.compact_panel.raise_()
        self.compact_panel.activateWindow()

    @Slot()
    def toggle_recording(self, show_panel: bool = True) -> None:
        if show_panel:
            self.show_window()
        if self.realtime_worker is not None and self.realtime_worker.isRunning():
            self.stop_websocket_realtime()
            return
        if self.worker is not None and self.worker.isRunning():
            self._set_status("识别中，请稍候")
            return

        if self.recorder.is_recording:
            self.stop_recording()
            return

        self.apply_settings_from_form(save=False, restart_hotkey=False)
        if self.settings.asr_provider == "websocket":
            self.start_websocket_realtime()
            return

        self.start_recording()

    def start_websocket_realtime(self) -> None:
        config = RealtimeAsrConfig(
            websocket_url=self.settings.websocket_url,
            api_key=self.settings.websocket_api_key or self.settings.api_key,
            model=self.settings.websocket_model,
            language=self.settings.language,
            sample_rate=self.settings.sample_rate,
            chunk_ms=self.settings.realtime_chunk_ms,
            final_wait_seconds=self.settings.websocket_final_wait_ms / 1000,
        )
        self._clear_result_text()
        self.preview_text = ""
        self.realtime_failed = False
        self._mark_diagnostic_start()
        self.realtime_worker = RealtimeWebSocketWorker(config)
        self.realtime_worker.partial.connect(self.on_realtime_partial)
        self.realtime_worker.final.connect(self.on_realtime_final)
        self.realtime_worker.error.connect(self.on_realtime_error)
        self.realtime_worker.level.connect(self.on_audio_level)
        self.realtime_worker.finished.connect(self.on_realtime_finished)
        self.realtime_worker.start()
        self._set_record_button_state(recording=True)
        self._set_actions_enabled(False)
        self._set_connection_state("连接中")
        self._set_floating_bar_state("listening", "监听中", "等待你开始说话")
        self._set_feedback("实时模式已启动，正在等待语音输入")
        self._set_status("实时识别中：正在通过 WebSocket 边说边出字")

    def stop_websocket_realtime(self) -> None:
        if self.realtime_worker is not None:
            self.realtime_worker.stop()
        self._mark_diagnostic_stop()
        self._set_record_button_state(recording=False)
        self._set_connection_state("结束中")
        self.on_audio_level(0.0)
        self._set_floating_bar_state("processing", "处理中", "正在结束实时识别")
        self._set_status("停止录音：正在结束 WebSocket 实时识别")

    @Slot(str)
    def on_realtime_partial(self, text: str) -> None:
        self._set_result_text(text)
        self.preview_text = text
        self._mark_diagnostic_first_text()
        self._set_connection_state("识别中")
        self._set_floating_bar_state("success", "说话中", text)
        self._set_feedback("正在实时输出识别结果")

    @Slot(str)
    def on_realtime_final(self, text: str) -> None:
        self._set_result_text(text)
        self.preview_text = text
        self._mark_diagnostic_first_text()
        self._set_connection_state("完成")
        self._set_floating_bar_state("success", "说话中", text)

    @Slot(str)
    def on_realtime_error(self, message: str) -> None:
        self.realtime_failed = True
        self._set_diagnostic_error(message)
        self._mark_diagnostic_finish()
        self._show_error(message)
        self._set_record_button_state(recording=False)
        self._set_actions_enabled(True)
        self._set_connection_state("错误")
        self._set_floating_bar_state("error", "错误", message)
        self._set_status("错误：WebSocket 实时识别失败")

    @Slot()
    def on_realtime_finished(self) -> None:
        if self.realtime_failed:
            self.realtime_worker = None
            return

        text = self._postprocess_text(self._current_result_text().strip())
        if text:
            self._set_result_text(text)
        if text:
            self.history.add(text)
            self._refresh_history()
            self.preview_text = text
            if self.settings.auto_insert and not self.settings.preview_before_insert:
                self.paste_text()
            else:
                self._set_floating_bar_state("success", "待确认", text, can_insert=True)
        else:
            self._set_floating_bar_state("idle", "待机", "没有识别到可用文字")
        self._set_record_button_state(recording=False)
        self._set_actions_enabled(True)
        self._set_connection_state("待机")
        self.realtime_worker = None
        self._mark_diagnostic_finish()
        self._set_feedback("实时识别已完成，可以确认插入")
        self._set_status("完成：WebSocket 实时识别已结束")

    def start_recording(self) -> None:
        try:
            self.recorder.start(on_level=self.on_audio_level)
        except RecordingError as exc:
            self._show_error(str(exc))
            return

        self._clear_result_text()
        self.preview_text = ""
        self._mark_diagnostic_start()
        self._set_record_button_state(recording=True)
        self._set_actions_enabled(False)
        self._set_connection_state("录音中")
        self.on_audio_level(0.0)
        self._set_floating_bar_state("listening", "监听中", "等待你开始说话")
        self._set_feedback("正在录音，结束后会自动识别")
        self._set_status("录音中：再次点击或按快捷键停止")

    def stop_recording(self) -> None:
        try:
            audio_path = self.recorder.stop()
        except RecordingError as exc:
            self._set_diagnostic_error(str(exc))
            self._mark_diagnostic_finish()
            self._show_error(str(exc))
            self._set_record_button_state(recording=False)
            self._set_actions_enabled(True)
            self._set_connection_state("错误")
            return

        self._mark_diagnostic_stop()
        self._set_record_button_state(recording=False)
        self._set_actions_enabled(False)
        self._set_connection_state("识别中")
        self.on_audio_level(0.0)
        self._set_floating_bar_state("processing", "处理中", "正在生成文字")
        self._set_feedback("录音已结束，正在生成文字")
        self._set_status(f"识别中：正在使用{self._provider_label()}转写")
        self.worker = TranscribeWorker(self.asr_engine, audio_path)
        self.worker.partial.connect(self.on_transcription_partial)
        self.worker.finished.connect(self.on_transcription_finished)
        self.worker.start()

    @Slot(str)
    def on_transcription_partial(self, text: str) -> None:
        self._set_result_text(text)
        self.preview_text = text
        self._mark_diagnostic_first_text()
        self._set_floating_bar_state("success", "说话中", text)

    @Slot(object)
    def on_transcription_finished(self, result: TranscriptionResult) -> None:
        if result.error:
            self._set_diagnostic_error(result.error)
            self._mark_diagnostic_finish()
            self._show_error(result.error)
            self._set_actions_enabled(True)
            self._set_connection_state("错误")
            self._set_status("错误：识别失败")
            return

        processed_text = self._postprocess_text(result.text)
        self._set_result_text(processed_text)
        self.preview_text = processed_text
        if processed_text:
            self._mark_diagnostic_first_text()
        self.history.add(processed_text)
        self._refresh_history()
        self._set_actions_enabled(True)
        self._set_connection_state("待机")
        self._set_floating_bar_state("success", "待确认", processed_text, can_insert=bool(processed_text))
        self._set_feedback("识别完成，可以编辑、复制或插入")
        self._set_status(
            f"完成：{self._provider_label()} {result.model_name}，耗时 {result.elapsed_seconds:.1f}s"
        )
        self._mark_diagnostic_finish()
        if self.settings.auto_insert and processed_text and not self.settings.preview_before_insert:
            self.paste_text()

    @Slot()
    def tidy_current_text(self) -> None:
        self._set_result_text(tidy_text(self._current_result_text()))
        self._set_feedback("文本已整理")

    @Slot()
    def copy_text(self) -> None:
        try:
            self.injector.copy(self._current_result_text())
            self._set_feedback("已复制到剪贴板")
            self._set_status("已复制到剪贴板")
        except RuntimeError as exc:
            self._show_error(str(exc))

    @Slot()
    def paste_text(self) -> None:
        text = self._current_result_text()
        try:
            self.injector.paste(text)
            self._set_feedback("已插入到当前输入位置")
            self._set_floating_bar_state("idle", "待机", "已插入")
            self._set_status("已插入到当前输入位置")
        except RuntimeError as exc:
            self._show_error(str(exc))

    @Slot()
    def insert_preview_text(self) -> None:
        text = self._current_result_text().strip() or self.preview_text.strip()
        if not text:
            self._set_floating_bar_state("idle", "待机", "没有可插入的预览文本")
            return
        try:
            self.injector.paste(text)
            self._set_feedback("预览文本已插入")
            self._set_status("预览文本已插入到当前输入位置")
            self._set_floating_bar_state("idle", "待机", "已插入")
        except RuntimeError as exc:
            self._show_error(str(exc))

    @Slot()
    def save_settings(self) -> None:
        self.apply_settings_from_form(save=True, restart_hotkey=True)
        self._update_context_badges()
        self._set_feedback("设置已保存，下一次识别会使用新配置")
        self._set_status("设置已保存")

    def apply_settings_from_form(self, save: bool, restart_hotkey: bool) -> None:
        previous_settings = self.settings
        self.settings = Settings(
            asr_provider=self.provider_combo.currentText(),
            model_size=self.model_combo.currentText(),
            model_path=self.model_path_input.text().strip(),
            language=self.language_input.currentText(),
            api_base_url=self.api_base_url_input.text().strip(),
            api_key=self.api_key_input.text().strip(),
            api_model=self.api_model_input.text().strip(),
            local_beam_size=self.local_beam_size_input.value(),
            websocket_url=self.websocket_url_input.text().strip(),
            websocket_api_key=self.websocket_api_key_input.text().strip(),
            websocket_model=self.websocket_model_input.text().strip(),
            realtime_chunk_ms=self.realtime_chunk_input.value(),
            websocket_final_wait_ms=self.websocket_final_wait_input.value(),
            hotkey=self.hotkey_input.text().strip() or "ctrl+alt+space",
            auto_insert=self.auto_insert_check.isChecked(),
            preview_before_insert=self.preview_before_insert_check.isChecked(),
            postprocess_enabled=self.postprocess_check.isChecked(),
            postprocess_mode=self.postprocess_mode_combo.currentText(),
            history_limit=self.history_limit_input.value(),
            sample_rate=self.settings.sample_rate,
        )
        self._update_context_badges()
        if save:
            self.settings_store.save(self.settings)
        if self._engine_settings_changed(previous_settings, self.settings):
            self.asr_engine = self._build_engine()
        self.history.limit = self.settings.history_limit
        self._refresh_diagnostics()
        if restart_hotkey:
            self.hotkey.stop()
            self.hotkey = GlobalHotkey(self.settings.hotkey, self.hotkey_pressed.emit)
            self.hotkey.start()

    @staticmethod
    def _engine_settings_changed(old: Settings, new: Settings) -> bool:
        return any(
            getattr(old, field) != getattr(new, field)
            for field in (
                "asr_provider",
                "model_size",
                "model_path",
                "language",
                "api_base_url",
                "api_key",
                "api_model",
                "local_beam_size",
            )
        )

    def _refresh_history(self) -> None:
        self.history_list.clear()
        for item in self.history.list():
            self.history_list.addItem(item.text)

    def _show_error(self, message: str) -> None:
        self._set_diagnostic_error(message)
        self._set_feedback(message, is_error=True)
        self._set_floating_bar_state("error", "错误", message)
        QMessageBox.warning(self, "提示", message)

    @Slot(object)
    def on_tray_activated(self, reason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.show_window()

    @Slot()
    def show_window(self) -> None:
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        if hasattr(self, "compact_panel"):
            self.compact_panel.hide()

    def _provider_label(self) -> str:
        if self.settings.asr_provider == "api":
            return "云端 API"
        if self.settings.asr_provider == "websocket":
            return "WebSocket 实时识别"
        return "本地模型"

    def _language_label(self) -> str:
        if self.settings.language == "en":
            return "English"
        return "中文"

    def closeEvent(self, event) -> None:
        self.hide()
        self.floating_bar.show()
        if not self._close_tip_shown and self.tray.isVisible():
            self.tray.showMessage(
                "语音输入器仍在运行",
                "窗口已隐藏，悬浮球仍可继续控制录音。双击悬浮球或托盘图标可恢复。",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            self._close_tip_shown = True
        event.ignore()

    def quit_app(self) -> None:
        if self.realtime_worker is not None and self.realtime_worker.isRunning():
            self.realtime_worker.stop()
        self.hotkey.stop()
        self.floating_bar.hide()
        if hasattr(self, "compact_panel"):
            self.compact_panel.hide()
        self.tray.hide()
        QApplication.quit()
