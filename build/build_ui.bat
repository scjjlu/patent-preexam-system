@echo off
REM ============================================================================
REM  专利快速预审案卷辅助审查系统 — Windows 构建脚本
REM  在 Windows 上运行此脚本打包独立的 .exe 文件
REM
REM  前置条件:
REM    1. Python 3.11+ 已安装
REM    2. pip install pyinstaller pyyaml lxml pillow streamlit
REM
REM  输出:
REM    dist/专利预审案卷辅助审查系统/  → 产出的可执行程序
REM ============================================================================

setlocal enabledelayedexpansion

echo ╔══════════════════════════════════════════════════╗
echo ║  专利快速预审案卷辅助审查系统 - 构建脚本          ║
echo ╚══════════════════════════════════════════════════╝
echo.

REM ── 1. 检查 Python ─────────────────────────────────────────────
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 未检测到 Python。请先安装 Python 3.11+。
    pause
    exit /b 1
)

echo [✓] Python: 
python --version

REM ── 2. 检查 PyInstaller ────────────────────────────────────────
pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] 安装 PyInstaller...
    pip install pyinstaller
)

REM ── 3. 检查项目依赖 ────────────────────────────────────────────
echo [*] 检查项目依赖...
pip install -e . 2>nul || pip install pyyaml lxml pillow streamlit

REM ── 4. 清理旧构建 ──────────────────────────────────────────────
echo [*] 清理旧构建...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build 2>nul

REM ── 5. 构建 ────────────────────────────────────────────────────
echo [*] 开始打包，这可能需要 2-5 分钟...
echo.
pyinstaller build/preexam_ui.spec --noconfirm

if %ERRORLEVEL% NEQ 0 (
    echo [错误] 打包失败，请检查上方错误信息。
    pause
    exit /b 1
)

REM ── 6. 完成 ────────────────────────────────────────────────────
echo.
echo ╔══════════════════════════════════════════════════╗
echo ║  ✓ 构建完成！                                    ║
echo ║                                                  ║
echo ║  可执行程序位置：                                 ║
echo ║    dist\专利预审案卷辅助审查系统\                 ║
echo ║                                                  ║
echo ║  使用方法：                                      ║
echo ║    双击 "专利预审案卷辅助审查系统.exe" 启动      ║
echo ║    系统会在浏览器中打开 http://localhost:8501    ║
echo ╚══════════════════════════════════════════════════╝

pause
