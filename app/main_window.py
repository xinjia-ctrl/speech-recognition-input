from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QSystemTrayIcon,
)

from app.asr import UnifiedAsrEngine
from app.config_check import build_config_checks
from app.config import SettingsStore
from app.controllers import (
    InputController,
    RecognitionSessionController,
    TranslationController,
    TranslationRequest,
)
from app.errors import user_error_message
from app.history import HistoryStore
from app.input import GlobalHotkey
from app.session_state import SessionDiagnostics
from app.text_pipeline import process_text_pipeline
from app.text_tools import tidy_text
from app.text_translate import translation_button_label
from app.ui import CompactInputPanel, FloatingVoiceBall, MainPanel
from app.ui.styles import MAIN_WINDOW_STYLE
from app.window_recognition import RecognitionWindowMixin
from app.window_state import diagnostic_values, engine_settings_changed, language_label, provider_label


class FloatingInputWindow(RecognitionWindowMixin, QMainWindow):
    hotkey_pressed = Signal()

    def __init__(self, settings_store: SettingsStore) -> None:
        super().__init__()
        self.settings_store = settings_store
        self.settings = settings_store.load()
        self.input_controller = InputController()
        self.translation_controller = TranslationController()
        self.translation_controller.finished.connect(self.on_translation_finished)
        self.translation_controller.error.connect(self.on_translation_error)
        self.history = HistoryStore(limit=self.settings.history_limit)
        self.asr_engine = self._build_engine()
        self.recognition = RecognitionSessionController(self.asr_engine, sample_rate=self.settings.sample_rate)
        self._connect_recognition_signals()
        self.preview_text = ""
        self.diagnostics = SessionDiagnostics()
        self._close_tip_shown = False
        self.hotkey_active = False
        self.microphone_available: bool | None = None
        self.hotkey_pressed.connect(self.on_hotkey_pressed)
        self.hotkey = GlobalHotkey(self.settings.hotkey, self.hotkey_pressed.emit)

        self.setWindowTitle("XinVoice")
        self.setMinimumSize(520, 420)
        self._build_ui()
        self._build_tray()
        self._build_floating_bar()
        self._build_compact_panel()
        self._refresh_history()

        self.hotkey_active = self.hotkey.start()
        if not self.hotkey_active:
            self._set_status("待机：全局快捷键依赖未安装，可使用窗口按钮")
        else:
            self._set_status(f"待机：按 {self.settings.hotkey} 开始/停止录音")

    def _build_engine(self) -> UnifiedAsrEngine:
        return UnifiedAsrEngine(self.settings)

    def _connect_recognition_signals(self) -> None:
        self.recognition.audio_level.connect(self.on_audio_level)
        self.recognition.recording_started.connect(self.on_recording_started)
        self.recognition.recording_failed.connect(self.on_recording_failed)
        self.recognition.recording_stopped.connect(self.on_recording_stopped)
        self.recognition.file_transcription_started.connect(self.on_file_transcription_started)
        self.recognition.file_partial.connect(self.on_transcription_partial)
        self.recognition.file_fallback.connect(self.on_file_fallback)
        self.recognition.file_finished.connect(self.on_transcription_finished)
        self.recognition.realtime_started.connect(self.on_realtime_started)
        self.recognition.realtime_stopping.connect(self.on_realtime_stopping)
        self.recognition.realtime_partial.connect(self.on_realtime_partial)
        self.recognition.realtime_final.connect(self.on_realtime_final)
        self.recognition.realtime_error.connect(self.on_realtime_error)
        self.recognition.realtime_finished.connect(self.on_realtime_finished)

    def _build_ui(self) -> None:
        self.main_panel = MainPanel(self.settings)
        self.main_panel.record_requested.connect(lambda: self.toggle_recording(show_panel=True))
        self.main_panel.tidy_requested.connect(self.tidy_current_text)
        self.main_panel.copy_requested.connect(self.copy_text)
        self.main_panel.paste_requested.connect(self.paste_text)
        self.main_panel.history_item_selected.connect(self._set_result_text)
        self.main_panel.save_settings_requested.connect(self.save_settings)
        self.main_panel.refresh_config_checks_requested.connect(self.refresh_config_checks)
        self.main_panel.refresh_diagnostics_requested.connect(self._refresh_diagnostics)
        self.settings_panel = self.main_panel.settings_panel
        self.config_check_panel = self.main_panel.config_check_panel
        self.diagnostics_panel = self.main_panel.diagnostics_panel
        self.setCentralWidget(self.main_panel)
        self._apply_styles()
        self._update_context_badges()
        self.settings_panel.refresh_hints()
        self.refresh_config_checks()
        self._refresh_diagnostics()

    def _apply_styles(self) -> None:
        self.setStyleSheet(MAIN_WINDOW_STYLE)

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
        self.floating_bar.close_requested.connect(self.hide_floating_button)
        self.floating_bar.quit_requested.connect(self.quit_app)
        self.floating_bar.moved.connect(self._position_compact_panel)
        self.floating_bar.move(80, 160)
        self.floating_bar.show()

    def _build_compact_panel(self) -> None:
        self.compact_panel = CompactInputPanel()
        self.compact_panel.toggle_requested.connect(self.toggle_compact_recording)
        self.compact_panel.insert_requested.connect(self.insert_preview_text)
        self.compact_panel.copy_requested.connect(self.copy_text)
        self.compact_panel.translate_requested.connect(self.translate_current_text)
        self.compact_panel.settings_requested.connect(self.show_window)
        self._update_compact_translation_button()

    def _update_compact_translation_button(self) -> None:
        if hasattr(self, "compact_panel"):
            self.compact_panel.set_translation_label(translation_button_label(self.settings.language))

    def _position_compact_panel(self) -> None:
        if not hasattr(self, "compact_panel") or not hasattr(self, "floating_bar"):
            return
        if not self.compact_panel.isVisible():
            return
        ball_rect = self.floating_bar.geometry()
        self.compact_panel.move(ball_rect.right(), ball_rect.top())

    @Slot()
    def on_hotkey_pressed(self) -> None:
        if hasattr(self, "floating_bar") and not self.floating_bar.isVisible():
            self.floating_bar.show()
            self.floating_bar.raise_()
            self._set_status(f"待机：按 {self.settings.hotkey} 开始/停止录音")
            return
        self.toggle_compact_recording()

    @Slot()
    def hide_floating_button(self) -> None:
        if hasattr(self, "compact_panel"):
            self.compact_panel.hide()
        self.floating_bar.hide()
        self._set_status(f"悬浮按钮已隐藏：按 {self.settings.hotkey} 唤醒")

    def _set_status(self, text: str) -> None:
        self.main_panel.set_status(text)
        self._refresh_diagnostics()

    def _set_feedback(self, text: str, is_error: bool = False) -> None:
        self.main_panel.set_feedback(text, is_error)

    def _set_record_button_state(self, recording: bool) -> None:
        self.main_panel.set_recording(recording)
        if hasattr(self, "compact_panel"):
            self.compact_panel.set_recording(recording)

    def _set_result_text(self, text: str) -> None:
        self.main_panel.set_result_text(text)
        if hasattr(self, "compact_panel"):
            self.compact_panel.set_text(text)

    def _clear_result_text(self) -> None:
        self._set_result_text("")

    def _current_result_text(self) -> str:
        if hasattr(self, "compact_panel") and self.compact_panel.isVisible():
            return self.compact_panel.text()
        return self.main_panel.current_result_text()

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.main_panel.set_actions_enabled(enabled)

    def _update_context_badges(self) -> None:
        if not hasattr(self, "main_panel"):
            return
        self.main_panel.set_badges(self._provider_label(), self._language_label())
        self._update_compact_translation_button()

    def _set_connection_state(self, text: str) -> None:
        self.main_panel.set_connection_state(text)
        self._refresh_diagnostics()

    def refresh_config_checks(self) -> None:
        self.microphone_available = self._detect_microphone_available()
        self.config_check_panel.set_items(
            build_config_checks(
                self.settings,
                microphone_available=self.microphone_available,
                hotkey_available=self.hotkey_active,
            )
        )

    @staticmethod
    def _detect_microphone_available() -> bool:
        try:
            import sounddevice as sd

            sd.query_devices(kind="input")
        except Exception:
            return False
        return True

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
        return process_text_pipeline(
            text,
            mode=self.settings.postprocess_mode,
            enabled=self.settings.postprocess_enabled,
            dictionary_enabled=self.settings.dictionary_correction_enabled,
            ai_polish_enabled=self.settings.ai_polish_enabled,
            ai_api_base_url=self.settings.ai_polish_api_base_url,
            ai_api_key=self.settings.ai_polish_api_key,
            ai_model=self.settings.ai_polish_model,
        )

    def _mark_diagnostic_start(self) -> None:
        self.diagnostics.start()
        self._refresh_diagnostics()

    def _mark_diagnostic_first_text(self) -> None:
        self.diagnostics.mark_first_text()
        self._refresh_diagnostics()

    def _mark_diagnostic_stop(self) -> None:
        self.diagnostics.mark_stop()
        self._refresh_diagnostics()

    def _mark_diagnostic_finish(self) -> None:
        self.diagnostics.mark_finish()
        self._refresh_diagnostics()

    def _set_diagnostic_error(self, message: str) -> None:
        self.diagnostics.set_error(message)
        self._refresh_diagnostics()

    def _refresh_diagnostics(self) -> None:
        if not hasattr(self, "diagnostics_panel"):
            return

        state = self.main_panel.connection_state() if hasattr(self, "main_panel") else "-"
        self.diagnostics_panel.set_values(diagnostic_values(self.settings, self.diagnostics, state))

    def show_compact_panel(self) -> None:
        if not hasattr(self, "compact_panel"):
            return
        self.compact_panel.show()
        self._position_compact_panel()
        self.compact_panel.raise_()
        self.compact_panel.activateWindow()

    @Slot()
    def tidy_current_text(self) -> None:
        self._set_result_text(tidy_text(self._current_result_text()))
        self._set_feedback("文本已整理")

    @Slot()
    def translate_current_text(self) -> None:
        text = self._current_result_text().strip()
        if not text:
            self._set_feedback("没有可翻译的文本")
            return
        if self.translation_controller.is_running():
            self._set_feedback("正在翻译，请稍候")
            return

        self.apply_settings_from_form(save=False, restart_hotkey=False)
        request = TranslationRequest(
            text=text,
            source_language=self.settings.language,
            api_base_url=self.settings.translation_api_base_url,
            api_key=self.settings.translation_api_key,
            model=self.settings.translation_model,
        )
        if not self.translation_controller.start(request):
            self._set_feedback("正在翻译，请稍候")
            return
        self._set_feedback(f"正在{translation_button_label(self.settings.language)}")
        self._set_status("翻译中：正在调用云端翻译模型")
        self._set_floating_bar_state("processing", "翻译中", text)

    @Slot(str)
    def on_translation_finished(self, translated: str) -> None:
        self._set_result_text(translated)
        self.preview_text = translated
        self._set_feedback(f"已完成{translation_button_label(self.settings.language)}")
        self._set_status("完成：翻译结果已生成")
        self._set_floating_bar_state("success", "已翻译", translated, can_insert=True)

    @Slot(str)
    def on_translation_error(self, message: str) -> None:
        self._show_error(f"翻译失败：{message}")
        self._set_status("错误：翻译失败")
        self._set_floating_bar_state("error", "翻译失败", message)

    @Slot()
    def copy_text(self) -> None:
        result = self.input_controller.copy(self._current_result_text())
        if not result.ok:
            self._show_error(result.error)
            return
        self._set_feedback(result.message)
        self._set_status(result.message)

    @Slot()
    def paste_text(self) -> None:
        result = self.input_controller.paste(self._current_result_text())
        if not result.ok:
            self._show_error(result.error)
            return
        self._set_feedback(result.message)
        self._set_floating_bar_state("idle", "待机", "已插入")
        self._set_status(result.message)

    @Slot()
    def insert_preview_text(self) -> None:
        result = self.input_controller.insert_preview(self._current_result_text(), self.preview_text)
        if not result.ok:
            if result.error == "没有可插入的预览文本":
                self._set_floating_bar_state("idle", "待机", result.error)
                return
            self._show_error(result.error)
            return
        self._set_feedback(result.message)
        self._set_status("预览文本已插入到当前输入位置")
        self._set_floating_bar_state("idle", "待机", "已插入")

    @Slot()
    def save_settings(self) -> None:
        self.apply_settings_from_form(save=True, restart_hotkey=True)
        self._update_context_badges()
        self.settings_panel.mark_saved()
        self._set_feedback("设置已保存，下一次识别会使用新配置")
        self._set_status("设置已保存")

    def apply_settings_from_form(self, save: bool, restart_hotkey: bool) -> None:
        previous_settings = self.settings
        self.settings = self.settings_panel.to_settings(sample_rate=self.settings.sample_rate)
        self._update_context_badges()
        self.settings_panel.refresh_hints()
        if save:
            self.settings_store.save(self.settings)
        if engine_settings_changed(previous_settings, self.settings):
            self.asr_engine = self._build_engine()
            self.recognition.set_engine(self.asr_engine)
        self.history.limit = self.settings.history_limit
        self.refresh_config_checks()
        self._refresh_diagnostics()
        if restart_hotkey:
            self.hotkey.stop()
            self.hotkey = GlobalHotkey(self.settings.hotkey, self.hotkey_pressed.emit)
            self.hotkey_active = self.hotkey.start()
            self.refresh_config_checks()

    def _refresh_history(self) -> None:
        self.main_panel.set_history_items(item.text for item in self.history.list())

    def _show_error(self, message: str) -> None:
        safe_message = user_error_message(message)
        self._set_diagnostic_error(safe_message)
        self._set_feedback(safe_message, is_error=True)
        self._set_floating_bar_state("error", "错误", safe_message)

    def _show_notice(self, message: str) -> None:
        self._set_feedback(message)
        self._set_floating_bar_state("idle", "待机", message)

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
        return provider_label(self.settings)

    def _language_label(self) -> str:
        return language_label(self.settings)

    def closeEvent(self, event) -> None:
        self.hide()
        self.floating_bar.show()
        if not self._close_tip_shown and self.tray.isVisible():
            self.tray.showMessage(
                "XinVoice 仍在运行",
                "窗口已隐藏，悬浮球仍可继续控制录音。双击悬浮球或托盘图标可恢复。",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            self._close_tip_shown = True
        event.ignore()

    def quit_app(self) -> None:
        self.recognition.stop_all()
        self.hotkey.stop()
        self.floating_bar.hide()
        if hasattr(self, "compact_panel"):
            self.compact_panel.hide()
        self.tray.hide()
        QApplication.quit()
