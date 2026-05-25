from __future__ import annotations

from enum import StrEnum

from app.text_tools import redact_secret


class ErrorKind(StrEnum):
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    AUDIO = "audio"
    NO_SPEECH = "no_speech"
    ASR = "asr"
    REALTIME_ASR = "realtime_asr"
    TRANSLATION = "translation"
    INPUT = "input"
    UNKNOWN = "unknown"


class AppError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        kind: ErrorKind = ErrorKind.UNKNOWN,
        detail: str = "",
        hint: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.detail = detail
        self.hint = hint

    def user_message(self) -> str:
        parts = [self.message]
        if self.detail:
            parts.append(self.detail)
        if self.hint:
            parts.append(self.hint)
        return redact_secret("；".join(parts))


class DependencyMissingError(AppError):
    def __init__(self, dependency: str, install_command: str) -> None:
        super().__init__(
            f"缺少 {dependency}",
            kind=ErrorKind.DEPENDENCY,
            hint=f"请先安装：{install_command}",
        )


class ConfigurationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, kind=ErrorKind.CONFIGURATION)


class ExternalServiceError(AppError):
    def __init__(self, message: str, *, kind: ErrorKind = ErrorKind.UNKNOWN) -> None:
        super().__init__(message, kind=kind)


class InputActionError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, kind=ErrorKind.INPUT)


def user_error_message(error: BaseException | str) -> str:
    if isinstance(error, AppError):
        return error.user_message()
    return redact_secret(str(error))
