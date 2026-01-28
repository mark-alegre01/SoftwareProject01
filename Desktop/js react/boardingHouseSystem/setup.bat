@echo off
REM Boarding House Payment System - Setup Script for Windows

echo.
echo ====================================
echo Boarding House Payment System Setup
echo ====================================
echo.

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed!
    echo.
    echo Please download and install Node.js from:
    echo https://nodejs.org/
    echo.
    echo Make sure to:
    echo 1. Download the LTS version
    echo 2. Run the installer
    echo 3. Select "Add to PATH" during installation
    echo 4. Restart your computer or terminal
    echo.
    pause
    exit /b 1
)

echo [OK] Node.js is installed
node --version
npm --version
echo.

REM Install root dependencies
echo [STEP 1] Installing root dependencies...
call npm install
if errorlevel 1 (
    echo [ERROR] Failed to install root dependencies
    pause
    exit /b 1
)
echo [OK] Root dependencies installed
echo.

REM Install client dependencies
echo [STEP 2] Installing client dependencies...
cd client
call npm install
if errorlevel 1 (
    echo [ERROR] Failed to install client dependencies
    cd ..
    pause
    exit /b 1
)
echo [OK] Client dependencies installed
cd ..
echo.

echo.
echo ====================================
echo Setup Complete!
echo ====================================
echo.
echo To start the application, run:
echo   npm run dev
echo.
echo This will start both the backend (port 5000) and frontend (port 5173)
echo.
pause
