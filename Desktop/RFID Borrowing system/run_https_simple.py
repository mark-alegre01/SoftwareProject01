"""
Simple HTTPS server wrapper for Django development server.
This doesn't require django-extensions.
"""
import os
import sys
import ssl
from pathlib import Path

# Add project to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rfid_borrowing.settings')

import django
django.setup()

from django.core.servers.basehttp import WSGIServer, WSGIRequestHandler
from django.core.wsgi import get_wsgi_application
from django.contrib.staticfiles.handlers import StaticFilesHandler

def run_https_server():
    """Run Django with HTTPS using SSL certificates."""
    cert_file = BASE_DIR / "ssl_certs" / "server.crt"
    key_file = BASE_DIR / "ssl_certs" / "server.key"
    
    if not cert_file.exists() or not key_file.exists():
        print("❌ SSL certificates not found!")
        print(f"   Certificate: {cert_file}")
        print(f"   Key: {key_file}")
        print("\n   Please run: .\\.venv\\Scripts\\python generate_ssl_cert.py")
        return
    
    # Get WSGI application with static files middleware
    application = StaticFilesHandler(get_wsgi_application())
    
    # Create HTTPS server (use port 8443 to avoid conflict with HTTP on 8000)
    server_address = ('0.0.0.0', 8443)
    httpd = WSGIServer(server_address, WSGIRequestHandler)
    httpd.set_app(application)
    
    # Wrap socket with SSL
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_file), str(key_file))
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    
    print("=" * 60)
    print("  Django HTTPS Server Running")
    print("=" * 60)
    print(f"\n✓ Server running at:")
    print(f"  - https://localhost:8443")
    print(f"  - https://YOUR_IP:8443 (for mobile devices)")
    print(f"\n⚠️  Your browser will show a security warning.")
    print(f"   Click 'Advanced' → 'Proceed' to continue")
    print(f"   (This is safe for local development)")
    print(f"\nPress Ctrl+C to stop the server\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped.")
        httpd.shutdown()

if __name__ == '__main__':
    run_https_server()

