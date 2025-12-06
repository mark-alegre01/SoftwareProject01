import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rfid_borrowing.settings')
django.setup()

from core.models import Borrower

# Clean up test data
deleted, _ = Borrower.objects.filter(rfid_uid__startswith='API-TEST').delete()
print(f"Deleted {deleted} API-TEST borrowers")

deleted, _ = Borrower.objects.filter(rfid_uid__startswith='TEST-SPACES').delete()
print(f"Deleted {deleted} TEST-SPACES borrowers")

deleted, _ = Borrower.objects.filter(rfid_uid__startswith='TEST-RFID').delete()
print(f"Deleted {deleted} TEST-RFID borrowers")

deleted, _ = Borrower.objects.filter(rfid_uid__startswith='COMPLETE-TEST').delete()
print(f"Deleted {deleted} COMPLETE-TEST borrowers")

deleted, _ = Borrower.objects.filter(rfid_uid__startswith='WITH-TXN-TEST').delete()
print(f"Deleted {deleted} WITH-TXN-TEST borrowers")

print("✓ Cleanup complete")
