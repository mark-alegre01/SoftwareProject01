#!/usr/bin/env python
"""
Startup script for RFID Borrowing System
Handles database migration and server startup
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the project to the path
project_path = Path(__file__).resolve().parent
sys.path.insert(0, str(project_path))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rfid_borrowing.settings")

def run_command(cmd, description=""):
    """Run a shell command and report status"""
    if description:
        print(f"\n📋 {description}...")
    try:
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 RFID Borrowing System - Startup")
    print("=" * 60)
    
    venv_python = project_path / ".venv" / "Scripts" / "python.exe"
    
    # Step 1: Run migrations
    print("\n1️⃣ Checking database migrations...")
    migrate_cmd = [str(venv_python), "manage.py", "migrate"]
    run_command(migrate_cmd)
    
    # Step 2: Collect static files
    print("\n2️⃣ Collecting static files...")
    static_cmd = [str(venv_python), "manage.py", "collectstatic", "--noinput"]
    run_command(static_cmd)
    
    # Step 3: Start the server
    print("\n3️⃣ Starting Django development server...")
    print("🌐 Server will be available at http://localhost:8000")
    print("👤 Admin panel at http://localhost:8000/admin/")
    print("📊 Dashboard at http://localhost:8000/core/dashboard")
    print("\nPress Ctrl+C to stop the server.\n")
    
    server_cmd = [str(venv_python), "manage.py", "runserver", "0.0.0.0:8000"]
    subprocess.run(server_cmd)

if __name__ == "__main__":
    main()
