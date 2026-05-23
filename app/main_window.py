from __future__ import annotations

from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtGui import QAction, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
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
from app.text_tools import tidy_text


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

    def __init__(self, config: RealtimeAsrConfig) -> None:
        super().__init__()
        self.client = WebSocketRealtimeAsrClient(config)

    def run(self) -> None:
        self.client.run(
            on_partial=self.partial.emit,
            on_final=self.final.emit,
            on_error=self.error.emit,
        )

    def stop(self) -> None:
        self.client.stop()


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
        self._close_tip_shown = False
        self.hotkey_pressed.connect(self.toggle_recording)
        self.hotkey = GlobalHotkey(self.settings.hotkey, self.hotkey_pressed.emit)

        self.setWindowTitle("语音输入器")
        self.setMinimumSize(460, 360)
        self._build_ui()
        self._build_tray()
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
            api_base_url=self.settings.api_base_url,
            api_key=self.settings.api_key,
            api_model=self.settings.api_model,
        )

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        self.status_label = QLabel()
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("识别结果会显示在这里，也可以手动编辑后复制或插入。")

        self.record_button = QPushButton("开始录音")
        self.record_button.clicked.connect(self.toggle_recording)
        self.tidy_button = QPushButton("整理文本")
        self.tidy_button.clicked.connect(self.tidy_current_text)
        self.copy_button = QPushButton("复制")
        self.copy_button.clicked.connect(self.copy_text)
        self.paste_button = QPushButton("插入")
        self.paste_button.clicked.connect(self.paste_text)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.record_button)
        button_layout.addWidget(self.tidy_button)
        button_layout.addWidget(self.copy_button)
        button_layout.addWidget(self.paste_button)

        input_page = QWidget()
        input_layout = QVBoxLayout(input_page)
        input_layout.addWidget(self.status_label)
        input_layout.addWidget(self.text_edit)
        input_layout.addLayout(button_layout)

        history_page = QWidget()
        history_layout = QVBoxLayout(history_page)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(
            lambda item: self.text_edit.setPlainText(item.text())
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
        self.language_input = QLineEdit(self.settings.language)
        self.api_base_url_input = QLineEdit(self.settings.api_base_url)
        self.api_base_url_input.setPlaceholderText("https://example.com/v1/audio/transcriptions")
        self.api_key_input = QLineEdit(self.settings.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("云端 API Key，settings.json 已被忽略")
        self.api_model_input = QLineEdit(self.settings.api_model)
        self.api_model_input.setPlaceholderText("例如 whisper-1 或服务商模型名")
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
        self.hotkey_input = QLineEdit(self.settings.hotkey)
        self.auto_insert_check = QCheckBox()
        self.auto_insert_check.setChecked(self.settings.auto_insert)
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
        form.addRow("WebSocket 地址", self.websocket_url_input)
        form.addRow("WebSocket API Key", self.websocket_api_key_input)
        form.addRow("WebSocket 模型", self.websocket_model_input)
        form.addRow("实时音频块(ms)", self.realtime_chunk_input)
        form.addRow("全局快捷键", self.hotkey_input)
        form.addRow("识别后自动插入", self.auto_insert_check)
        form.addRow("历史记录条数", self.history_limit_input)
        form.addRow(self.save_settings_button)

        tabs = QTabWidget()
        tabs.addTab(input_page, "输入")
        tabs.addTab(history_page, "历史")
        tabs.addTab(settings_page, "设置")
        layout.addWidget(tabs)
        self.setCentralWidget(root)

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray.activated.connect(self.on_tray_activated)
        menu = QMenu(self)

        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show_window)
        record_action = QAction("开始/停止录音", self)
        record_action.triggered.connect(self.toggle_recording)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action)
        menu.addAction(record_action)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    @Slot()
    def toggle_recording(self) -> None:
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
        )
        self.text_edit.clear()
        self.realtime_failed = False
        self.realtime_worker = RealtimeWebSocketWorker(config)
        self.realtime_worker.partial.connect(self.on_realtime_partial)
        self.realtime_worker.final.connect(self.on_realtime_final)
        self.realtime_worker.error.connect(self.on_realtime_error)
        self.realtime_worker.finished.connect(self.on_realtime_finished)
        self.realtime_worker.start()
        self.record_button.setText("停止录音")
        self._set_status("实时识别中：正在通过 WebSocket 边说边出字")

    def stop_websocket_realtime(self) -> None:
        if self.realtime_worker is not None:
            self.realtime_worker.stop()
        self.record_button.setText("开始录音")
        self._set_status("停止录音：正在结束 WebSocket 实时识别")

    @Slot(str)
    def on_realtime_partial(self, text: str) -> None:
        self.text_edit.setPlainText(text)
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

    @Slot(str)
    def on_realtime_final(self, text: str) -> None:
        self.text_edit.setPlainText(text)
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

    @Slot(str)
    def on_realtime_error(self, message: str) -> None:
        self.realtime_failed = True
        self._show_error(message)
        self.record_button.setText("开始录音")
        self._set_status("错误：WebSocket 实时识别失败")

    @Slot()
    def on_realtime_finished(self) -> None:
        if self.realtime_failed:
            self.realtime_worker = None
            return

        text = self.text_edit.toPlainText().strip()
        if text:
            self.history.add(text)
            self._refresh_history()
            if self.settings.auto_insert:
                self.paste_text()
        self.record_button.setText("开始录音")
        self.realtime_worker = None
        self._set_status("完成：WebSocket 实时识别已结束")

    def start_recording(self) -> None:
        try:
            self.recorder.start()
        except RecordingError as exc:
            self._show_error(str(exc))
            return

        self.text_edit.clear()
        self.record_button.setText("停止录音")
        self._set_status("录音中：再次点击或按快捷键停止")

    def stop_recording(self) -> None:
        try:
            audio_path = self.recorder.stop()
        except RecordingError as exc:
            self._show_error(str(exc))
            self.record_button.setText("开始录音")
            return

        self.record_button.setText("开始录音")
        self._set_status(f"识别中：正在使用{self._provider_label()}转写")
        self.worker = TranscribeWorker(self.asr_engine, audio_path)
        self.worker.partial.connect(self.on_transcription_partial)
        self.worker.finished.connect(self.on_transcription_finished)
        self.worker.start()

    @Slot(str)
    def on_transcription_partial(self, text: str) -> None:
        self.text_edit.setPlainText(text)
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

    @Slot(object)
    def on_transcription_finished(self, result: TranscriptionResult) -> None:
        if result.error:
            self._show_error(result.error)
            self._set_status("错误：识别失败")
            return

        self.text_edit.setPlainText(result.text)
        self.history.add(result.text)
        self._refresh_history()
        self._set_status(
            f"完成：{self._provider_label()} {result.model_name}，耗时 {result.elapsed_seconds:.1f}s"
        )
        if self.settings.auto_insert and result.text:
            self.paste_text()

    @Slot()
    def tidy_current_text(self) -> None:
        self.text_edit.setPlainText(tidy_text(self.text_edit.toPlainText()))

    @Slot()
    def copy_text(self) -> None:
        try:
            self.injector.copy(self.text_edit.toPlainText())
            self._set_status("已复制到剪贴板")
        except RuntimeError as exc:
            self._show_error(str(exc))

    @Slot()
    def paste_text(self) -> None:
        try:
            self.injector.paste(self.text_edit.toPlainText())
            self._set_status("已插入到当前输入位置")
        except RuntimeError as exc:
            self._show_error(str(exc))

    @Slot()
    def save_settings(self) -> None:
        self.apply_settings_from_form(save=True, restart_hotkey=True)
        self._set_status("设置已保存")

    def apply_settings_from_form(self, save: bool, restart_hotkey: bool) -> None:
        self.settings = Settings(
            asr_provider=self.provider_combo.currentText(),
            model_size=self.model_combo.currentText(),
            model_path=self.model_path_input.text().strip(),
            language=self.language_input.text().strip() or "zh",
            api_base_url=self.api_base_url_input.text().strip(),
            api_key=self.api_key_input.text().strip(),
            api_model=self.api_model_input.text().strip(),
            websocket_url=self.websocket_url_input.text().strip(),
            websocket_api_key=self.websocket_api_key_input.text().strip(),
            websocket_model=self.websocket_model_input.text().strip(),
            realtime_chunk_ms=self.realtime_chunk_input.value(),
            hotkey=self.hotkey_input.text().strip() or "ctrl+alt+space",
            auto_insert=self.auto_insert_check.isChecked(),
            history_limit=self.history_limit_input.value(),
            sample_rate=self.settings.sample_rate,
        )
        if save:
            self.settings_store.save(self.settings)
        self.asr_engine = self._build_engine()
        self.history.limit = self.settings.history_limit
        if restart_hotkey:
            self.hotkey.stop()
            self.hotkey = GlobalHotkey(self.settings.hotkey, self.hotkey_pressed.emit)
            self.hotkey.start()

    def _refresh_history(self) -> None:
        self.history_list.clear()
        for item in self.history.list():
            self.history_list.addItem(item.text)

    def _show_error(self, message: str) -> None:
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
        self.show()
        self.raise_()
        self.activateWindow()

    def _provider_label(self) -> str:
        if self.settings.asr_provider == "api":
            return "云端 API"
        if self.settings.asr_provider == "websocket":
            return "WebSocket 实时识别"
        return "本地模型"

    def closeEvent(self, event) -> None:
        self.hide()
        if not self._close_tip_shown and self.tray.isVisible():
            self.tray.showMessage(
                "语音输入器仍在运行",
                "窗口已隐藏到托盘。双击托盘图标可恢复，也可以从托盘菜单退出。",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            self._close_tip_shown = True
        event.ignore()

    def quit_app(self) -> None:
        if self.realtime_worker is not None and self.realtime_worker.isRunning():
            self.realtime_worker.stop()
        self.hotkey.stop()
        self.tray.hide()
        QApplication.quit()
