#!/usr/bin/env python
"""
Test API endpoint for borrower registration after deletion.
This simulates the exact JavaScript fetch call from the frontend.
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

def test_api_borrower_registration():
    """Test the API registration endpoint"""
    
    client = Client()
    test_rfid = "API-TEST-12345"
    test_name = "API Test Borrower"
    test_email = "apitest@example.com"
    
    print("=" * 70)
    print("BORROWER REGISTRATION API TEST")
    print("=" * 70)
    
    # Step 1: Create and delete a borrower with this RFID
    print("\n[Step 1] Creating and deleting borrower with RFID...")
    try:
        borrower = Borrower.objects.create(
            name=test_name,
            rfid_uid=test_rfid,
            email=test_email
        )
        print(f"✓ Borrower created: {borrower}")
        
        # Delete returned transactions if any
        borrower.transactions.filter(status=BorrowTransaction.Status.RETURNED).delete()
        
        # Delete borrower
        borrower.delete()
        print(f"✓ Borrower deleted")
        
        # Verify deletion
        exists = Borrower.objects.filter(rfid_uid=test_rfid).exists()
        print(f"  Borrower still exists in DB: {exists}")
        
    except Exception as e:
        print(f"✗ Setup failed: {e}")
        return
    
    # Step 2: Try to register via API
    print("\n[Step 2] Calling registration API endpoint...")
    
    payload = {
        "name": test_name,
        "email": test_email,
        "rfid_uid": test_rfid
    }
    
    print(f"  Request payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = client.post(
            '/api/register-borrower',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        print(f"\n  Response Status: {response.status_code}")
        print(f"  Response Headers: {dict(response)}")
        
        response_data = response.json()
        print(f"  Response Data: {json.dumps(response_data, indent=2)}")
        
        if response.status_code == 201:
            print(f"\n✓ SUCCESS: Borrower registered via API")
            print(f"  Registered borrower ID: {response_data.get('id')}")
            
            # Cleanup
            Borrower.objects.filter(rfid_uid=test_rfid).delete()
            
        else:
            print(f"\n✗ FAILED: API returned status {response.status_code}")
            if 'detail' in response_data:
                print(f"  Error detail: {response_data['detail']}")
            
    except Exception as e:
        print(f"✗ API call failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 3: Test with different RFID formats
    print("\n[Step 3] Testing with whitespace in RFID...")
    
    payload_with_spaces = {
        "name": "Test with Spaces",
        "email": "space@example.com",
        "rfid_uid": "  TEST-SPACES-123  "  # With leading/trailing spaces
    }
    
    print(f"  Request payload: {json.dumps(payload_with_spaces, indent=2)}")
    
    try:
        response = client.post(
            '/api/register-borrower',
            data=json.dumps(payload_with_spaces),
            content_type='application/json'
        )
        
        print(f"\n  Response Status: {response.status_code}")
        response_data = response.json()
        
        if response.status_code == 201:
            print(f"✓ Registered successfully despite spaces")
            print(f"  Stored RFID: {response_data.get('rfid_uid')}")
            borrower_id = response_data.get('id')
            
            # Try to register again with the same RFID but different spacing
            payload_different_spacing = {
                "name": "Different Spacing",
                "email": "different@example.com",
                "rfid_uid": " TEST-SPACES-123 "  # Different spacing
            }
            
            response2 = client.post(
                '/api/register-borrower',
                data=json.dumps(payload_different_spacing),
                content_type='application/json'
            )
            
            print(f"\n  Second attempt status: {response2.status_code}")
            if response2.status_code != 201:
                data2 = response2.json()
                print(f"  Second attempt response: {json.dumps(data2, indent=2)}")
            
            # Cleanup
            Borrower.objects.filter(rfid_uid="TEST-SPACES-123").delete()
        else:
            print(f"✗ Failed: {response.json()}")
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
    
    print("\n" + "=" * 70)
    print("API TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_api_borrower_registration()
