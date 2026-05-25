# 打包、安装与发布流程

本文档说明 Windows 桌面版本如何管理版本号、构建 PyInstaller 包，以及发布前需要检查哪些内容。

## 版本号

当前应用版本号统一定义在 `app/version.py`：

```python
__version__ = "0.1.0"
```

修改版本号时只改这一处。应用启动时会把该版本写入 Qt 应用元信息，打包脚本也会读取同一个版本号用于构建输出提示。

建议版本规则：

- `0.1.x`：比赛开发期的小修小补。
- `0.2.x`：新增明显功能，例如新的供应商适配、完整日志系统。
- `1.0.0`：比赛提交或正式发布版本。

## 构建环境准备

建议使用干净虚拟环境构建，避免把本机临时依赖混进发布包：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-build.txt
```

`requirements-build.txt` 会安装完整 Demo 所需依赖，包括本地识别、HTTP API、WebSocket 和 PyInstaller。只做轻量云端版时，也可以按需调整依赖，但发布说明里必须写清楚不包含哪些能力。

## 执行打包

默认构建目录版，启动速度和排错体验更好：

```powershell
.\scripts\build_windows.ps1
```

输出目录：

```text
dist/
  speech-input/
    speech-input.exe
```

构建脚本会随包带上 `config/settings.example.json`、`docs/` 和 `app/ui/assets/`，确保首次配置示例、说明文档和界面箭头图标都能正常使用。

如果需要单文件包，可以执行：

```powershell
.\scripts\build_windows.ps1 -OneFile
```

单文件包启动更慢，且包含大型 ASR 依赖时排错不如目录版直观。比赛 Demo 优先推荐目录版。

## 发布前检查

发布前至少完成以下检查：

- 运行 `python -m unittest discover -s tests`。
- 运行 `python -m ruff check app tests`。
- 按 `docs/manual_test_checklist.md` 完成本地、HTTP API、WebSocket、翻译和插入流程验收。
- 确认 `config/settings.json` 没有进入 Git 暂存区。
- 确认 `data/`、录音文件、历史记录和 API Key 没有进入发布仓库。
- 打开 `dist/speech-input/speech-input.exe`，确认首次引导、悬浮按钮和设置页可以正常使用。
- 在 README 或 Release 说明里写明第三方依赖、原创功能范围和 Demo 视频链接。

## 发布包建议

比赛提交时建议上传或附带以下内容：

- 公开仓库链接。
- README 中的 Demo 视频链接。
- `dist/speech-input/` 目录压缩包，供评审快速试用。
- `docs/manual_test_checklist.md` 的验收结论截图或摘要。

不要发布以下内容：

- `config/settings.json`
- `data/history.json`
- 麦克风录音文件
- API Key、Authorization Header 或包含密钥的截图

## 常见问题

### PowerShell 禁止执行脚本

可以临时使用当前进程策略：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\build_windows.ps1
```

### 缺少 PyInstaller

先安装构建依赖：

```powershell
pip install -r requirements-build.txt
```

### 打包后缺少某个识别能力

通常是构建环境没有安装对应依赖。完整 Demo 构建请使用：

```powershell
pip install -r requirements-build.txt
```

如果只安装了 `requirements.txt`，应用只具备基础桌面能力，不包含本地 Whisper、HTTP API、WebSocket 等完整能力。
