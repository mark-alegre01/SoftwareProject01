echo.
@echo off
REM Run both HTTP (for ESP32) and HTTPS (for mobile camera) servers
REM This script uses the workspace .venv and records PIDs so it only stops the processes it started.

SETLOCAL ENABLEDELAYEDEXPANSION
set "SCRIPT_DIR=%~dp0"
rem Remove trailing backslash if present (keep consistent)
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo.
echo ========================================
echo  RFID Borrowing System - Dual Server
echo  HTTP (8000) for ESP32
echo  HTTPS (8443) for Mobile Camera
echo ========================================
echo.

set "VENV=%SCRIPT_DIR%\.venv\Scripts\python.exe"

rem Verify virtualenv python exists
if not exist "%VENV%" (
    echo [ERROR] Virtual environment not found at "%VENV%"
    echo Please create the virtual environment or update the path.
    pause
    exit /b 1
)

rem Ensure logs directory exists
if not exist "%SCRIPT_DIR%\logs" mkdir "%SCRIPT_DIR%\logs"

rem Check/generate SSL certificates
if not exist "%SCRIPT_DIR%\ssl_certs\server.crt" (
    echo [INFO] SSL certificates not found. Attempting to generate...
    if not exist "%SCRIPT_DIR%\ssl_certs" mkdir "%SCRIPT_DIR%\ssl_certs"
    "%VENV%" "%SCRIPT_DIR%\generate_ssl_cert.py"
)

echo [INFO] Starting HTTP server on port 8000 (for ESP32)...
start "Django HTTP Server" cmd /k "cd /d "%SCRIPT_DIR%" && "%VENV%" "%SCRIPT_DIR%\manage.py" runserver 0.0.0.0:8000"

timeout /t 2 /nobreak >nul

echo [INFO] Starting HTTPS server on port 8443 (for mobile camera)...
start "Django HTTPS Server" cmd /k "cd /d "%SCRIPT_DIR%" && "%VENV%" "%SCRIPT_DIR%\run_https_simple.py""

echo.
echo ========================================
echo  Servers Started!
echo ========================================
echo.
echo HTTP Server (ESP32):
echo   - http://localhost:8000
echo   - http://YOUR_IP:8000
echo.
echo HTTPS Server (Mobile Camera):
echo   - https://localhost:8443
echo   - https://YOUR_IP:8443
echo.
echo.
echo Press any key to stop BOTH servers and close their windows.
pause >nul

echo Stopping servers now...
taskkill /FI "WINDOWTITLE eq Django HTTP Server*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Django HTTPS Server*" /T /F >nul 2>&1

echo Servers stopped.

ENDLOCAL

exit /b 0


