# Clean up any lingering Python processes
Write-Host "Cleaning up old processes..." -ForegroundColor Yellow
taskkill /F /IM python.exe 2>$null
Start-Sleep -Seconds 1

# Set project directory
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

Write-Host "Starting servers in VS Code terminals..." -ForegroundColor Green
Write-Host ""

# Start two PowerShell windows with the servers (do not re-open VS Code)

# Use VS Code command line to open terminals and run servers
# Terminal 1: Django HTTP Server
Write-Host "Starting Django HTTP server on port 8000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectDir'; .\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000"

Start-Sleep -Seconds 2

# Terminal 2: Django HTTPS Server
Write-Host "Starting Django HTTPS server on port 8443..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectDir'; .\.venv\Scripts\python.exe run_https_simple.py"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Servers Started Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "HTTP Server  (ESP32):  http://localhost:8000" -ForegroundColor White
Write-Host "HTTPS Server (Mobile): https://localhost:8443" -ForegroundColor White
Write-Host ""
Write-Host "To stop a server, press Ctrl+C in its window" -ForegroundColor Yellow
Write-Host ""
