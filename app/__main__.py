from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        print("缺少 PySide6，请先运行：pip install -r requirements.txt")
        print(f"导入错误：{exc}")
        return 1

    from app.config import SettingsStore
    from app.main_window import FloatingInputWindow
    from app.ui import OnboardingDialog
    from app.version import __version__

    app = QApplication(sys.argv)
    app.setApplicationName("语音输入器")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)

    settings_store = SettingsStore()
    if not settings_store.exists():
        dialog = OnboardingDialog(settings_store.load())
        if dialog.exec() == dialog.DialogCode.Accepted:
            settings_store.save(dialog.build_settings())

    _window = FloatingInputWindow(settings_store)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
