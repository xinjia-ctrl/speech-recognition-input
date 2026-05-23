import os
import unittest
from pathlib import Path

from app.config import Settings, SettingsStore
from app.asr import AsrEngine
from app.history import HistoryStore
from app.text_tools import redact_secret, tidy_text, to_simplified_chinese


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
            )
        )

        loaded = store.load()

        self.assertEqual(loaded.asr_provider, "api")
        self.assertEqual(loaded.api_base_url, "https://example.com/asr")
        self.assertEqual(loaded.api_key, "test-key")
        self.assertEqual(loaded.api_model, "speech-model")

    def test_api_payload_text_extraction_supports_common_shapes(self) -> None:
        self.assertEqual(AsrEngine._extract_text_from_api_payload({"text": "你好"}), "你好")
        self.assertEqual(
            AsrEngine._extract_text_from_api_payload({"data": {"text": "你好"}}),
            "你好",
        )

    def test_history_limit(self) -> None:
        store = HistoryStore(self.tmp_dir / "history.json", limit=2)

        store.add("第一句")
        store.add("第二句")
        items = store.add("第三句")

        self.assertEqual([item.text for item in items], ["第三句", "第二句"])


if __name__ == "__main__":
    unittest.main()
