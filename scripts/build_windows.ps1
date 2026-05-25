param(
    [string]$AppName = "speech-input",
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = "python"
}

Push-Location $ProjectRoot
try {
    $Version = (& $Python -c "from app.version import __version__; print(__version__)").Trim()

    & $Python -m PyInstaller --version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "缺少 PyInstaller，请先运行：pip install -r requirements-build.txt"
    }

    $PyInstallerArgs = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", $AppName,
        "--add-data", "app/ui/assets;app/ui/assets",
        "--add-data", "config/settings.example.json;config",
        "--add-data", "docs;docs"
    )

    if ($OneFile) {
        $PyInstallerArgs += "--onefile"
    }

    $PyInstallerArgs += "main.py"

    Write-Host "开始构建 $AppName v$Version"
    & $Python @PyInstallerArgs

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller 构建失败"
    }

    Write-Host "构建完成：dist\$AppName"
    Write-Host "发布前请按 docs\manual_test_checklist.md 完成手动验收"
} finally {
    Pop-Location
}
