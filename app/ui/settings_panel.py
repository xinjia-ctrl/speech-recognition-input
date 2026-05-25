from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QWidget,
)

from app.config_check import ASR_API_MODEL_RULES, TRANSLATION_MODEL_RULES, WEBSOCKET_MODEL_RULES, model_match_hint
from app.config import Settings


Preset = tuple[str, str]


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


ASR_API_URL_PRESETS: tuple[Preset, ...] = (
    ("OpenAI | https://api.openai.com/v1/audio/transcriptions", "https://api.openai.com/v1/audio/transcriptions"),
    ("硅基流动 | https://api.siliconflow.com/v1/audio/transcriptions", "https://api.siliconflow.com/v1/audio/transcriptions"),
    ("硅基流动 | https://api.siliconflow.cn/v1/audio/transcriptions", "https://api.siliconflow.cn/v1/audio/transcriptions"),
    (
        "百炼 Qwen-ASR | https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    ),
)

ASR_API_MODEL_PRESETS: tuple[Preset, ...] = (
    ("OpenAI | whisper-1", "whisper-1"),
    ("OpenAI | gpt-4o-mini-transcribe", "gpt-4o-mini-transcribe"),
    ("OpenAI | gpt-4o-transcribe", "gpt-4o-transcribe"),
    ("硅基流动 | FunAudioLLM/SenseVoiceSmall", "FunAudioLLM/SenseVoiceSmall"),
    ("百炼 Qwen-ASR | qwen3-asr-flash", "qwen3-asr-flash"),
)

TRANSLATION_API_URL_PRESETS: tuple[Preset, ...] = (
    ("OpenAI | https://api.openai.com/v1/chat/completions", "https://api.openai.com/v1/chat/completions"),
    ("硅基流动 | https://api.siliconflow.cn/v1/chat/completions", "https://api.siliconflow.cn/v1/chat/completions"),
    ("硅基流动 | https://api.siliconflow.com/v1/chat/completions", "https://api.siliconflow.com/v1/chat/completions"),
    (
        "百炼 | https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    ),
    ("DeepSeek | https://api.deepseek.com/chat/completions", "https://api.deepseek.com/chat/completions"),
    ("DeepInfra | https://api.deepinfra.com/v1/openai/chat/completions", "https://api.deepinfra.com/v1/openai/chat/completions"),
)

TRANSLATION_MODEL_PRESETS: tuple[Preset, ...] = (
    ("OpenAI | gpt-4o-mini", "gpt-4o-mini"),
    ("OpenAI | gpt-4o", "gpt-4o"),
    ("硅基流动 | Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct"),
    ("硅基流动 | Qwen/Qwen2.5-1.5B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct"),
    ("硅基流动 | Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-14B-Instruct"),
    ("百炼 | qwen-turbo", "qwen-turbo"),
    ("百炼 | qwen-plus", "qwen-plus"),
    ("DeepSeek | deepseek-chat", "deepseek-chat"),
    ("DeepSeek | deepseek-reasoner", "deepseek-reasoner"),
    ("DeepInfra | meta-llama/Meta-Llama-3.1-8B-Instruct", "meta-llama/Meta-Llama-3.1-8B-Instruct"),
)

WEBSOCKET_URL_PRESETS: tuple[Preset, ...] = (
    ("百炼 | wss://dashscope.aliyuncs.com/api-ws/v1/inference", "wss://dashscope.aliyuncs.com/api-ws/v1/inference"),
)

WEBSOCKET_MODEL_PRESETS: tuple[Preset, ...] = (
    ("百炼 | paraformer-realtime-v2", "paraformer-realtime-v2"),
    ("百炼 | paraformer-realtime-v1", "paraformer-realtime-v1"),
)

class SettingsPanel(QScrollArea):
    save_requested = Signal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        page = QWidget()
        page.setObjectName("settingsPage")
        self.setWidget(page)

        form = QFormLayout(page)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.provider_combo = NoWheelComboBox()
        self.provider_combo.addItems(["local", "api", "websocket"])
        self.provider_combo.setCurrentText(settings.asr_provider)

        self.model_combo = NoWheelComboBox()
        self.model_combo.addItems(["tiny", "base", "small"])
        if settings.model_size not in {"tiny", "base", "small"}:
            self.model_combo.addItem(settings.model_size)
        self.model_combo.setCurrentText(settings.model_size)

        self.model_path_input = QLineEdit(settings.model_path)
        self.model_path_input.setPlaceholderText("更大模型请填写已下载的本地模型目录")

        self.language_input = NoWheelComboBox()
        self.language_input.addItems(["zh", "en"])
        self.language_input.setCurrentText(settings.language if settings.language in {"zh", "en"} else "zh")

        self.api_base_url_input = self._build_editable_combo(
            settings.api_base_url,
            ASR_API_URL_PRESETS,
            "选择常用 HTTP 识别地址或手动填写",
        )
        self.api_key_input = QLineEdit(settings.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("云端 API Key，settings.json 已被忽略")
        self.api_model_input = self._build_editable_combo(
            settings.api_model,
            ASR_API_MODEL_PRESETS,
            "选择常用 HTTP 识别模型或手动填写",
        )
        self.api_model_hint = self._create_config_hint_label()
        self.fallback_to_local_check = QCheckBox()
        self.fallback_to_local_check.setChecked(settings.fallback_to_local)

        self.translation_api_base_url_input = self._build_editable_combo(
            settings.translation_api_base_url,
            TRANSLATION_API_URL_PRESETS,
            "选择常用翻译地址或手动填写 OpenAI 兼容地址",
        )
        self.translation_api_key_input = QLineEdit(settings.translation_api_key)
        self.translation_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.translation_api_key_input.setPlaceholderText("翻译 API Key，settings.json 已被忽略")
        self.translation_model_input = self._build_editable_combo(
            settings.translation_model,
            TRANSLATION_MODEL_PRESETS,
            "选择常用翻译模型或手动填写模型名",
        )
        self.translation_model_hint = self._create_config_hint_label()

        self.local_beam_size_input = QSpinBox()
        self.local_beam_size_input.setRange(1, 5)
        self.local_beam_size_input.setValue(settings.local_beam_size)
        self.local_beam_size_input.setToolTip("数值越小越快，输入法场景建议保持 1")

        self.websocket_url_input = self._build_editable_combo(
            settings.websocket_url,
            WEBSOCKET_URL_PRESETS,
            "选择常用 WebSocket 地址或手动填写",
        )
        self.websocket_api_key_input = QLineEdit(settings.websocket_api_key)
        self.websocket_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.websocket_api_key_input.setPlaceholderText("实时识别 API Key，留空则尝试使用 API Key")
        self.websocket_model_input = self._build_editable_combo(
            settings.websocket_model,
            WEBSOCKET_MODEL_PRESETS,
            "选择常用实时识别模型或手动填写",
        )
        self.websocket_model_hint = self._create_config_hint_label()

        self.realtime_chunk_input = QSpinBox()
        self.realtime_chunk_input.setRange(50, 2000)
        self.realtime_chunk_input.setSingleStep(50)
        self.realtime_chunk_input.setValue(settings.realtime_chunk_ms)

        self.websocket_final_wait_input = QSpinBox()
        self.websocket_final_wait_input.setRange(100, 5000)
        self.websocket_final_wait_input.setSingleStep(100)
        self.websocket_final_wait_input.setValue(settings.websocket_final_wait_ms)
        self.websocket_final_wait_input.setToolTip("停止录音后等待最终结果的时间，越短响应越快")

        self.hotkey_input = QLineEdit(settings.hotkey)
        self.auto_insert_check = QCheckBox()
        self.auto_insert_check.setChecked(settings.auto_insert)
        self.preview_before_insert_check = QCheckBox()
        self.preview_before_insert_check.setChecked(settings.preview_before_insert)
        self.postprocess_check = QCheckBox()
        self.postprocess_check.setChecked(settings.postprocess_enabled)
        self.dictionary_correction_check = QCheckBox()
        self.dictionary_correction_check.setChecked(settings.dictionary_correction_enabled)

        self.postprocess_mode_combo = NoWheelComboBox()
        self.postprocess_mode_combo.addItems(["chat", "document", "code"])
        if settings.postprocess_mode not in {"chat", "document", "code"}:
            self.postprocess_mode_combo.addItem(settings.postprocess_mode)
        self.postprocess_mode_combo.setCurrentText(settings.postprocess_mode)

        self.ai_polish_check = QCheckBox()
        self.ai_polish_check.setChecked(settings.ai_polish_enabled)
        self.ai_polish_api_base_url_input = self._build_editable_combo(
            settings.ai_polish_api_base_url,
            TRANSLATION_API_URL_PRESETS,
            "选择 AI 润色地址或手动填写 OpenAI 兼容地址",
        )
        self.ai_polish_api_key_input = QLineEdit(settings.ai_polish_api_key)
        self.ai_polish_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_polish_api_key_input.setPlaceholderText("AI 润色 API Key，settings.json 已被忽略")
        self.ai_polish_model_input = self._build_editable_combo(
            settings.ai_polish_model,
            TRANSLATION_MODEL_PRESETS,
            "选择 AI 润色模型或手动填写模型名",
        )

        self.history_limit_input = QSpinBox()
        self.history_limit_input.setRange(1, 100)
        self.history_limit_input.setValue(settings.history_limit)

        self.save_settings_button = QPushButton("保存设置")
        self.save_settings_button.setObjectName("saveSettingsButton")
        self.save_settings_button.clicked.connect(self.save_requested.emit)

        self._connect_hint_refresh()
        self._add_rows(form)
        self.refresh_hints()

    def to_settings(self, sample_rate: int) -> Settings:
        return Settings(
            asr_provider=self.provider_combo.currentText(),
            model_size=self.model_combo.currentText(),
            model_path=self.model_path_input.text().strip(),
            language=self.language_input.currentText(),
            api_base_url=self._combo_value(self.api_base_url_input),
            api_key=self.api_key_input.text().strip(),
            api_model=self._combo_value(self.api_model_input),
            fallback_to_local=self.fallback_to_local_check.isChecked(),
            translation_api_base_url=self._combo_value(self.translation_api_base_url_input),
            translation_api_key=self.translation_api_key_input.text().strip(),
            translation_model=self._combo_value(self.translation_model_input),
            local_beam_size=self.local_beam_size_input.value(),
            websocket_url=self._combo_value(self.websocket_url_input),
            websocket_api_key=self.websocket_api_key_input.text().strip(),
            websocket_model=self._combo_value(self.websocket_model_input),
            realtime_chunk_ms=self.realtime_chunk_input.value(),
            websocket_final_wait_ms=self.websocket_final_wait_input.value(),
            hotkey=self.hotkey_input.text().strip() or "ctrl+alt+space",
            auto_insert=self.auto_insert_check.isChecked(),
            preview_before_insert=self.preview_before_insert_check.isChecked(),
            postprocess_enabled=self.postprocess_check.isChecked(),
            postprocess_mode=self.postprocess_mode_combo.currentText(),
            dictionary_correction_enabled=self.dictionary_correction_check.isChecked(),
            ai_polish_enabled=self.ai_polish_check.isChecked(),
            ai_polish_api_base_url=self._combo_value(self.ai_polish_api_base_url_input),
            ai_polish_api_key=self.ai_polish_api_key_input.text().strip(),
            ai_polish_model=self._combo_value(self.ai_polish_model_input),
            history_limit=self.history_limit_input.value(),
            sample_rate=sample_rate,
        )

    def refresh_hints(self, *_args: object) -> None:
        hints = (
            (
                self.api_model_hint,
                self._combo_value(self.api_base_url_input),
                self._combo_value(self.api_model_input),
                ASR_API_MODEL_RULES,
            ),
            (
                self.translation_model_hint,
                self._combo_value(self.translation_api_base_url_input),
                self._combo_value(self.translation_model_input),
                TRANSLATION_MODEL_RULES,
            ),
            (
                self.websocket_model_hint,
                self._combo_value(self.websocket_url_input),
                self._combo_value(self.websocket_model_input),
                WEBSOCKET_MODEL_RULES,
            ),
        )
        for label, url, model, rules in hints:
            hint = model_match_hint(url, model, rules)
            label.setText(hint)
            label.setVisible(bool(hint))

    def _connect_hint_refresh(self) -> None:
        for combo in (self.api_base_url_input, self.api_model_input):
            combo.currentTextChanged.connect(self.refresh_hints)
        for combo in (self.translation_api_base_url_input, self.translation_model_input):
            combo.currentTextChanged.connect(self.refresh_hints)
        for combo in (self.websocket_url_input, self.websocket_model_input):
            combo.currentTextChanged.connect(self.refresh_hints)

    def _add_rows(self, form: QFormLayout) -> None:
        form.addRow("识别模式", self.provider_combo)
        form.addRow("本地模型大小", self.model_combo)
        form.addRow("本地模型路径", self.model_path_input)
        form.addRow("识别语言", self.language_input)
        form.addRow("API 地址", self.api_base_url_input)
        form.addRow("API Key", self.api_key_input)
        form.addRow("API 模型", self.api_model_input)
        form.addRow("", self.api_model_hint)
        form.addRow("API 失败本地兜底", self.fallback_to_local_check)
        form.addRow("翻译 API 地址", self.translation_api_base_url_input)
        form.addRow("翻译 API Key", self.translation_api_key_input)
        form.addRow("翻译模型", self.translation_model_input)
        form.addRow("", self.translation_model_hint)
        form.addRow("本地搜索宽度", self.local_beam_size_input)
        form.addRow("WebSocket 地址", self.websocket_url_input)
        form.addRow("WebSocket API Key", self.websocket_api_key_input)
        form.addRow("WebSocket 模型", self.websocket_model_input)
        form.addRow("", self.websocket_model_hint)
        form.addRow("实时音频块(ms)", self.realtime_chunk_input)
        form.addRow("实时收尾等待(ms)", self.websocket_final_wait_input)
        form.addRow("全局快捷键", self.hotkey_input)
        form.addRow("识别后自动插入", self.auto_insert_check)
        form.addRow("插入前预览确认", self.preview_before_insert_check)
        form.addRow("规则后处理", self.postprocess_check)
        form.addRow("词典校正", self.dictionary_correction_check)
        form.addRow("文本场景模式", self.postprocess_mode_combo)
        form.addRow("AI 润色", self.ai_polish_check)
        form.addRow("AI 润色 API 地址", self.ai_polish_api_base_url_input)
        form.addRow("AI 润色 API Key", self.ai_polish_api_key_input)
        form.addRow("AI 润色模型", self.ai_polish_model_input)
        form.addRow("历史记录条数", self.history_limit_input)
        form.addRow(self.save_settings_button)

    @staticmethod
    def _build_editable_combo(
        current_value: str,
        presets: tuple[Preset, ...],
        placeholder: str,
    ) -> QComboBox:
        combo = NoWheelComboBox()
        combo.setEditable(True)
        current_index = -1
        for index, (label, value) in enumerate(presets):
            combo.addItem(label, value)
            if current_value == value:
                current_index = index
        if current_value and current_index < 0:
            combo.addItem(current_value, current_value)
            current_index = combo.count() - 1
        if current_index >= 0:
            combo.setCurrentIndex(current_index)
        else:
            combo.setCurrentText("")
        line_edit = combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText(placeholder)
        return combo

    @staticmethod
    def _combo_value(combo: QComboBox) -> str:
        current_text = combo.currentText().strip()
        for index in range(combo.count()):
            if combo.itemText(index) == current_text:
                data = combo.itemData(index)
                if isinstance(data, str):
                    return data.strip()
        return current_text

    def mark_saved(self) -> None:
        self.save_settings_button.setText("已保存")
        self.save_settings_button.setProperty("saved", True)
        self.save_settings_button.style().unpolish(self.save_settings_button)
        self.save_settings_button.style().polish(self.save_settings_button)
        QTimer.singleShot(1400, self._restore_save_button)

    def _restore_save_button(self) -> None:
        self.save_settings_button.setText("保存设置")
        self.save_settings_button.setProperty("saved", False)
        self.save_settings_button.style().unpolish(self.save_settings_button)
        self.save_settings_button.style().polish(self.save_settings_button)

    @staticmethod
    def _create_config_hint_label() -> QLabel:
        label = QLabel("")
        label.setObjectName("configHintLabel")
        label.setWordWrap(True)
        label.setVisible(False)
        return label
