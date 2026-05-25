# 比赛提交说明

## 项目名称

语音输入器

## 项目简介

本项目是一个面向 Windows 桌面的语音输入法原型。它不接入系统级 IME，而是以悬浮输入助手的形式工作：用户通过悬浮球或全局快捷键开始录音，系统完成语音识别、文本整理、预览编辑，并将结果复制或插入到当前输入位置。

当前版本已支持本地离线识别、HTTP API 一次性识别和 WebSocket 实时识别三种模式，适合在比赛 Demo 中展示“离线可用、云端可扩展、实时有反馈”的完整语音输入流程。

## 仓库链接

待补充：议题发布后 24 小时内将公开仓库链接填写到报名表和本文档中。

## Demo 视频链接

待补充：提交前将 Demo 视频链接填写到 README 和本文档中。

建议视频控制在 2 到 4 分钟，覆盖以下流程：

1. 启动应用并展示首次引导或悬浮球。
2. 切换识别模式，说明本地、HTTP API、WebSocket 的区别。
3. 使用悬浮球或 `ctrl+alt+space` 开始和停止录音。
4. 展示识别文本进入预览框，并进行编辑、整理或翻译。
5. 将文本复制或插入到记事本、浏览器输入框等外部应用。
6. 展示历史记录、配置检查、诊断信息和错误脱敏效果。

## 核心功能

- Windows 桌面悬浮球和轻量输入框。
- 全局快捷键启动、停止录音和唤醒悬浮球。
- 本地 `faster-whisper` 离线中文识别。
- HTTP API 云端识别，并支持失败后自动本地兜底。
- WebSocket 实时识别，支持通用 JSON 协议和百炼 Paraformer 实时协议。
- 识别结果预览、编辑、复制和模拟粘贴插入。
- 规则后处理、词典校正、简繁转换和场景化文本整理。
- 可选云端 AI 润色和中英双向翻译。
- 本地历史记录，支持数量限制和清空。
- 设置页、配置检查页和诊断页。
- API Key 脱敏显示和敏感配置忽略提交。

## 技术栈与依赖

- Python 3.12
- PySide6：桌面界面
- sounddevice、numpy：麦克风录音和音频处理
- faster-whisper：本地离线识别
- requests：HTTP API 调用
- websocket-client：WebSocket 实时识别
- OpenCC：繁体中文转简体中文
- pynput：全局快捷键
- pyperclip、pyautogui：剪贴板和模拟输入
- PyInstaller：Windows 打包

依赖按能力拆分在多个 requirements 文件中，基础桌面功能、离线识别、云端接口、WebSocket、开发工具和打包工具可以按需安装。

## 原创实现范围

本项目原创实现主要包括：

- 桌面悬浮输入交互和主窗口流程编排。
- 录音状态管理、音量反馈和录音结果封装。
- 本地、HTTP API、WebSocket 三类 ASR Provider 的统一调用入口。
- HTTP API 失败后的本地识别兜底流程。
- WebSocket 实时音频分块发送、事件解析和 UI 实时刷新。
- 文本处理 Pipeline，包括词典校正、规则清洗、简繁转换和场景模式处理。
- 翻译、复制、粘贴、历史记录、配置检查和诊断信息展示。
- 类型化异常、用户可读错误提示和密钥脱敏处理。
- Windows 打包脚本、发布说明和端到端手动测试清单。

第三方模型、GUI 框架、录音库、网络库和输入模拟库均为外部依赖，已在 README 和依赖文件中列明。

## 项目结构

```text
app/
  asr/          本地、HTTP API、WebSocket 识别 Provider
  audio/        麦克风录音
  controllers/ 录音、识别、翻译和输入动作控制器
  input/        全局快捷键、剪贴板和模拟粘贴
  ui/           悬浮球、设置页、诊断页和样式
  config.py     配置读写
  errors.py     类型化异常和脱敏提示
  history.py    历史记录仓储
  main_window.py 主窗口编排
config/
  settings.example.json
docs/
  architecture.md
  runtime_data.md
  release.md
  manual_test_checklist.md
tests/
  test_core.py
scripts/
  build_windows.ps1
```

更完整的模块边界见 `docs/architecture.md`。

## 安装与运行

基础运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app
```

完整 Demo 环境建议安装：

```powershell
pip install -r requirements-local.txt -r requirements-cloud.txt -r requirements-websocket.txt
python -m app
```

开发检查：

```powershell
pip install -r requirements-dev.txt
python -m unittest discover -s tests
python -m ruff check app tests
```

Windows 打包：

```powershell
pip install -r requirements-build.txt
.\scripts\build_windows.ps1
```

打包和版本管理细节见 `docs/release.md`。

## 配置与数据安全

- 示例配置文件：`config/settings.example.json`
- 本地真实配置：`config/settings.json`
- 历史记录文件：`data/history.json`

`config/settings.json` 和 `data/` 已被 `.gitignore` 忽略，不应提交到公开仓库。API Key、Authorization Header 和常见密钥格式会在界面错误提示中脱敏显示。

运行数据结构、诊断字段和历史记录格式见 `docs/runtime_data.md`。

## 测试与验收

当前自动化测试覆盖以下内容：

- 配置读写和配置检查。
- 文本清洗、简繁转换、语言过滤和词典校正。
- ASR Provider 选择、HTTP 失败本地兜底和无语音处理。
- WebSocket 消息解析和百炼实时协议事件解析。
- 翻译结果抽取和方向判断。
- 历史记录数量限制和清空。
- 类型化错误、密钥脱敏和输入控制器错误处理。

运行命令：

```powershell
python -m unittest discover -s tests
python -m ruff check app tests
```

麦克风录音、真实本地模型、真实云端 API、WebSocket 实时识别和外部应用插入需要在 Windows 桌面环境手动验收。提交前按 `docs/manual_test_checklist.md` 完整检查。

## 当前不足与后续计划

当前版本已经把录音、识别、输入、翻译、历史和错误处理拆出了一部分控制层与 Provider 层，但仍有继续优化空间：

1. `app/main_window.py` 仍承担较多流程编排职责，后续可以继续拆分普通录音会话和实时识别会话控制器。
2. 第三方服务协议适配已经收敛到 ASR Provider，但不同厂商协议仍可进一步拆成更独立的 Adapter。
3. 运行诊断目前主要显示在界面中，暂未默认写入日志文件；后续可增加 `data/logs/app.log`，同时继续做好敏感信息脱敏。
4. 历史记录当前使用 JSON 存储，适合原型和比赛 Demo；如需搜索、分页或同步，可升级为 SQLite 或云端仓储。
5. 自动化测试主要覆盖核心纯逻辑和适配解析，GUI 交互、音频设备和外部窗口插入仍以手动验收为主。
6. 打包脚本和版本号已建立，但正式发布前仍需要补充 Release 产物、Demo 视频和实际验收记录。

## 持续交付说明

比赛开发过程中应保持功能阶段独立提交，不在截止前一次性导入全部代码。提交和 PR 描述需要写清楚本次变更的实际内容，避免把配置文件、历史数据、录音文件或 API Key 带入仓库。

提交前建议确认：

- README 已说明功能、依赖、原创范围和运行方式。
- `docs/architecture.md`、`docs/runtime_data.md`、`docs/release.md` 和 `docs/manual_test_checklist.md` 与当前代码保持一致。
- `python -m unittest discover -s tests` 通过。
- `python -m ruff check app tests` 通过。
- Demo 视频和仓库链接已经补充。
- `config/settings.json`、`data/history.json`、录音文件和密钥没有进入暂存区。

## 许可证

比赛作品阶段暂未指定许可证，正式开源前可根据比赛规则和第三方依赖协议补充。
