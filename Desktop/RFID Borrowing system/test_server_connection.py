"""
Test script to verify Django server is accessible from the network.
This helps diagnose ESP32 connection issues.
"""
import sys
import socket
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Add project to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

def get_local_ip():
    """Get the local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return None

def test_port(host, port, timeout=5):
    """Test if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"  ❌ Socket test failed: {e}")
        return False

def test_http_endpoint(url):
    """Test HTTP endpoint"""
    try:
        req = Request(url)
        with urlopen(req, timeout=5) as response:
            status = response.getcode()
            body = response.read().decode('utf-8')[:200]
            return status, body
    except URLError as e:
        if "Connection refused" in str(e) or "No connection could be made" in str(e):
            return None, "Connection refused - server not running or firewall blocking"
        return None, f"URL Error: {e}"
    except HTTPError as e:
        return e.code, e.read().decode('utf-8')[:200] if hasattr(e, 'read') else str(e)
    except Exception as e:
        return None, f"Error: {e}"

if __name__ == "__main__":
    print("=" * 60)
    print("  Django Server Connection Diagnostic")
    print("=" * 60)
    print()
    
    # Get local IP
    local_ip = get_local_ip()
    print(f"📍 Your local IP address: {local_ip or 'Could not determine'}")
    print()
    
    # Test ports
    print("Testing ports...")
    print(f"  Port 8000 (HTTP): ", end="")
    port_8000_open = test_port("0.0.0.0", 8000) if local_ip else False
    if port_8000_open:
        print("✅ OPEN")
    else:
        print("❌ CLOSED or not listening on 0.0.0.0")
    
    print(f"  Port 8443 (HTTPS): ", end="")
    port_8443_open = test_port("0.0.0.0", 8443) if local_ip else False
    if port_8443_open:
        print("✅ OPEN")
    else:
        print("❌ CLOSED or not listening on 0.0.0.0")
    print()
    
    # Test HTTP endpoints
    if local_ip:
        test_urls = [
            f"http://localhost:8000/api/borrowers",
            f"http://127.0.0.1:8000/api/borrowers",
            f"http://{local_ip}:8000/api/borrowers",
        ]
        
        print("Testing HTTP endpoints...")
        for url in test_urls:
            print(f"  {url}")
            status, result = test_http_endpoint(url)
            if status:
                print(f"    ✅ Status: {status}")
                if result:
                    print(f"    Response: {result[:100]}...")
            else:
                print(f"    ❌ {result}")
            print()
    
    # Recommendations
    print("=" * 60)
    print("  Recommendations")
    print("=" * 60)
    print()
    
    if not port_8000_open:
        print("❌ Port 8000 is not open!")
        print("   → Start the HTTP server:")
        print("     .\\.venv\\Scripts\\python manage.py runserver 0.0.0.0:8000")
        print("   → Or use: run_both_servers.bat")
        print()
    
    if local_ip:
        print(f"📱 ESP32 Configuration:")
        print(f"   API_HOST = \"http://{local_ip}:8000\"")
        print()
        print("🔧 If connection still fails:")
        print("   1. Check Windows Firewall allows Python on port 8000")
        print("   2. Verify ESP32 and PC are on the same Wi-Fi network")
        print("   3. Try pinging {local_ip} from ESP32 serial monitor")
        print("   4. Check router doesn't block device-to-device communication")
    else:
        print("⚠️  Could not determine local IP address")
        print("   → Check your network connection")
    
    print()

