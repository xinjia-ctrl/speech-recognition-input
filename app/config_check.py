from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings


ASR_API_MODEL_RULES = (
    ("api.openai.com", ("whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe")),
    ("api.siliconflow.com", ("FunAudioLLM/SenseVoiceSmall",)),
    ("api.siliconflow.cn", ("FunAudioLLM/SenseVoiceSmall",)),
    ("dashscope.aliyuncs.com", ("paraformer-v2",)),
)

TRANSLATION_MODEL_RULES = (
    ("api.openai.com", ("gpt-4o-mini", "gpt-4o")),
    (
        "api.siliconflow.cn",
        (
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-1.5B-Instruct",
            "Qwen/Qwen2.5-14B-Instruct",
        ),
    ),
    (
        "api.siliconflow.com",
        (
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-1.5B-Instruct",
            "Qwen/Qwen2.5-14B-Instruct",
        ),
    ),
    ("dashscope.aliyuncs.com", ("qwen-turbo", "qwen-plus")),
    ("api.deepseek.com", ("deepseek-chat", "deepseek-reasoner")),
    ("api.deepinfra.com", ("meta-llama/Meta-Llama-3.1-8B-Instruct",)),
)

WEBSOCKET_MODEL_RULES = (
    ("dashscope.aliyuncs.com", ("paraformer-realtime-v2", "paraformer-realtime-v1")),
)


@dataclass(slots=True)
class ConfigCheckItem:
    key: str
    title: str
    status: str
    message: str
    detail: str = ""


def model_match_hint(
    url: str,
    model: str,
    rules: tuple[tuple[str, tuple[str, ...]], ...],
) -> str:
    normalized_url = url.strip().lower()
    normalized_model = model.strip()
    if not normalized_url or not normalized_model:
        return ""

    for url_marker, allowed_models in rules:
        if url_marker.lower() not in normalized_url:
            continue
        if normalized_model in allowed_models:
            return ""
        return f"当前地址通常使用：{', '.join(allowed_models)}"

    return "这是自定义地址，请确认模型名与该服务商接口匹配"


def build_config_checks(
    settings: Settings,
    microphone_available: bool | None = None,
    hotkey_available: bool | None = None,
) -> list[ConfigCheckItem]:
    return [
        _check_microphone(microphone_available),
        _check_hotkey(settings, hotkey_available),
        _check_local_model(settings),
        _check_http_asr(settings),
        _check_websocket(settings),
        _check_translation(settings),
        _check_postprocess(settings),
        _check_ai_polish(settings),
    ]


def _check_microphone(available: bool | None) -> ConfigCheckItem:
    if available is True:
        return ConfigCheckItem("microphone", "麦克风", "ok", "可用", "检测到可用输入设备")
    if available is False:
        return ConfigCheckItem("microphone", "麦克风", "error", "不可用", "没有检测到可用输入设备")
    return ConfigCheckItem("microphone", "麦克风", "warning", "未检测", "点击刷新后会重新检查输入设备")


def _check_hotkey(settings: Settings, available: bool | None) -> ConfigCheckItem:
    if not settings.hotkey.strip():
        return ConfigCheckItem("hotkey", "全局快捷键", "error", "未配置", "建议使用 ctrl+alt+space")
    if available is True:
        return ConfigCheckItem("hotkey", "全局快捷键", "ok", "已启用", settings.hotkey)
    if available is False:
        return ConfigCheckItem("hotkey", "全局快捷键", "warning", "未启用", "可使用悬浮球或窗口按钮控制录音")
    return ConfigCheckItem("hotkey", "全局快捷键", "warning", "未检测", settings.hotkey)


def _check_local_model(settings: Settings) -> ConfigCheckItem:
    if settings.model_path.strip():
        path = Path(settings.model_path)
        if not path.exists():
            return ConfigCheckItem("local_model", "本地模型", "error", "路径不存在", settings.model_path)
        return ConfigCheckItem("local_model", "本地模型", "ok", "已配置模型路径", settings.model_path)

    if settings.model_size in {"tiny", "base", "small"}:
        return ConfigCheckItem("local_model", "本地模型", "ok", "使用内置模型名", settings.model_size)
    return ConfigCheckItem("local_model", "本地模型", "warning", "自定义模型名", settings.model_size)


def _check_http_asr(settings: Settings) -> ConfigCheckItem:
    missing = _missing_fields(
        ("地址", settings.api_base_url),
        ("API Key", settings.api_key),
        ("模型", settings.api_model),
    )
    active = settings.asr_provider == "api"
    if missing:
        status = "error" if active else "warning"
        message = "缺少必填项" if active else "未完整配置"
        return ConfigCheckItem("http_asr", "HTTP 云端识别", status, message, f"缺少：{', '.join(missing)}")

    hint = model_match_hint(settings.api_base_url, settings.api_model, ASR_API_MODEL_RULES)
    if hint:
        status = "error" if active else "warning"
        return ConfigCheckItem("http_asr", "HTTP 云端识别", status, "地址和模型可能不匹配", hint)
    return ConfigCheckItem("http_asr", "HTTP 云端识别", "ok", "配置完整", settings.api_model)


def _check_websocket(settings: Settings) -> ConfigCheckItem:
    key = settings.websocket_api_key or settings.api_key
    missing = _missing_fields(
        ("地址", settings.websocket_url),
        ("API Key", key),
        ("模型", settings.websocket_model),
    )
    active = settings.asr_provider == "websocket"
    if missing:
        status = "error" if active else "warning"
        message = "缺少必填项" if active else "未完整配置"
        return ConfigCheckItem("websocket", "WebSocket 实时识别", status, message, f"缺少：{', '.join(missing)}")

    hint = model_match_hint(settings.websocket_url, settings.websocket_model, WEBSOCKET_MODEL_RULES)
    if hint:
        status = "error" if active else "warning"
        return ConfigCheckItem("websocket", "WebSocket 实时识别", status, "地址和模型可能不匹配", hint)
    return ConfigCheckItem("websocket", "WebSocket 实时识别", "ok", "配置完整", settings.websocket_model)


def _check_translation(settings: Settings) -> ConfigCheckItem:
    missing = _missing_fields(
        ("地址", settings.translation_api_base_url),
        ("API Key", settings.translation_api_key),
        ("模型", settings.translation_model),
    )
    if missing:
        return ConfigCheckItem("translation", "翻译输入", "warning", "未完整配置", f"缺少：{', '.join(missing)}")

    hint = model_match_hint(
        settings.translation_api_base_url,
        settings.translation_model,
        TRANSLATION_MODEL_RULES,
    )
    if hint:
        return ConfigCheckItem("translation", "翻译输入", "warning", "地址和模型可能不匹配", hint)
    return ConfigCheckItem("translation", "翻译输入", "ok", "配置完整", settings.translation_model)


def _check_postprocess(settings: Settings) -> ConfigCheckItem:
    if settings.postprocess_enabled:
        dictionary_state = "词典校正开启" if settings.dictionary_correction_enabled else "词典校正关闭"
        return ConfigCheckItem(
            "postprocess",
            "文本处理 Pipeline",
            "ok",
            "已启用",
            f"{settings.postprocess_mode}，{dictionary_state}",
        )
    return ConfigCheckItem("postprocess", "规则后处理", "warning", "未启用", "识别结果不会自动消除口语和整理标点")


def _check_ai_polish(settings: Settings) -> ConfigCheckItem:
    if not settings.ai_polish_enabled:
        return ConfigCheckItem("ai_polish", "AI 润色", "warning", "未启用", "当前只使用本地词典和规则处理")

    missing = _missing_fields(
        ("地址", settings.ai_polish_api_base_url),
        ("API Key", settings.ai_polish_api_key),
        ("模型", settings.ai_polish_model),
    )
    if missing:
        return ConfigCheckItem("ai_polish", "AI 润色", "error", "缺少必填项", f"缺少：{', '.join(missing)}")
    return ConfigCheckItem("ai_polish", "AI 润色", "ok", "配置完整", settings.ai_polish_model)


def _missing_fields(*fields: tuple[str, str]) -> list[str]:
    return [name for name, value in fields if not value.strip()]
