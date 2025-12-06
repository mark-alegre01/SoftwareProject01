# PowerShell script to start Django server with HTTPS
# This script will generate SSL certificates if needed and start the server

Write-Host "🔐 RFID Borrowing System - HTTPS Server Setup" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "❌ Virtual environment not found!" -ForegroundColor Red
    Write-Host "   Run: py -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# Check if certificates exist
$certDir = "ssl_certs"
$certFile = "$certDir\server.crt"
$keyFile = "$certDir\server.key"

if (-not (Test-Path $certFile) -or -not (Test-Path $keyFile)) {
    Write-Host "📜 SSL certificates not found. Generating..." -ForegroundColor Yellow
    
    # Create directory
    if (-not (Test-Path $certDir)) {
        New-Item -ItemType Directory -Path $certDir | Out-Null
    }
    
    # Try to generate certificates
    Write-Host "   Running certificate generator..." -ForegroundColor Gray
    & .\.venv\Scripts\python.exe generate_ssl_cert.py
    
    if (-not (Test-Path $certFile) -or -not (Test-Path $keyFile)) {
        Write-Host ""
        Write-Host "⚠️  Certificate generation failed. Trying alternative method..." -ForegroundColor Yellow
        Write-Host "   Installing required packages..." -ForegroundColor Gray
        
        # Install packages
        & .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
        & .\.venv\Scripts\python.exe -m pip install pyopenssl django-extensions | Out-Null
        
        # Try again
        & .\.venv\Scripts\python.exe generate_ssl_cert.py
        
        if (-not (Test-Path $certFile) -or -not (Test-Path $keyFile)) {
            Write-Host ""
            Write-Host "❌ Could not generate SSL certificates." -ForegroundColor Red
            Write-Host "   Please run manually: .\.venv\Scripts\python generate_ssl_cert.py" -ForegroundColor Yellow
            exit 1
        }
    }
    
    Write-Host "✓ Certificates generated successfully!" -ForegroundColor Green
    Write-Host ""
}

# Start the server
Write-Host "🚀 Starting Django server with HTTPS..." -ForegroundColor Cyan
Write-Host "   Server will be available at:" -ForegroundColor Gray
Write-Host "   - https://localhost:8000" -ForegroundColor White
Write-Host "   - https://YOUR_IP:8000 (for mobile devices)" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  Your browser will show a security warning." -ForegroundColor Yellow
Write-Host "   Click 'Advanced' → 'Proceed' to continue (safe for local dev)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Run the server
& .\.venv\Scripts\python.exe manage.py runserver_plus --cert-file $certFile --key-file $keyFile 0.0.0.0:8000

