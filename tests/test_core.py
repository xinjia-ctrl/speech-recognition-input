import os
import unittest
from pathlib import Path

from app.config import Settings, SettingsStore
from app.asr import AsrEngine, WebSocketRealtimeAsrClient
from app.history import HistoryStore
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

    def test_settings_round_trip_api_fields(self) -> None:
        path = self.tmp_dir / "settings.json"
        store = SettingsStore(path)
        store.save(
            Settings(
                asr_provider="api",
                api_base_url="https://example.com/asr",
                api_key="test-key",
                api_model="speech-model",
                websocket_url="wss://example.com/realtime",
                websocket_api_key="websocket-test-key",
                websocket_model="realtime-model",
                realtime_chunk_ms=100,
            )
        )

        loaded = store.load()

        self.assertEqual(loaded.asr_provider, "api")
        self.assertEqual(loaded.api_base_url, "https://example.com/asr")
        self.assertEqual(loaded.api_key, "test-key")
        self.assertEqual(loaded.api_model, "speech-model")
        self.assertEqual(loaded.websocket_url, "wss://example.com/realtime")
        self.assertEqual(loaded.websocket_api_key, "websocket-test-key")
        self.assertEqual(loaded.websocket_model, "realtime-model")
        self.assertEqual(loaded.realtime_chunk_ms, 100)

    def test_api_payload_text_extraction_supports_common_shapes(self) -> None:
        self.assertEqual(AsrEngine._extract_text_from_api_payload({"text": "你好"}), "你好")
        self.assertEqual(
            AsrEngine._extract_text_from_api_payload({"data": {"text": "你好"}}),
            "你好",
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


if __name__ == "__main__":
    unittest.main()
