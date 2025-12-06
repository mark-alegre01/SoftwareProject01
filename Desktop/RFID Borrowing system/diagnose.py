#!/usr/bin/env python
"""
Quick Diagnostic Script for RFID Borrowing System
Checks configuration, dependencies, and system readiness
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Verify Python version compatibility"""
    version = sys.version_info
    print(f"✅ Python Version: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print("   ⚠️  WARNING: Python 3.9+ recommended")
        return False
    return True

def check_django():
    """Verify Django installation"""
    try:
        import django
        print(f"✅ Django: {django.VERSION}")
        return True
    except ImportError:
        print("❌ Django not installed")
        print("   Run: pip install -r requirements.txt")
        return False

def check_required_packages():
    """Check all required packages"""
    packages = {
        'rest_framework': 'Django REST Framework',
        'django_cors_headers': 'CORS Headers',
        'Pillow': 'Image Processing',
        'cryptography': 'SSL Support',
    }
    
    missing = []
    for package, description in packages.items():
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {description}: Installed")
        except ImportError:
            print(f"❌ {description}: NOT installed")
            missing.append(package)
    
    if missing:
        print(f"\n   Install missing packages: pip install {' '.join(missing)}")
        return False
    return True

def check_database():
    """Check if database exists"""
    db_path = Path('db.sqlite3')
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        print(f"✅ Database: db.sqlite3 ({size_mb:.1f} MB)")
        return True
    else:
        print("⚠️  Database: db.sqlite3 not found")
        print("   Run: python manage.py migrate")
        return False

def check_static_files():
    """Check if static files are configured"""
    static_dir = Path('static')
    if static_dir.exists():
        css_files = list(static_dir.glob('*.css'))
        print(f"✅ Static Files: {len(list(static_dir.iterdir()))} files")
        if css_files:
            print(f"   └─ {len(css_files)} CSS files found")
        return True
    else:
        print("⚠️  Static Files: Directory not found")
        return False

def check_templates():
    """Check if templates exist"""
    template_dir = Path('templates/core')
    if template_dir.exists():
        templates = list(template_dir.glob('*.html'))
        print(f"✅ Templates: {len(templates)} found")
        
        # Check for specific templates
        important = ['borrow.html', 'dashboard.html', 'login.html']
        for tmpl in important:
            if (template_dir / tmpl).exists():
                print(f"   ✅ {tmpl}")
            else:
                print(f"   ⚠️  {tmpl} MISSING")
        return True
    else:
        print("❌ Templates: Directory not found")
        return False

def check_django_settings():
    """Verify Django can import settings"""
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rfid_borrowing.settings')
        import django
        django.setup()
        print("✅ Django Settings: Configuration loaded")
        return True
    except Exception as e:
        print(f"❌ Django Settings: {str(e)[:50]}")
        return False

def check_port_availability():
    """Check if default ports are available"""
    import socket
    
    ports = {'8000': 'Django HTTP', '8443': 'Django HTTPS'}
    
    for port, service in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', int(port)))
        sock.close()
        
        if result == 0:
            print(f"⚠️  Port {port} ({service}): IN USE")
        else:
            print(f"✅ Port {port} ({service}): Available")

def check_api_endpoints():
    """List available API endpoints"""
    print("\n📡 API Endpoints (should be running):")
    endpoints = [
        "/api/rfid-scans",
        "/api/borrowers",
        "/api/items",
        "/api/borrow",
    ]
    for endpoint in endpoints:
        print(f"   • {endpoint}")

def main():
    """Run all diagnostics"""
    print("=" * 60)
    print("RFID Borrowing System - Diagnostic Check")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Django Installation", check_django),
        ("Required Packages", check_required_packages),
        ("Database", check_database),
        ("Static Files", check_static_files),
        ("Templates", check_templates),
        ("Django Settings", check_django_settings),
        ("Port Availability", check_port_availability),
    ]
    
    results = {}
    for name, check_func in checks:
        print(f"\n🔍 {name}:")
        try:
            result = check_func()
            results[name] = result
        except Exception as e:
            print(f"❌ Error: {str(e)[:60]}")
            results[name] = False
    
    # API endpoints info
    check_api_endpoints()
    
    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    if passed == total:
        print(f"✅ All checks PASSED ({passed}/{total})")
        print("\n🚀 Ready to start server!")
        print("   Run: python manage.py runserver 0.0.0.0:8000")
        print("   Then: http://localhost:8000/borrow/")
    else:
        print(f"⚠️  {total - passed} checks need attention ({passed}/{total})")
        print("\nRecommended fixes:")
        for name, result in results.items():
            if not result:
                print(f"   • {name}")
    
    print("=" * 60)

if __name__ == '__main__':
    main()
