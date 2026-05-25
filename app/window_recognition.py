from __future__ import annotations

from PySide6.QtCore import Slot

from app.asr import TranscriptionResult, is_no_speech_message
from app.controllers import RecordingActionResult


class RecognitionWindowMixin:
    @Slot()
    def toggle_compact_recording(self) -> None:
        self.show_compact_panel()
        self.toggle_recording(show_panel=False)

    @Slot()
    def toggle_recording(self, show_panel: bool = True) -> None:
        if show_panel:
            self.show_window()
        if self.recognition.is_realtime_running:
            self.stop_websocket_realtime()
            return
        if self.recognition.is_file_transcribing:
            self._set_status("识别中，请稍候")
            return

        if self.recognition.is_recording:
            self.stop_recording()
            return

        self.apply_settings_from_form(save=False, restart_hotkey=False)
        if self.settings.asr_provider == "websocket":
            self.start_websocket_realtime()
            return

        self.start_recording()

    def start_websocket_realtime(self) -> None:
        self._clear_result_text()
        self.preview_text = ""
        self._mark_diagnostic_start()
        self.recognition.start_realtime()

    @Slot()
    def on_realtime_started(self) -> None:
        self._set_record_button_state(recording=True)
        self._set_actions_enabled(False)
        self._set_connection_state("连接中")
        self._set_floating_bar_state("listening", "监听中", "等待你开始说话")
        self._set_feedback("实时模式已启动，正在等待语音输入")
        self._set_status("实时识别中：正在通过 WebSocket 边说边出字")

    def stop_websocket_realtime(self) -> None:
        self.recognition.stop_realtime()

    @Slot()
    def on_realtime_stopping(self) -> None:
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
        if is_no_speech_message(message):
            self._show_notice("未识别到声音，请靠近麦克风后再试")
            self._set_record_button_state(recording=False)
            self._set_actions_enabled(True)
            self._set_connection_state("待机")
            self._set_status("待机：本次没有识别到声音")
            return

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
        if self.recognition.realtime_failed:
            return

        text = self._postprocess_text(self._current_result_text().strip())
        if text:
            self._set_result_text(text)
        has_text = bool(text)
        if has_text:
            self.history.add(text)
            self._refresh_history()
            self.preview_text = text
            if self.settings.auto_insert and not self.settings.preview_before_insert:
                self.paste_text()
            else:
                self._set_floating_bar_state("success", "待确认", text, can_insert=True)
        else:
            self._show_notice("未识别到声音，请靠近麦克风后再试")
        self._set_record_button_state(recording=False)
        self._set_actions_enabled(True)
        self._set_connection_state("待机")
        self._mark_diagnostic_finish()
        if has_text:
            self._set_feedback("实时识别已完成，可以确认插入")
            self._set_status("完成：WebSocket 实时识别已结束")
        else:
            self._set_status("待机：本次没有识别到声音")

    def start_recording(self) -> None:
        self.recognition.start_recording()

    @Slot()
    def on_recording_started(self) -> None:
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
        self.recognition.stop_recording()

    @Slot(object)
    def on_recording_failed(self, result: RecordingActionResult) -> None:
        if result.is_no_speech:
            self._show_notice("未识别到声音，请靠近麦克风后再试")
            self._mark_diagnostic_finish()
            self._set_record_button_state(recording=False)
            self._set_actions_enabled(True)
            self._set_connection_state("待机")
            self._set_status("待机：本次没有识别到声音")
            return
        self._set_diagnostic_error(result.error)
        self._mark_diagnostic_finish()
        self._show_error(result.error)
        self._set_record_button_state(recording=False)
        self._set_actions_enabled(True)
        self._set_connection_state("错误")

    @Slot(str)
    def on_recording_stopped(self, _audio_path: str) -> None:
        self._mark_diagnostic_stop()
        self._set_record_button_state(recording=False)

    @Slot(str)
    def on_file_transcription_started(self, _model_name: str) -> None:
        self._set_actions_enabled(False)
        self._set_connection_state("识别中")
        self.on_audio_level(0.0)
        self._set_floating_bar_state("processing", "处理中", "正在生成文字")
        self._set_feedback("录音已结束，正在生成文字")
        self._set_status(f"识别中：正在使用{self._provider_label()}转写")

    @Slot(str)
    def on_file_fallback(self, message: str) -> None:
        self._set_feedback(message)
        self._set_status("云端识别失败：正在使用本地模型兜底")
        self._set_floating_bar_state("processing", "本地兜底", "正在使用本地模型重新识别")

    @Slot(str)
    def on_transcription_partial(self, text: str) -> None:
        self._set_result_text(text)
        self.preview_text = text
        self._mark_diagnostic_first_text()
        self._set_floating_bar_state("success", "说话中", text)

    @Slot(object)
    def on_transcription_finished(self, result: TranscriptionResult) -> None:
        if result.error:
            if is_no_speech_message(result.error):
                self._show_notice("未识别到声音，请靠近麦克风后再试")
                self._set_actions_enabled(True)
                self._set_connection_state("待机")
                self._set_status("待机：本次没有识别到声音")
                self._mark_diagnostic_finish()
                return
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
        else:
            self._show_notice("未识别到声音，请靠近麦克风后再试")
            self._set_actions_enabled(True)
            self._set_connection_state("待机")
            self._set_status(
                f"完成：{self._provider_label()} {result.model_name}，没有识别到声音"
            )
            self._mark_diagnostic_finish()
            return
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
