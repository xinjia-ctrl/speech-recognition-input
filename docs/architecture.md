# 项目架构说明

本文档用于说明当前项目的模块边界和主要数据流，方便后续继续迭代，而不是把所有逻辑都堆进主窗口。

## 总体分层

```text
入口层
  app/__main__.py
    创建 QApplication、处理首次引导、启动主窗口

界面层
  app/main_window.py
    负责窗口编排、信号连接、状态刷新
  app/ui/
    悬浮球、轻量输入框、设置页、配置检查、诊断页和样式

控制层
  app/controllers/
    录音、识别 Worker、翻译 Worker、复制/粘贴动作封装

领域能力层
  app/asr/
    本地、HTTP API、WebSocket 三种 ASR Provider
  app/audio/
    麦克风录音和音量反馈
  app/input/
    全局快捷键、剪贴板和模拟粘贴
  app/text_pipeline.py
    词典校正、规则清洗、可选 AI 润色
  app/text_translate.py
    翻译 API 调用和结果归一化

基础设施层
  app/config.py
    设置读写
  app/history.py
    历史记录 Repository 抽象和 JSON 实现
  app/errors.py
    类型化异常和错误脱敏
```

## 主要运行流程

### 普通文件识别

1. 用户点击悬浮球或按快捷键。
2. `FloatingInputWindow` 调用 `RecordingController.start()` 开始录音。
3. 再次触发时调用 `RecordingController.stop()` 生成 WAV 文件。
4. `TranscribeWorker` 在线程中调用 `UnifiedAsrEngine.transcribe_file()`。
5. `UnifiedAsrEngine` 根据设置选择 `LocalWhisperProvider` 或 `HttpAsrProvider`。
6. 识别结果进入 `process_text_pipeline()` 做文本处理。
7. 主窗口刷新预览、历史记录和诊断信息。
8. 用户确认后通过 `InputController` 复制或粘贴到当前窗口。

### WebSocket 实时识别

1. 用户选择 WebSocket 模式后点击悬浮球。
2. `RealtimeWebSocketWorker` 在线程中调用 `UnifiedAsrEngine.run_realtime()`。
3. `WebSocketRealtimeProvider` 创建 `WebSocketRealtimeAsrClient` 并持续发送音频块。
4. Worker 通过 `AsrStreamEvent` 把 partial、final、level、error 事件发回主线程。
5. 主窗口实时刷新预览文本、悬浮球状态和音量反馈。
6. 停止后对最终文本执行文本处理并写入历史。

## ASR Provider 边界

ASR 统一入口是 `UnifiedAsrEngine`，它只依赖 `Settings`，不关心具体厂商细节。

Provider 约定：

- `LocalWhisperProvider`：本地 faster-whisper 文件识别。
- `HttpAsrProvider`：HTTP API 一次性文件识别。
- `WebSocketRealtimeProvider`：WebSocket 实时识别。

后续新增厂商时，优先新增 Provider 或在现有 Provider 内补协议适配，不要把厂商判断散落到 UI 层。

## 文本处理 Pipeline

识别后的文本处理顺序固定为：

1. `DictionaryCorrectionStage`：本地词典校正。
2. `RuleCleanupStage`：口语清理、简繁转换、场景化标点和简单代码口令转换。
3. `AiPolishStage`：可选云端 AI 润色。

UI 层只负责传入配置开关，不直接处理具体规则。

## 配置与数据

- 配置示例：`config/settings.example.json`
- 本地真实配置：`config/settings.json`
- 历史记录：`data/history.json`

真实配置和数据目录都已被 `.gitignore` 忽略。字段说明见 `docs/runtime_data.md`。

## 当前工程化原则

- 主窗口只做编排，不直接实现录音、识别、翻译、输入注入的底层细节。
- 第三方服务差异收敛在 ASR Provider、翻译模块和文本润色模块。
- 历史记录通过 Repository 抽象隔离，当前使用 JSON，后续可替换 SQLite。
- 错误统一经过 `user_error_message()` 做用户可读化和密钥脱敏。
- 构建、发布和手动验收分别由 `scripts/build_windows.ps1`、`docs/release.md`、`docs/manual_test_checklist.md` 承接。

## 后续可继续拆分的点

- 将 `FloatingInputWindow` 中的普通录音流程和 WebSocket 流程继续拆成更细的会话控制器。
- 将 UI 样式按主窗口、设置页、悬浮球拆成多个样式常量。
- 为不同云厂商增加独立协议适配类，而不是在通用 Provider 内继续堆分支。
- 将手动验收清单中最稳定的场景逐步沉淀为自动化测试。
