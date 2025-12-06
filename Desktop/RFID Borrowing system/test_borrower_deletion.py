#!/usr/bin/env python
"""
Test script to verify borrower deletion and re-registration with same RFID UID.
This helps diagnose why re-registration fails after deletion.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rfid_borrowing.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from core.models import Borrower, BorrowTransaction, Item
from django.db import IntegrityError

def test_borrower_lifecycle():
    """Test full borrower lifecycle: create, delete, re-create with same RFID"""
    
    test_rfid = "TEST-RFID-12345"
    test_name = "Test Borrower"
    test_email = "test@example.com"
    
    print("=" * 70)
    print("BORROWER DELETION AND RE-REGISTRATION TEST")
    print("=" * 70)
    
    # Step 1: Create a borrower
    print("\n[Step 1] Creating borrower...")
    try:
        borrower1 = Borrower.objects.create(
            name=test_name,
            rfid_uid=test_rfid,
            email=test_email
        )
        print(f"✓ Borrower created: {borrower1}")
        print(f"  ID: {borrower1.id}, RFID: {borrower1.rfid_uid}")
    except Exception as e:
        print(f"✗ Failed to create borrower: {e}")
        return
    
    # Step 2: Check if borrower exists in DB
    print("\n[Step 2] Verifying borrower exists in database...")
    exists = Borrower.objects.filter(rfid_uid=test_rfid).exists()
    print(f"  Borrower with RFID '{test_rfid}' exists: {exists}")
    count = Borrower.objects.filter(rfid_uid=test_rfid).count()
    print(f"  Count of borrowers with this RFID: {count}")
    
    # Step 3: Delete the borrower
    print("\n[Step 3] Deleting borrower...")
    borrower_id = borrower1.id
    try:
        borrower1.delete()
        print(f"✓ Borrower deleted")
    except Exception as e:
        print(f"✗ Failed to delete borrower: {e}")
        return
    
    # Step 4: Check if borrower still exists after deletion
    print("\n[Step 4] Verifying borrower deleted from database...")
    exists = Borrower.objects.filter(rfid_uid=test_rfid).exists()
    print(f"  Borrower with RFID '{test_rfid}' exists: {exists}")
    count = Borrower.objects.filter(rfid_uid=test_rfid).count()
    print(f"  Count of borrowers with this RFID: {count}")
    
    # Also check by ID
    by_id_exists = Borrower.objects.filter(id=borrower_id).exists()
    print(f"  Borrower with ID {borrower_id} exists: {by_id_exists}")
    
    # Step 5: Try to re-create borrower with same RFID
    print("\n[Step 5] Re-creating borrower with same RFID UID...")
    try:
        borrower2 = Borrower.objects.create(
            name=test_name,
            rfid_uid=test_rfid,
            email=test_email
        )
        print(f"✓ Borrower re-created successfully: {borrower2}")
        print(f"  ID: {borrower2.id}, RFID: {borrower2.rfid_uid}")
    except IntegrityError as e:
        print(f"✗ INTEGRITY ERROR (unique constraint): {e}")
        print(f"  This means the database still has the old RFID value!")
    except Exception as e:
        print(f"✗ Failed to re-create borrower: {e}")
        return
    
    # Cleanup
    print("\n[Cleanup] Removing test data...")
    try:
        Borrower.objects.filter(rfid_uid=test_rfid).delete()
        print("✓ Cleanup complete")
    except Exception as e:
        print(f"✗ Cleanup failed: {e}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

def test_deletion_with_transactions():
    """Test borrower deletion when transactions exist"""
    
    test_rfid = "TEST-RFID-TXN-123"
    test_name = "Test Borrower with Transactions"
    
    print("\n" + "=" * 70)
    print("BORROWER DELETION WITH TRANSACTIONS TEST")
    print("=" * 70)
    
    # Create test borrower
    print("\n[Step 1] Creating borrower and transactions...")
    try:
        borrower = Borrower.objects.create(
            name=test_name,
            rfid_uid=test_rfid,
            email="txn@example.com"
        )
        print(f"✓ Borrower created: {borrower}")
        
        # Create or get an item
        item, created = Item.objects.get_or_create(
            name="Test Item",
            defaults={"qr_code": "TEST-QR-123", "description": "Test item for transactions"}
        )
        if created:
            print(f"✓ Item created: {item}")
        else:
            print(f"✓ Item already exists: {item}")
        
        # Create a returned transaction
        txn = BorrowTransaction.objects.create(
            borrower=borrower,
            item=item,
            status=BorrowTransaction.Status.RETURNED
        )
        print(f"✓ Transaction created: {txn}")
        print(f"  Transaction count for borrower: {borrower.transactions.count()}")
        
    except Exception as e:
        print(f"✗ Setup failed: {e}")
        return
    
    # Try to delete borrower (should work with the fix)
    print("\n[Step 2] Attempting to delete borrower with transactions...")
    try:
        # Delete returned transactions first
        deleted_count, _ = borrower.transactions.filter(status=BorrowTransaction.Status.RETURNED).delete()
        print(f"✓ Deleted {deleted_count} returned transactions")
        
        # Now delete borrower
        borrower.delete()
        print(f"✓ Borrower deleted successfully")
    except Exception as e:
        print(f"✗ Deletion failed: {e}")
        return
    
    # Try to re-create with same RFID
    print("\n[Step 3] Re-creating borrower with same RFID...")
    try:
        borrower2 = Borrower.objects.create(
            name=test_name,
            rfid_uid=test_rfid,
            email="txn@example.com"
        )
        print(f"✓ Borrower re-created: {borrower2}")
    except IntegrityError as e:
        print(f"✗ INTEGRITY ERROR: {e}")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    # Cleanup
    print("\n[Cleanup] Removing test data...")
    try:
        Borrower.objects.filter(rfid_uid=test_rfid).delete()
        print("✓ Cleanup complete")
    except Exception as e:
        print(f"✗ Cleanup failed: {e}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_borrower_lifecycle()
    test_deletion_with_transactions()
