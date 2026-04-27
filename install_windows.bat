@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

set "LUFFY_DIR=%~dp0"
set "VENV_DIR=%LUFFY_DIR%.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
set "PW_EXE=%VENV_DIR%\Scripts\playwright.exe"

echo ============================================
echo   巨浪商品分发 - 本地代理安装程序
echo ============================================
echo.

rem 检查 Python
echo [1/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 未检测到 Python，请先安装 Python 3.11 或更高版本
    echo 下载地址: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo   已找到 Python %PY_VER%

rem 创建虚拟环境
echo [2/5] 创建虚拟环境...
if not exist "%VENV_DIR%" (
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo   虚拟环境已创建
) else (
    echo   虚拟环境已存在，跳过
)

rem 安装依赖
echo [3/5] 安装后端依赖（首次约需 1-2 分钟）...
"%PIP_EXE%" install -q -r "%LUFFY_DIR%server\requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/
if errorlevel 1 (
    echo [错误] 安装依赖失败，请检查网络连接
    pause
    exit /b 1
)
"%PIP_EXE%" install -q playwright -i https://mirrors.aliyun.com/pypi/simple/
echo   依赖安装完成

rem 安装 Playwright 浏览器
echo [4/5] 安装 Playwright 浏览器（首次约需 2-5 分钟，文件较大）...
"%PW_EXE%" install chromium
if errorlevel 1 (
    echo [警告] Playwright Chromium 安装失败，将尝试使用系统 Edge 浏览器
)
echo   浏览器安装完成

rem 注册开机自启
echo [5/5] 注册开机自启任务...
schtasks /delete /tn "LuffyBackend" /f >nul 2>&1
schtasks /create ^
    /tn "LuffyBackend" ^
    /tr "\"%PYTHON_EXE%\" \"%LUFFY_DIR%start.py\"" ^
    /sc onlogon ^
    /ru "%USERNAME%" ^
    /f >nul 2>&1
if errorlevel 1 (
    echo [警告] 注册开机自启失败（可能需要管理员权限），但不影响正常使用
) else (
    echo   已设置开机自动启动
)

rem 立即启动服务（最小化窗口）
echo.
echo 正在启动本地代理服务...
start "LuffyBackend" /min "%PYTHON_EXE%" "%LUFFY_DIR%start.py"

rem 等待服务启动
timeout /t 3 /nobreak >nul

echo.
echo ============================================
echo   安装完成！
echo.
echo   1. 在浏览器中打开:
echo      https://jvlangai.com/luffy/
echo.
echo   2. 后台服务已在运行，开机后会自动启动
echo.
echo   3. 如需卸载，双击 uninstall_windows.bat
echo ============================================
echo.
pause
