@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

title TT-Copy - TikTok Video Downloader

echo.
echo  ==========================================
echo    TT-Copy - TikTok Video Downloader
echo  ==========================================
echo.

:: ---- 配置 ----
set "PYTHON_DIR=%~dp0python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "PIP_EXE=%PYTHON_DIR%\Scripts\pip.exe"
set "SETUP_FLAG=%~dp0.setup_done"
set "PYTHON_VER=3.11.9"
set "PYTHON_ZIP=python-%PYTHON_VER%-embed-amd64.zip"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/%PYTHON_ZIP%"
set "GETPIP_URL=https://bootstrap.pypa.io/get-pip.py"

:: ---- Step 1: 检查 / 安装 Python ----
if not exist "%PYTHON_EXE%" (
    echo  [1/4] 首次启动，正在下载 Python 运行环境...
    echo        ^(约 12MB，请稍候^)
    echo.

    if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_DIR%\%PYTHON_ZIP%' -UseBasicParsing"

    if not exist "%PYTHON_DIR%\%PYTHON_ZIP%" (
        echo  [错误] Python 下载失败，请检查网络连接后重试。
        pause & exit /b 1
    )

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Expand-Archive -Path '%PYTHON_DIR%\%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"

    del "%PYTHON_DIR%\%PYTHON_ZIP%"

    :: 启用 site-packages（embedded Python 默认禁用）
    for %%f in ("%PYTHON_DIR%\python*._pth") do (
        powershell -NoProfile -ExecutionPolicy Bypass -Command ^
            "(Get-Content '%%f') -replace '#import site', 'import site' | Set-Content '%%f'"
    )

    echo  [1/4] Python 环境准备完成 OK
) else (
    echo  [1/4] Python 环境       OK
)

:: ---- Step 2: 检查 / 安装 pip ----
if not exist "%PIP_EXE%" (
    echo  [2/4] 正在安装包管理器...

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Invoke-WebRequest -Uri '%GETPIP_URL%' -OutFile '%PYTHON_DIR%\get-pip.py' -UseBasicParsing"

    "%PYTHON_EXE%" "%PYTHON_DIR%\get-pip.py" --no-warn-script-location -q
    del "%PYTHON_DIR%\get-pip.py"

    echo  [2/4] 包管理器          OK
) else (
    echo  [2/4] 包管理器          OK
)

:: ---- Step 3 & 4: 首次检查依赖 + Chromium ----
if not exist "%SETUP_FLAG%" (
    echo.
    echo  [3/4] 正在安装依赖库...
    echo        ^(playwright + yt-dlp，约需 1-2 分钟^)
    echo.

    "%PIP_EXE%" install -r requirements.txt --no-warn-script-location -q

    if !errorlevel! neq 0 (
        echo  [错误] 依赖安装失败，请检查网络连接后重试。
        pause & exit /b 1
    )

    echo  [3/4] 依赖库            OK
    echo.
    echo  [4/4] 正在下载 Chromium 浏览器...
    echo        ^(约 150MB，首次下载需要 3-5 分钟，请耐心等待^)
    echo.

    "%PYTHON_EXE%" -m playwright install chromium

    if !errorlevel! neq 0 (
        echo  [错误] Chromium 下载失败，请检查网络连接后重试。
        pause & exit /b 1
    )

    echo. > "%SETUP_FLAG%"
    echo  [4/4] Chromium          OK
) else (
    echo  [3/4] 依赖库            OK
    echo  [4/4] Chromium          OK
)

echo.
echo  ==========================================
echo    正在启动，浏览器即将打开...
echo  ==========================================
echo.

"%PYTHON_EXE%" -m ttcopy.main %*

if !errorlevel! neq 0 (
    echo.
    echo  程序已退出。如有错误请截图上方信息。
    pause
)
