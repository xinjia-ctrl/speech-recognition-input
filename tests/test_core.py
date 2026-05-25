import os
import unittest
from pathlib import Path

from app.config_check import build_config_checks, model_match_hint, TRANSLATION_MODEL_RULES
from app.config import Settings, SettingsStore
from app.audio import RecordingError
from app.asr import (
    AsrEngine,
    AsrStreamEvent,
    FallbackAsrProvider,
    HttpAsrProvider,
    LocalWhisperProvider,
    RealtimeAsrConfig,
    TranscriptionResult,
    UnifiedAsrEngine,
    WebSocketRealtimeAsrClient,
    WebSocketRealtimeProvider,
    build_asr_provider,
    is_no_speech_message,
)
from app.controllers import InputController, RecognitionSessionController, RecordingController, TranslationRequest
from app.errors import DependencyMissingError, ErrorKind, InputActionError, user_error_message
from app.history import HistoryRepository, HistoryStore, JsonHistoryRepository
from app.session_state import SessionDiagnostics
from app.text_pipeline import (
    DictionaryCorrectionStage,
    TextPipelineOptions,
    TextProcessingPipeline,
    _extract_chat_text,
    process_text_pipeline,
)
from app.text_translate import (
    _extract_translation_text,
    _normalize_translation_result,
    translate_text,
    translation_button_label,
)
from app.text_tools import (
    filter_text_by_language,
    redact_secret,
    remove_cjk_false_positive_text,
    tidy_text,
    to_simplified_chinese,
)


class CoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(".test_tmp") / f"{os.getpid()}_{self.id().replace('.', '_')}"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        for file in self.tmp_dir.glob("*.json"):
            file.unlink(missing_ok=True)

    def test_tidy_text_normalizes_spaces_and_punctuation(self) -> None:
        self.assertEqual(tidy_text("  你好   world , test. "), "你好 world， test。")

    def test_to_simplified_chinese_converts_common_traditional_text(self) -> None:
        self.assertEqual(to_simplified_chinese("語音輸入軟體，開發測試"), "语音输入软件，开发测试")

    def test_redact_secret_masks_common_api_key_patterns(self) -> None:
        text = "Authorization: Bearer sk-test-secret-token"
        self.assertEqual(redact_secret(text), "Authorization: ***")

    def test_remove_cjk_false_positive_text_filters_kana_and_hangul(self) -> None:
        self.assertEqual(remove_cjk_false_positive_text("你好こんにちは안녕世界"), "你好世界")

    def test_filter_text_by_language_keeps_only_selected_language(self) -> None:
        self.assertEqual(filter_text_by_language("你好abc123，世界", "zh"), "你好123，世界")
        self.assertEqual(filter_text_by_language("hello你好 world", "en"), "hello world")

    def test_settings_round_trip(self) -> None:
        path = self.tmp_dir / "settings.json"
        store = SettingsStore(path)
        store.save(Settings(model_size="small", auto_insert=True, history_limit=3))

        loaded = store.load()

        self.assertEqual(loaded.model_size, "small")
        self.assertTrue(loaded.auto_insert)
        self.assertEqual(loaded.history_limit, 3)

    def test_settings_store_reports_existing_config(self) -> None:
        path = self.tmp_dir / "settings.json"
        store = SettingsStore(path)

        self.assertFalse(store.exists())
        store.save(Settings())

        self.assertTrue(store.exists())

    def test_settings_store_falls_back_when_json_is_corrupt(self) -> None:
        path = self.tmp_dir / "settings.json"
        path.write_text("{bad json", encoding="utf-8")
        store = SettingsStore(path)

        loaded = store.load()

        self.assertEqual(loaded, Settings())

    def test_settings_store_falls_back_when_json_shape_is_invalid(self) -> None:
        path = self.tmp_dir / "settings.json"
        path.write_text('["not", "settings"]', encoding="utf-8")
        store = SettingsStore(path)

        loaded = store.load()

        self.assertEqual(loaded, Settings())

    def test_settings_round_trip_api_fields(self) -> None:
        path = self.tmp_dir / "settings.json"
        store = SettingsStore(path)
        store.save(
            Settings(
                asr_provider="api",
                api_base_url="https://example.com/asr",
                api_key="test-key",
                api_model="speech-model",
                fallback_to_local=False,
                websocket_url="wss://example.com/realtime",
                websocket_api_key="websocket-test-key",
                websocket_model="realtime-model",
                realtime_chunk_ms=100,
                websocket_final_wait_ms=1200,
                preview_before_insert=False,
                postprocess_enabled=False,
                postprocess_mode="code",
                dictionary_correction_enabled=False,
                ai_polish_enabled=True,
                ai_polish_api_base_url="https://example.com/v1/chat/completions",
                ai_polish_api_key="polish-key",
                ai_polish_model="qwen-polish",
                translation_api_base_url="https://example.com/v1/chat/completions",
                translation_api_key="translate-key",
                translation_model="qwen-test",
            )
        )

        loaded = store.load()

        self.assertEqual(loaded.asr_provider, "api")
        self.assertEqual(loaded.api_base_url, "https://example.com/asr")
        self.assertEqual(loaded.api_key, "test-key")
        self.assertEqual(loaded.api_model, "speech-model")
        self.assertFalse(loaded.fallback_to_local)
        self.assertEqual(loaded.websocket_url, "wss://example.com/realtime")
        self.assertEqual(loaded.websocket_api_key, "websocket-test-key")
        self.assertEqual(loaded.websocket_model, "realtime-model")
        self.assertEqual(loaded.realtime_chunk_ms, 100)
        self.assertEqual(loaded.websocket_final_wait_ms, 1200)
        self.assertFalse(loaded.preview_before_insert)
        self.assertFalse(loaded.postprocess_enabled)
        self.assertEqual(loaded.postprocess_mode, "code")
        self.assertFalse(loaded.dictionary_correction_enabled)
        self.assertTrue(loaded.ai_polish_enabled)
        self.assertEqual(loaded.ai_polish_api_base_url, "https://example.com/v1/chat/completions")
        self.assertEqual(loaded.ai_polish_api_key, "polish-key")
        self.assertEqual(loaded.ai_polish_model, "qwen-polish")
        self.assertEqual(loaded.translation_api_base_url, "https://example.com/v1/chat/completions")
        self.assertEqual(loaded.translation_api_key, "translate-key")
        self.assertEqual(loaded.translation_model, "qwen-test")

    def test_model_match_hint_detects_provider_mismatch(self) -> None:
        self.assertIn(
            "qwen-turbo",
            model_match_hint(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "Qwen/Qwen2.5-7B-Instruct",
                TRANSLATION_MODEL_RULES,
            ),
        )
        self.assertEqual(
            model_match_hint(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "qwen-plus",
                TRANSLATION_MODEL_RULES,
            ),
            "",
        )

    def test_build_config_checks_marks_active_api_missing_as_error_without_fallback(self) -> None:
        checks = build_config_checks(
            Settings(asr_provider="api", fallback_to_local=False),
            microphone_available=True,
            hotkey_available=True,
        )
        http_check = next(item for item in checks if item.key == "http_asr")

        self.assertEqual(http_check.status, "error")
        self.assertIn("地址", http_check.detail)

    def test_build_config_checks_warns_when_api_missing_with_fallback(self) -> None:
        checks = build_config_checks(Settings(asr_provider="api"), microphone_available=True, hotkey_available=True)
        http_check = next(item for item in checks if item.key == "http_asr")

        self.assertEqual(http_check.status, "warning")
        self.assertIn("本地兜底", http_check.message)

    def test_build_config_checks_marks_complete_translation_as_ok(self) -> None:
        checks = build_config_checks(
            Settings(
                translation_api_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                translation_api_key="test-key",
                translation_model="qwen-plus",
            )
        )
        translation_check = next(item for item in checks if item.key == "translation")

        self.assertEqual(translation_check.status, "ok")

    def test_text_pipeline_removes_fillers_and_adds_question_mark(self) -> None:
        self.assertEqual(process_text_pipeline("呃 这个 能不能 帮我 看一下", "chat"), "能不能 帮我 看一下？")

    def test_text_pipeline_supports_code_mode_replacements(self) -> None:
        self.assertEqual(process_text_pipeline("i f 语句", "code"), "if :。")

    def test_text_pipeline_applies_dictionary_before_cleanup(self) -> None:
        self.assertEqual(process_text_pipeline("百练 web socket 能不能用", mode="chat"), "百炼 WebSocket 能不能用？")

    def test_dictionary_stage_can_be_disabled(self) -> None:
        pipeline = TextProcessingPipeline([DictionaryCorrectionStage()])
        options = TextPipelineOptions(dictionary_enabled=False)

        self.assertEqual(pipeline.process("百练", options), "百练")

    def test_ai_polish_payload_text_extraction_supports_common_shapes(self) -> None:
        self.assertEqual(
            _extract_chat_text({"choices": [{"message": {"content": "帮我确认接口是否上线。"}}]}),
            "帮我确认接口是否上线。",
        )

    def test_translate_text_uses_language_direction(self) -> None:
        self.assertEqual(translation_button_label("zh"), "中翻英")
        self.assertEqual(translation_button_label("en"), "英翻中")
        self.assertEqual(translate_text("你好", "zh"), "hello")
        self.assertEqual(translate_text("hello", "en"), "你好")

    def test_translation_payload_text_extraction_supports_common_shapes(self) -> None:
        self.assertEqual(_extract_translation_text({"text": "hello"}), "hello")
        self.assertEqual(
            _extract_translation_text({"choices": [{"message": {"content": "hello"}}]}),
            "hello",
        )
        self.assertEqual(_extract_translation_text({"data": {"output": {"text": "hello"}}}), "hello")

    def test_translation_result_keeps_english_punctuation(self) -> None:
        self.assertEqual(_normalize_translation_result("Hello, world.", "zh"), "Hello, world.")
        self.assertEqual(_normalize_translation_result("語音輸入。", "en"), "语音输入。")

    def test_realtime_config_defaults_to_short_final_wait(self) -> None:
        settings = Settings()
        config = RealtimeAsrConfig(
            websocket_url="wss://example.com/realtime",
            final_wait_seconds=settings.websocket_final_wait_ms / 1000,
        )

        self.assertEqual(settings.websocket_final_wait_ms, 1500)
        self.assertEqual(config.final_wait_seconds, 1.5)

    def test_websocket_stop_keeps_receiver_open_for_final_result(self) -> None:
        client = WebSocketRealtimeAsrClient(RealtimeAsrConfig(websocket_url="wss://example.com/realtime"))

        client.stop()

        self.assertTrue(client._stop_capture_event.is_set())
        self.assertFalse(client._close_receiver_event.is_set())

    def test_local_beam_size_defaults_to_low_latency(self) -> None:
        settings = Settings()
        engine = AsrEngine(beam_size=settings.local_beam_size)

        self.assertEqual(settings.local_beam_size, 1)
        self.assertEqual(engine.beam_size, 1)

    def test_unified_asr_engine_builds_realtime_config_from_settings(self) -> None:
        settings = Settings(
            api_key="fallback-key",
            websocket_url="wss://example.com/realtime",
            websocket_model="realtime-model",
            language="en",
            realtime_chunk_ms=100,
            websocket_final_wait_ms=1200,
        )
        config = UnifiedAsrEngine._build_realtime_config(settings)

        self.assertEqual(config.api_key, "fallback-key")
        self.assertEqual(config.websocket_url, "wss://example.com/realtime")
        self.assertEqual(config.model, "realtime-model")
        self.assertEqual(config.language, "en")
        self.assertEqual(config.chunk_ms, 100)
        self.assertEqual(config.final_wait_seconds, 1.2)

    def test_asr_provider_factory_selects_provider_by_mode(self) -> None:
        self.assertIsInstance(build_asr_provider(Settings(asr_provider="local")), LocalWhisperProvider)
        self.assertIsInstance(build_asr_provider(Settings(asr_provider="api")), FallbackAsrProvider)
        self.assertIsInstance(
            build_asr_provider(Settings(asr_provider="api", fallback_to_local=False)),
            HttpAsrProvider,
        )
        self.assertIsInstance(build_asr_provider(Settings(asr_provider="websocket")), WebSocketRealtimeProvider)

    def test_fallback_provider_uses_local_when_primary_fails(self) -> None:
        class FakeProvider:
            model_name = "cloud"

            def transcribe_file(self, audio_path, emit):
                return TranscriptionResult("", 0.2, self.model_name, "网络失败")

        class FakeLocalProvider:
            model_name = "base"

            def transcribe_file(self, audio_path, emit):
                emit(AsrStreamEvent("final", text="本地结果"))
                return TranscriptionResult("本地结果", 0.5, self.model_name)

        events = []
        provider = FallbackAsrProvider(FakeProvider(), FakeLocalProvider())
        result = provider.transcribe_file("audio.wav", events.append)

        self.assertEqual(result.text, "本地结果")
        self.assertEqual(result.model_name, "cloud -> base")
        self.assertEqual(events[0].kind, "fallback")

    def test_fallback_provider_keeps_no_speech_error_without_retry(self) -> None:
        class NoSpeechProvider:
            model_name = "cloud"

            def transcribe_file(self, audio_path, emit):
                emit(AsrStreamEvent("error", error="No speech detected in audio"))
                return TranscriptionResult("", 0.2, self.model_name, "No speech detected in audio")

        class UnexpectedFallbackProvider:
            model_name = "base"

            def transcribe_file(self, audio_path, emit):
                raise AssertionError("无语音错误不应该触发本地兜底")

        events = []
        provider = FallbackAsrProvider(NoSpeechProvider(), UnexpectedFallbackProvider())
        result = provider.transcribe_file("audio.wav", events.append)

        self.assertTrue(result.error)
        self.assertEqual(events[0].kind, "error")

    def test_unified_asr_engine_delegates_to_selected_provider(self) -> None:
        engine = UnifiedAsrEngine(Settings(asr_provider="websocket", websocket_model="realtime-model"))

        self.assertIsInstance(engine.provider, WebSocketRealtimeProvider)
        self.assertEqual(engine.model_name, "realtime-model")

    def test_asr_stream_event_carries_partial_text(self) -> None:
        event = AsrStreamEvent("partial", text="你好")

        self.assertEqual(event.kind, "partial")
        self.assertEqual(event.text, "你好")

    def test_recognition_session_dispatches_file_events(self) -> None:
        controller = RecognitionSessionController(UnifiedAsrEngine(Settings()), sample_rate=16000)
        partials = []
        fallbacks = []

        controller.file_partial.connect(partials.append)
        controller.file_fallback.connect(fallbacks.append)

        controller._handle_file_event(AsrStreamEvent("partial", text="你好"))
        controller._handle_file_event(AsrStreamEvent("fallback", error="云端失败"))

        self.assertEqual(partials, ["你好"])
        self.assertEqual(fallbacks, ["云端失败"])

    def test_recognition_session_tracks_realtime_error_state(self) -> None:
        controller = RecognitionSessionController(UnifiedAsrEngine(Settings()), sample_rate=16000)
        errors = []

        controller.realtime_error.connect(errors.append)

        controller._handle_realtime_event(AsrStreamEvent("error", error="连接失败"))

        self.assertTrue(controller.realtime_failed)
        self.assertEqual(errors, ["连接失败"])

    def test_no_speech_message_detection(self) -> None:
        self.assertTrue(is_no_speech_message("没有采集到有效音频，请检查麦克风权限"))
        self.assertTrue(is_no_speech_message("No speech detected in audio"))
        self.assertFalse(is_no_speech_message("WebSocket API Key 无效"))

    def test_main_window_errors_are_non_blocking(self) -> None:
        source = Path("app/main_window.py").read_text(encoding="utf-8")

        self.assertNotIn("QMessageBox.warning", source)

    def test_api_payload_text_extraction_supports_common_shapes(self) -> None:
        self.assertEqual(AsrEngine._extract_text_from_api_payload({"text": "你好"}), "你好")
        self.assertEqual(
            AsrEngine._extract_text_from_api_payload({"data": {"text": "你好"}}),
            "你好",
        )
        self.assertEqual(
            AsrEngine._extract_text_from_api_payload({"choices": [{"message": {"content": "你好"}}]}),
            "你好",
        )

    def test_dashscope_qwen_asr_url_normalization(self) -> None:
        self.assertEqual(
            AsrEngine._dashscope_qwen_asr_url(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/audio/transcriptions"
            ),
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
        self.assertEqual(
            AsrEngine._dashscope_qwen_asr_url("https://dashscope.aliyuncs.com/compatible-mode/v1"),
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        )

    def test_websocket_message_parsing_supports_partial_and_final_text(self) -> None:
        self.assertEqual(
            WebSocketRealtimeAsrClient._parse_message('{"partial": "你好"}'),
            ("你好", False),
        )
        self.assertEqual(
            WebSocketRealtimeAsrClient._parse_message('{"text": "你好", "is_final": true}'),
            ("你好", True),
        )

    def test_dashscope_message_parsing_supports_result_generated(self) -> None:
        message = (
            '{"header":{"event":"result-generated"},'
            '"payload":{"output":{"sentence":{"text":"你好","sentence_end":true}}}}'
        )
        self.assertEqual(
            WebSocketRealtimeAsrClient._parse_dashscope_message(message),
            ("result-generated", "你好", True, ""),
        )

    def test_dashscope_url_detection(self) -> None:
        self.assertTrue(
            WebSocketRealtimeAsrClient._is_dashscope_url(
                "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
            )
        )

    def test_history_limit(self) -> None:
        store = HistoryStore(self.tmp_dir / "history.json", limit=2)

        store.add("第一句")
        store.add("第二句")
        items = store.add("第三句")

        self.assertEqual([item.text for item in items], ["第三句", "第二句"])

    def test_json_history_repository_matches_repository_contract(self) -> None:
        repository = JsonHistoryRepository(self.tmp_dir / "history.json", limit=2)

        self.assertIsInstance(repository, HistoryRepository)
        repository.add("第一句")
        repository.clear()

        self.assertEqual(repository.list(), [])

    def test_json_history_repository_returns_empty_list_when_json_is_corrupt(self) -> None:
        path = self.tmp_dir / "history.json"
        path.write_text("{bad json", encoding="utf-8")
        repository = JsonHistoryRepository(path)

        self.assertEqual(repository.list(), [])

    def test_json_history_repository_skips_invalid_items(self) -> None:
        path = self.tmp_dir / "history.json"
        path.write_text(
            '[{"text": "有效记录", "created_at": "2026-05-25T12:00:00"}, {"text": ""}, "bad"]',
            encoding="utf-8",
        )
        repository = JsonHistoryRepository(path)

        self.assertEqual([item.text for item in repository.list()], ["有效记录"])

    def test_session_diagnostics_tracks_redacted_error_and_durations(self) -> None:
        diagnostics = SessionDiagnostics()

        diagnostics.start()
        diagnostics.mark_first_text()
        diagnostics.mark_stop()
        diagnostics.mark_finish()
        diagnostics.set_error("Authorization: Bearer sk-test-secret-token")

        self.assertIsNotNone(diagnostics.first_text_latency)
        self.assertIsNotNone(diagnostics.tail_latency)
        self.assertIsNotNone(diagnostics.total_elapsed)
        self.assertEqual(diagnostics.last_error, "Authorization: ***")

    def test_recording_controller_wraps_no_speech_error(self) -> None:
        class EmptyRecorder:
            is_recording = False

            def start(self, on_level=None) -> None:
                pass

            def stop(self) -> str:
                raise RecordingError("没有采集到有效音频，请检查麦克风权限")

        result = RecordingController(sample_rate=16000, recorder=EmptyRecorder()).stop()

        self.assertFalse(result.ok)
        self.assertTrue(result.is_no_speech)

    def test_typed_error_formats_install_hint_and_redacts_secret(self) -> None:
        error = DependencyMissingError("requests", "pip install -r requirements-cloud.txt")

        self.assertEqual(error.kind, ErrorKind.DEPENDENCY)
        self.assertIn("pip install -r requirements-cloud.txt", user_error_message(error))
        self.assertEqual(user_error_message("Authorization: Bearer sk-test-secret-token"), "Authorization: ***")

    def test_input_controller_inserts_preview_fallback(self) -> None:
        class FakeInjector:
            def __init__(self) -> None:
                self.pasted = ""
                self.excluded_handles = []

            def copy(self, text: str) -> None:
                pass

            def paste(self, text: str) -> None:
                self.pasted = text

            def remember_target_window(self, excluded_handles=()) -> None:
                self.excluded_handles = list(excluded_handles)

        injector = FakeInjector()
        controller = InputController(injector=injector)
        controller.remember_target_window([1, 2])
        result = controller.insert_preview("", "预览文本")

        self.assertTrue(result.ok)
        self.assertEqual(injector.pasted, "预览文本")
        self.assertEqual(injector.excluded_handles, [1, 2])

    def test_input_controller_formats_typed_errors(self) -> None:
        class BrokenInjector:
            def copy(self, text: str) -> None:
                raise InputActionError("复制失败：Authorization: Bearer sk-test-secret-token")

            def paste(self, text: str) -> None:
                raise InputActionError("粘贴失败")

        result = InputController(injector=BrokenInjector()).copy("text")

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "复制失败：Authorization: ***")

    def test_translation_request_groups_translation_inputs(self) -> None:
        request = TranslationRequest(
            text="你好",
            source_language="zh",
            api_base_url="https://example.com/v1/chat/completions",
            api_key="test-key",
            model="qwen-plus",
        )

        self.assertEqual(request.text, "你好")
        self.assertEqual(request.source_language, "zh")

    def test_base_requirements_exclude_optional_asr_dependencies(self) -> None:
        base_requirements = Path("requirements.txt").read_text(encoding="utf-8")

        self.assertNotIn("faster-whisper", base_requirements)
        self.assertNotIn("websocket-client", base_requirements)
        self.assertNotIn("requests", base_requirements)


if __name__ == "__main__":
    unittest.main()
