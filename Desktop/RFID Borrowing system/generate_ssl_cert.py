"""
Generate a self-signed SSL certificate for local development.
This allows HTTPS access which is required for camera access on mobile devices.
"""
import os
from pathlib import Path
from OpenSSL import crypto, SSL

BASE_DIR = Path(__file__).resolve().parent
CERT_DIR = BASE_DIR / "ssl_certs"
CERT_FILE = CERT_DIR / "server.crt"
KEY_FILE = CERT_DIR / "server.key"

def create_self_signed_cert():
    """Create a self-signed certificate for local development."""
    # Create cert directory if it doesn't exist
    CERT_DIR.mkdir(exist_ok=True)
    
    # Check if certificate already exists
    if CERT_FILE.exists() and KEY_FILE.exists():
        print(f"✓ SSL certificate already exists at {CERT_FILE}")
        print(f"  To regenerate, delete {CERT_FILE} and {KEY_FILE}")
        return
    
    # Create a key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    
    # Create a self-signed certificate
    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "Local"
    cert.get_subject().L = "Local"
    cert.get_subject().O = "RFID Borrowing System"
    cert.get_subject().OU = "Development"
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)  # Valid for 1 year
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, 'sha256')
    
    # Save certificate and key
    with open(CERT_FILE, "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    
    with open(KEY_FILE, "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    
    print(f"✓ SSL certificate created successfully!")
    print(f"  Certificate: {CERT_FILE}")
    print(f"  Private Key: {KEY_FILE}")
    print(f"\n⚠️  This is a self-signed certificate. Your browser will show a security warning.")
    print(f"   Click 'Advanced' → 'Proceed to localhost (unsafe)' to continue.")
    print(f"   On mobile, you may need to accept the certificate in your browser settings.")

if __name__ == "__main__":
    try:
        create_self_signed_cert()
    except ImportError:
        print("❌ Error: pyopenssl is not installed.")
        print("   Run: pip install pyopenssl")
    except Exception as e:
        print(f"❌ Error creating certificate: {e}")

