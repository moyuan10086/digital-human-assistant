@echo off
setlocal
:: Change code page to UTF-8
chcp 65001 >nul

title Digital Human Launcher

echo ========================================================
echo               Digital Human Assistant
echo ========================================================
echo.

:: 1. Check Frontend Build
if not exist "dist" (
    echo [ERROR] 'dist' directory not found!
    echo Please run 'npm run build' first.
    pause
    exit /b
)

:: 2. Check uv
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARN] uv not found. Installing...
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo Please restart this script.
    pause
    exit /b
)

:: 2.5 Proxy Detection
echo [INFO] Detecting proxy settings...
if defined http_proxy (
    echo [INFO] Using existing proxy: %http_proxy%
) else (
    :: Detect 7890 (Clash)
    netstat -an | findstr ":7890" | findstr "LISTENING" >nul
    if %errorlevel% equ 0 (
        echo [INFO] Auto-detected proxy: 127.0.0.1:7890
        set "http_proxy=http://127.0.0.1:7890"
        set "https_proxy=http://127.0.0.1:7890"
    ) else (
        :: Detect 10809 (v2ray)
        netstat -an | findstr ":10809" | findstr "LISTENING" >nul
        if %errorlevel% equ 0 (
            echo [INFO] Auto-detected proxy: 127.0.0.1:10809
            set "http_proxy=http://127.0.0.1:10809"
            set "https_proxy=http://127.0.0.1:10809"
        ) else (
             echo [INFO] No proxy detected. Will use Aliyun mirror for dependencies.
        )
    )
)

echo [INFO] Current Proxy: %http_proxy%

:: 3. Sync Environment
echo [INFO] Syncing Python environment...
uv sync
if %errorlevel% neq 0 (
    echo [ERROR] Environment sync failed. Check network.
    pause
    exit /b
)

:: 4. Start Service
echo.
echo [INFO] Starting service...
echo [INFO] Browser will open at http://localhost:8004
echo [INFO] Do not close this window.
echo.

:: Delay 3s then open browser
start /b cmd /c "timeout /t 3 >nul && start http://localhost:8004"

:: Run Backend
uv run backend/main.py

pause
