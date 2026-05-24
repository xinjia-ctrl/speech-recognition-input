from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.config import Settings
from app.ui.settings_panel import (
    ASR_API_MODEL_PRESETS,
    ASR_API_URL_PRESETS,
    TRANSLATION_API_URL_PRESETS,
    TRANSLATION_MODEL_PRESETS,
    WEBSOCKET_MODEL_PRESETS,
    WEBSOCKET_URL_PRESETS,
)


class OnboardingDialog(QDialog):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.setWindowTitle("语音输入器初始化")
        self.setMinimumWidth(520)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("欢迎使用语音输入器")
        title.setObjectName("onboardingTitle")
        subtitle = QLabel("先完成基础配置。后续可以在设置页继续调整模型、API 和文本处理。")
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["local", "api", "websocket"])
        self.provider_combo.setCurrentText(settings.asr_provider)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["zh", "en"])
        self.language_combo.setCurrentText(settings.language if settings.language in {"zh", "en"} else "zh")

        self.local_model_combo = QComboBox()
        self.local_model_combo.addItems(["tiny", "base", "small"])
        local_model = settings.model_size if settings.model_size in {"tiny", "base", "small"} else "base"
        self.local_model_combo.setCurrentText(local_model)

        self.api_url_combo = self._editable_combo(settings.api_base_url, ASR_API_URL_PRESETS)
        self.api_key_input = QLineEdit(settings.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("HTTP 识别 API Key")
        self.api_model_combo = self._editable_combo(settings.api_model, ASR_API_MODEL_PRESETS)

        self.websocket_url_combo = self._editable_combo(settings.websocket_url, WEBSOCKET_URL_PRESETS)
        self.websocket_key_input = QLineEdit(settings.websocket_api_key or settings.api_key)
        self.websocket_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.websocket_key_input.setPlaceholderText("WebSocket API Key")
        self.websocket_model_combo = self._editable_combo(settings.websocket_model, WEBSOCKET_MODEL_PRESETS)

        self.translation_enabled_check = QCheckBox()
        self.translation_enabled_check.setChecked(bool(settings.translation_api_key))
        self.translation_url_combo = self._editable_combo(
            settings.translation_api_base_url,
            TRANSLATION_API_URL_PRESETS,
        )
        self.translation_key_input = QLineEdit(settings.translation_api_key)
        self.translation_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.translation_key_input.setPlaceholderText("翻译 API Key")
        self.translation_model_combo = self._editable_combo(settings.translation_model, TRANSLATION_MODEL_PRESETS)

        self.preview_check = QCheckBox()
        self.preview_check.setChecked(settings.preview_before_insert)
        self.dictionary_check = QCheckBox()
        self.dictionary_check.setChecked(settings.dictionary_correction_enabled)

        form.addRow("识别模式", self.provider_combo)
        form.addRow("识别语言", self.language_combo)
        form.addRow("本地模型", self.local_model_combo)
        form.addRow("HTTP 识别地址", self.api_url_combo)
        form.addRow("HTTP API Key", self.api_key_input)
        form.addRow("HTTP 模型", self.api_model_combo)
        form.addRow("WebSocket 地址", self.websocket_url_combo)
        form.addRow("WebSocket API Key", self.websocket_key_input)
        form.addRow("WebSocket 模型", self.websocket_model_combo)
        form.addRow("启用翻译输入", self.translation_enabled_check)
        form.addRow("翻译地址", self.translation_url_combo)
        form.addRow("翻译 API Key", self.translation_key_input)
        form.addRow("翻译模型", self.translation_model_combo)
        form.addRow("插入前预览", self.preview_check)
        form.addRow("词典校正", self.dictionary_check)

        button_layout = QHBoxLayout()
        self.skip_button = QPushButton("稍后配置")
        self.skip_button.clicked.connect(self.reject)
        self.save_button = QPushButton("保存并开始")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(self.skip_button)
        button_layout.addWidget(self.save_button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(form)
        layout.addLayout(button_layout)
        self._apply_styles()

    def build_settings(self) -> Settings:
        translation_enabled = self.translation_enabled_check.isChecked()
        return Settings(
            asr_provider=self.provider_combo.currentText(),
            model_size=self.local_model_combo.currentText(),
            language=self.language_combo.currentText(),
            api_base_url=self.api_url_combo.currentText().strip(),
            api_key=self.api_key_input.text().strip(),
            api_model=self.api_model_combo.currentText().strip(),
            websocket_url=self.websocket_url_combo.currentText().strip(),
            websocket_api_key=self.websocket_key_input.text().strip(),
            websocket_model=self.websocket_model_combo.currentText().strip(),
            preview_before_insert=self.preview_check.isChecked(),
            dictionary_correction_enabled=self.dictionary_check.isChecked(),
            translation_api_base_url=self.translation_url_combo.currentText().strip() if translation_enabled else "",
            translation_api_key=self.translation_key_input.text().strip() if translation_enabled else "",
            translation_model=self.translation_model_combo.currentText().strip() if translation_enabled else "",
        )

    @staticmethod
    def _editable_combo(current_value: str, presets: tuple[str, ...]) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(presets)
        if current_value and current_value not in presets:
            combo.addItem(current_value)
        combo.setCurrentText(current_value)
        return combo

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background: #ffffff;
            }
            QLabel#onboardingTitle {
                color: #172033;
                font-size: 18px;
                font-weight: 700;
            }
            QLineEdit, QComboBox {
                min-height: 28px;
                border: 1px solid #cfd7e3;
                border-radius: 6px;
                padding: 4px 7px;
            }
            QPushButton {
                min-height: 32px;
                border-radius: 7px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton#primaryButton {
                color: #ffffff;
                background: #2563eb;
                border: 1px solid #1d4ed8;
            }
            """
        )
