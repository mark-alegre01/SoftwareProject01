# RFID Borrowing System - Server Launcher
# PowerShell version - Handles HTTP/HTTPS seamlessly

param(
    [ValidateSet("http", "https", "auto")]
    [string]$Mode = "http"
)

$projectPath = "C:\Users\admin\Desktop\RFID Borrowing system"
$port = 8000

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RFID Borrowing System - Server Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Kill any existing processes
Write-Host "Cleaning up existing processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force | Out-Null
Start-Sleep -Seconds 1

# Check Django installation
Write-Host "Verifying Django installation..." -ForegroundColor Yellow
$djangoCheck = & python -m django --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Django not found!" -ForegroundColor Red
    Write-Host "Run: pip install -r requirements.txt" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "✅ Django version: $djangoCheck" -ForegroundColor Green
Write-Host ""

# Navigate to project
Set-Location $projectPath

# Determine mode
if ($Mode -eq "auto") {
    $Mode = "http"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Django Server ($Mode)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($Mode -eq "http") {
    Write-Host "📱 HTTP Mode" -ForegroundColor Green
    Write-Host "🔗 Access: http://localhost:$port/borrow/" -ForegroundColor Cyan
} else {
    Write-Host "🔒 HTTPS Mode" -ForegroundColor Green
    Write-Host "🔗 Access: https://localhost:8443/borrow/" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "⏹️  To stop server: Press Ctrl+C" -ForegroundColor Yellow
Write-Host ""

# Start server
if ($Mode -eq "http") {
    python manage.py runserver 0.0.0.0:$port
} else {
    python run_https_server.py
}

Write-Host ""
Write-Host "Server stopped." -ForegroundColor Yellow
Read-Host "Press Enter to exit"
