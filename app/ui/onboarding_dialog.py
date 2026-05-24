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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
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
        self.setWindowTitle("快速配置")
        self.setFixedSize(460, 360)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

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
        self.api_key_input = self._password_input(settings.api_key, "HTTP 识别 API Key")
        self.api_model_combo = self._editable_combo(settings.api_model, ASR_API_MODEL_PRESETS)

        self.websocket_url_combo = self._editable_combo(settings.websocket_url, WEBSOCKET_URL_PRESETS)
        self.websocket_key_input = self._password_input(
            settings.websocket_api_key or settings.api_key,
            "WebSocket API Key",
        )
        self.websocket_model_combo = self._editable_combo(settings.websocket_model, WEBSOCKET_MODEL_PRESETS)

        self.translation_enabled_check = QCheckBox("启用翻译输入")
        self.translation_enabled_check.setChecked(bool(settings.translation_api_key))
        self.translation_url_combo = self._editable_combo(
            settings.translation_api_base_url,
            TRANSLATION_API_URL_PRESETS,
        )
        self.translation_key_input = self._password_input(settings.translation_api_key, "翻译 API Key")
        self.translation_model_combo = self._editable_combo(settings.translation_model, TRANSLATION_MODEL_PRESETS)

        self.preview_check = QCheckBox("插入前预览确认")
        self.preview_check.setChecked(settings.preview_before_insert)
        self.dictionary_check = QCheckBox("启用词典校正")
        self.dictionary_check.setChecked(settings.dictionary_correction_enabled)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_page("基础偏好", "先选最常用的识别方式和语言。", self._basic_form()))
        self.stack.addWidget(
            self._build_page(
                "云端识别",
                "使用 HTTP 或 WebSocket 时填写；本地模式可以直接跳过。",
                self._asr_form(),
            )
        )
        self.stack.addWidget(self._build_page("增强输入", "翻译、预览和词典校正可以之后再改。", self._enhance_form()))

        self.step_label = QLabel()
        self.step_label.setObjectName("stepLabel")
        self.back_button = QPushButton("上一步")
        self.back_button.clicked.connect(self.previous_page)
        self.skip_button = QPushButton("稍后配置")
        self.skip_button.clicked.connect(self.reject)
        self.next_button = QPushButton("继续")
        self.next_button.setObjectName("primaryButton")
        self.next_button.clicked.connect(self.next_page)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.step_label)
        button_layout.addStretch()
        button_layout.addWidget(self.back_button)
        button_layout.addWidget(self.skip_button)
        button_layout.addWidget(self.next_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self.stack)
        layout.addLayout(button_layout)

        self._apply_styles()
        self._refresh_navigation()

    def next_page(self) -> None:
        if self.stack.currentIndex() == self.stack.count() - 1:
            self.accept()
            return
        self.stack.setCurrentIndex(self.stack.currentIndex() + 1)
        self._refresh_navigation()

    def previous_page(self) -> None:
        self.stack.setCurrentIndex(max(self.stack.currentIndex() - 1, 0))
        self._refresh_navigation()

    def build_settings(self) -> Settings:
        translation_enabled = self.translation_enabled_check.isChecked()
        return Settings(
            asr_provider=self.provider_combo.currentText(),
            model_size=self.local_model_combo.currentText(),
            language=self.language_combo.currentText(),
            api_base_url=self._combo_value(self.api_url_combo),
            api_key=self.api_key_input.text().strip(),
            api_model=self._combo_value(self.api_model_combo),
            websocket_url=self._combo_value(self.websocket_url_combo),
            websocket_api_key=self.websocket_key_input.text().strip(),
            websocket_model=self._combo_value(self.websocket_model_combo),
            preview_before_insert=self.preview_check.isChecked(),
            dictionary_correction_enabled=self.dictionary_check.isChecked(),
            translation_api_base_url=self._combo_value(self.translation_url_combo) if translation_enabled else "",
            translation_api_key=self.translation_key_input.text().strip() if translation_enabled else "",
            translation_model=self._combo_value(self.translation_model_combo) if translation_enabled else "",
        )

    def _basic_form(self) -> QFormLayout:
        form = self._create_form()
        form.addRow("识别模式", self.provider_combo)
        form.addRow("识别语言", self.language_combo)
        form.addRow("本地模型", self.local_model_combo)
        return form

    def _asr_form(self) -> QFormLayout:
        form = self._create_form()
        form.addRow("HTTP 地址", self.api_url_combo)
        form.addRow("HTTP Key", self.api_key_input)
        form.addRow("HTTP 模型", self.api_model_combo)
        form.addRow("实时地址", self.websocket_url_combo)
        form.addRow("实时 Key", self.websocket_key_input)
        form.addRow("实时模型", self.websocket_model_combo)
        return form

    def _enhance_form(self) -> QFormLayout:
        form = self._create_form()
        form.addRow("", self.translation_enabled_check)
        form.addRow("翻译地址", self.translation_url_combo)
        form.addRow("翻译 Key", self.translation_key_input)
        form.addRow("翻译模型", self.translation_model_combo)
        form.addRow("", self.preview_check)
        form.addRow("", self.dictionary_check)
        return form

    @staticmethod
    def _build_page(title_text: str, subtitle_text: str, form: QFormLayout) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel(title_text)
        title.setObjectName("onboardingTitle")
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("onboardingSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(form)
        layout.addStretch()
        return page

    @staticmethod
    def _create_form() -> QFormLayout:
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        return form

    @staticmethod
    def _editable_combo(current_value: str, presets: tuple[tuple[str, str], ...]) -> QComboBox:
        combo = QComboBox()
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

    @staticmethod
    def _password_input(current_value: str, placeholder: str) -> QLineEdit:
        input_box = QLineEdit(current_value)
        input_box.setEchoMode(QLineEdit.EchoMode.Password)
        input_box.setPlaceholderText(placeholder)
        return input_box

    def _refresh_navigation(self) -> None:
        current = self.stack.currentIndex()
        self.step_label.setText(f"{current + 1}/{self.stack.count()}")
        self.back_button.setEnabled(current > 0)
        self.next_button.setText("保存并开始" if current == self.stack.count() - 1 else "继续")

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
            QLabel#onboardingSubtitle,
            QLabel#stepLabel {
                color: #5d6675;
            }
            QLineEdit, QComboBox {
                min-height: 28px;
                border: 1px solid #cfd7e3;
                border-radius: 6px;
                padding: 4px 7px;
                background: #ffffff;
            }
            QCheckBox {
                color: #172033;
                min-height: 24px;
            }
            QPushButton {
                min-height: 30px;
                border-radius: 7px;
                padding: 5px 12px;
                color: #243044;
                background: #ffffff;
                border: 1px solid #cfd7e3;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #f2f5f9;
            }
            QPushButton:disabled {
                color: #9aa4b5;
                background: #f4f6f8;
            }
            QPushButton#primaryButton {
                color: #ffffff;
                background: #2563eb;
                border: 1px solid #1d4ed8;
            }
            QPushButton#primaryButton:hover {
                background: #1d4ed8;
            }
            """
        )
