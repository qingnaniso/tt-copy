@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

title TT-Copy - TikTok Video Downloader

echo.
echo  ==========================================
echo    TT-Copy - TikTok Video Downloader
echo  ==========================================
echo.

set "PYTHON_DIR=%~dp0python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "PIP_EXE=%PYTHON_DIR%\Scripts\pip.exe"
set "SETUP_FLAG=%~dp0.setup_done"
set "PYTHON_VER=3.11.9"
set "PYTHON_ZIP=python-%PYTHON_VER%-embed-amd64.zip"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/%PYTHON_ZIP%"
set "GETPIP_URL=https://bootstrap.pypa.io/get-pip.py"

:: ---- Step 1: Check / Install Python ----
if not exist "%PYTHON_EXE%" (
    echo  [1/4] First launch, downloading Python runtime...
    echo        ^(~12MB, please wait^)
    echo.

    if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_DIR%\%PYTHON_ZIP%' -UseBasicParsing"

    if not exist "%PYTHON_DIR%\%PYTHON_ZIP%" (
        echo  [ERROR] Python download failed. Check network and retry.
        pause & exit /b 1
    )

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Expand-Archive -Path '%PYTHON_DIR%\%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"

    del "%PYTHON_DIR%\%PYTHON_ZIP%"

    for %%f in ("%PYTHON_DIR%\python*._pth") do (
        powershell -NoProfile -ExecutionPolicy Bypass -Command ^
            "(Get-Content '%%f') -replace '#import site', 'import site' | Set-Content '%%f'"
        echo %~dp0>> "%%f"
    )

    echo  [1/4] Python runtime      OK
) else (
    echo  [1/4] Python runtime      OK
)

:: ---- Step 2: Check / Install pip ----
if not exist "%PIP_EXE%" (
    echo  [2/4] Installing pip...

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Invoke-WebRequest -Uri '%GETPIP_URL%' -OutFile '%PYTHON_DIR%\get-pip.py' -UseBasicParsing"

    "%PYTHON_EXE%" "%PYTHON_DIR%\get-pip.py" --no-warn-script-location -q
    del "%PYTHON_DIR%\get-pip.py"

    echo  [2/4] pip                  OK
) else (
    echo  [2/4] pip                  OK
)

:: ---- Step 3 & 4: Install deps + Chromium ----
if not exist "%SETUP_FLAG%" (
    echo.
    echo  [3/4] Installing dependencies...
    echo        ^(playwright + yt-dlp, ~1-2 min^)
    echo.

    "%PIP_EXE%" install -r requirements.txt --no-warn-script-location -q

    if !errorlevel! neq 0 (
        echo  [ERROR] Dependency install failed. Check network and retry.
        pause & exit /b 1
    )

    echo  [3/4] Dependencies        OK
    echo.
    echo  [4/4] Downloading Chromium browser...
    echo        ^(~150MB, first download takes 3-5 min^)
    echo.

    "%PYTHON_EXE%" -m playwright install chromium

    if !errorlevel! neq 0 (
        echo  [ERROR] Chromium download failed. Check network and retry.
        pause & exit /b 1
    )

    echo. > "%SETUP_FLAG%"
    echo  [4/4] Chromium            OK
) else (
    echo  [3/4] Dependencies        OK
    echo  [4/4] Chromium            OK
)

echo.
echo  ==========================================
echo    Starting, browser will open soon...
echo  ==========================================
echo.

"%PYTHON_EXE%" "%~dp0_run.py" %*

if !errorlevel! neq 0 (
    echo.
    echo  Program exited. If error, screenshot the info above.
)

echo.
echo  Press any key to close...
pause >nul
