"""
Simple script to run Django with HTTPS using runserver_plus.
This will auto-generate certificates if they don't exist.
"""
import os
import sys
from pathlib import Path

# Add the project directory to the path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rfid_borrowing.settings')

# Import Django
import django
django.setup()

# Now import and run the server
from django_extensions.management.commands.runserver_plus import Command

if __name__ == '__main__':
    # Create ssl_certs directory if it doesn't exist
    cert_dir = BASE_DIR / "ssl_certs"
    cert_dir.mkdir(exist_ok=True)
    
    cert_file = cert_dir / "server.crt"
    key_file = cert_dir / "server.key"
    
    # Check if certificates exist
    if not cert_file.exists() or not key_file.exists():
        print("⚠️  SSL certificates not found. Attempting to generate...")
        print("   If this fails, run: .\\.venv\\Scripts\\python generate_ssl_cert.py")
        print()
    
    # Run the server with HTTPS
    print("🚀 Starting Django server with HTTPS on 0.0.0.0:8000")
    print("   Access at: https://localhost:8000 or https://YOUR_IP:8000")
    print("   Press Ctrl+C to stop")
    print()
    
    try:
        from django.core.management import execute_from_command_line
        # Use runserver_plus with SSL
        execute_from_command_line([
            'manage.py',
            'runserver_plus',
            '--cert-file', str(cert_file),
            '--key-file', str(key_file),
            '0.0.0.0:8000'
        ])
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Try running manually:")
        print("   .\\.venv\\Scripts\\python manage.py runserver_plus --cert-file ssl_certs/server.crt --key-file ssl_certs/server.key 0.0.0.0:8000")

