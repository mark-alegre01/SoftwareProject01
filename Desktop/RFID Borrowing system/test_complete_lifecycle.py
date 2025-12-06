#!/usr/bin/env python
"""
Test complete borrower lifecycle via API endpoints.
Simulates what the user does: delete via API, then register via API.
"""
import os
import sys
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rfid_borrowing.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from core.models import Borrower, BorrowTransaction, Item

def setup_admin_user():
    """Create or get admin user for testing"""
    admin, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'is_staff': True,
            'is_superuser': True,
            'email': 'admin@example.com'
        }
    )
    if created:
        admin.set_password('admin')
        admin.save()
    return admin

def test_complete_api_lifecycle():
    """Test complete API lifecycle: create borrower, delete via API, register via API"""
    
    client = Client()
    test_rfid = "COMPLETE-TEST-123"
    test_name = "Complete Lifecycle Test"
    test_email = "lifecycle@example.com"
    
    print("=" * 70)
    print("COMPLETE BORROWER LIFECYCLE API TEST")
    print("=" * 70)
    
    # Setup admin user
    print("\n[Setup] Creating admin user...")
    admin = setup_admin_user()
    client.force_login(admin)
    print(f"✓ Admin user ready")
    
    # Step 1: Create borrower
    print("\n[Step 1] Creating borrower...")
    try:
        borrower = Borrower.objects.create(
            name=test_name,
            rfid_uid=test_rfid,
            email=test_email
        )
        borrower_id = borrower.id
        print(f"✓ Borrower created: {borrower} (ID: {borrower_id})")
    except Exception as e:
        print(f"✗ Failed to create borrower: {e}")
        return
    
    # Step 2: Delete via API
    print("\n[Step 2] Deleting borrower via API...")
    try:
        response = client.delete(f'/api/borrowers/{borrower_id}')
        print(f"  Response Status: {response.status_code}")
        
        if response.status_code == 204:
            print(f"✓ Borrower deleted successfully via API")
        else:
            print(f"✗ Delete failed: {response.status_code}")
            try:
                print(f"  Response: {response.json()}")
            except:
                print(f"  Response: {response.content}")
            return
    except Exception as e:
        print(f"✗ Delete request failed: {e}")
        return
    
    # Step 3: Verify deletion
    print("\n[Step 3] Verifying deletion...")
    exists = Borrower.objects.filter(rfid_uid=test_rfid).exists()
    print(f"  Borrower exists in DB: {exists}")
    
    if exists:
        print(f"✗ ERROR: Borrower still exists after deletion!")
        remaining = Borrower.objects.filter(rfid_uid=test_rfid)
        for b in remaining:
            print(f"    - ID: {b.id}, Name: {b.name}, RFID: {b.rfid_uid}")
        return
    else:
        print(f"✓ Borrower successfully deleted from database")
    
    # Step 4: Re-register via API
    print("\n[Step 4] Re-registering borrower with same RFID...")
    
    payload = {
        "name": test_name,
        "email": test_email,
        "rfid_uid": test_rfid
    }
    
    # Note: We're not logged in for this request - simulating public registration
    client.logout()
    
    try:
        response = client.post(
            '/api/register-borrower',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        print(f"  Response Status: {response.status_code}")
        response_data = response.json()
        
        if response.status_code == 201:
            print(f"✓ SUCCESS: Borrower re-registered successfully!")
            print(f"  New Borrower ID: {response_data.get('id')}")
            print(f"  Response: {json.dumps(response_data, indent=2)}")
            
            # Cleanup
            Borrower.objects.filter(rfid_uid=test_rfid).delete()
            
        else:
            print(f"✗ FAILED: Re-registration failed with status {response.status_code}")
            print(f"  Response: {json.dumps(response_data, indent=2)}")
            
    except Exception as e:
        print(f"✗ Re-registration request failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("LIFECYCLE TEST COMPLETE")
    print("=" * 70)

def test_with_returned_transactions():
    """Test deletion with returned transactions present"""
    
    client = Client()
    test_rfid = "WITH-TXN-TEST-456"
    test_name = "Borrower with Transactions"
    
    print("\n" + "=" * 70)
    print("BORROWER DELETION WITH RETURNED TRANSACTIONS VIA API")
    print("=" * 70)
    
    # Setup admin user
    print("\n[Setup] Creating admin user...")
    admin = setup_admin_user()
    client.force_login(admin)
    print(f"✓ Admin user ready")
    
    # Create borrower with transactions
    print("\n[Step 1] Creating borrower and transactions...")
    try:
        borrower = Borrower.objects.create(
            name=test_name,
            rfid_uid=test_rfid,
            email="txn@example.com"
        )
        borrower_id = borrower.id
        print(f"✓ Borrower created: {borrower}")
        
        # Create item and transaction
        item, _ = Item.objects.get_or_create(
            name="Test Item for TXN",
            defaults={"qr_code": "TEST-TXN-QR"}
        )
        
        txn = BorrowTransaction.objects.create(
            borrower=borrower,
            item=item,
            status=BorrowTransaction.Status.RETURNED
        )
        print(f"✓ Created returned transaction")
        print(f"  Transactions for borrower: {borrower.transactions.count()}")
        
    except Exception as e:
        print(f"✗ Setup failed: {e}")
        return
    
    # Delete borrower via API
    print("\n[Step 2] Deleting borrower with returned transactions...")
    try:
        response = client.delete(f'/api/borrowers/{borrower_id}')
        print(f"  Response Status: {response.status_code}")
        
        if response.status_code == 204:
            print(f"✓ Borrower deleted successfully")
        else:
            print(f"✗ Delete failed: {response.status_code}")
            try:
                print(f"  Response: {response.json()}")
            except:
                print(f"  Response: {response.content}")
    except Exception as e:
        print(f"✗ Delete failed: {e}")
    
    # Try to re-register
    print("\n[Step 3] Re-registering with same RFID...")
    client.logout()
    
    payload = {
        "name": test_name,
        "email": "txn@example.com",
        "rfid_uid": test_rfid
    }
    
    try:
        response = client.post(
            '/api/register-borrower',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        if response.status_code == 201:
            print(f"✓ Re-registration successful!")
            Borrower.objects.filter(rfid_uid=test_rfid).delete()
        else:
            print(f"✗ Re-registration failed: {response.status_code}")
            print(f"  Response: {response.json()}")
            
    except Exception as e:
        print(f"✗ Re-registration failed: {e}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_complete_api_lifecycle()
    test_with_returned_transactions()
