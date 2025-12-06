from __future__ import annotations

import json
import uuid
from io import BytesIO

from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.http import url_has_allowed_host_and_scheme

import qrcode
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Borrower, Item, BorrowTransaction, RFIDScan
from .serializers import (
    BorrowerSerializer,
    ItemSerializer,
    BorrowTransactionSerializer,
    BorrowCreateSerializer,
    ReturnSerializer,
    ScanIdSerializer,
    BorrowerRegistrationSerializer,
    ItemRegistrationSerializer,
    RFIDScanSerializer,
    RFIDScanCreateSerializer,
)


class BorrowCreateView(APIView):
    def post(self, request):
        serializer = BorrowCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        borrower_rfid = serializer.validated_data["borrower_rfid"].strip()
        item_qr = serializer.validated_data["item_qr"].strip()

        try:
            borrower = Borrower.objects.get(rfid_uid=borrower_rfid)
        except Borrower.DoesNotExist:
            return Response({"detail": "Borrower not registered. Please register first."}, status=status.HTTP_404_NOT_FOUND)

        # Item must be registered - no auto-creation
        try:
            item = Item.objects.get(qr_code=item_qr)
        except Item.DoesNotExist:
            return Response({"detail": "Item not registered. Please register the item first."}, status=status.HTTP_404_NOT_FOUND)
        
        # If item exists but is inactive, reactivate it
        if not item.is_active:
            item.is_active = True
            item.save(update_fields=["is_active"])

        # Ensure item is not currently out
        if BorrowTransaction.objects.filter(item=item, status=BorrowTransaction.Status.OPEN).exists():
            return Response({"detail": "Item already borrowed"}, status=status.HTTP_409_CONFLICT)

        # Create new transaction
        with transaction.atomic():
            tx = BorrowTransaction.objects.create(borrower=borrower, item=item)

        return Response(BorrowTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class ReturnView(APIView):
    def post(self, request):
        serializer = ReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item_qr = serializer.validated_data.get("item_qr")
        if isinstance(item_qr, str):
            item_qr = item_qr.strip()
            if not item_qr:
                item_qr = None
        transaction_id = serializer.validated_data.get("transaction_id")

        try:
            if transaction_id:
                tx = BorrowTransaction.objects.get(id=transaction_id, status=BorrowTransaction.Status.OPEN)
            elif item_qr:
                item = Item.objects.get(qr_code__iexact=item_qr)
                tx = BorrowTransaction.objects.get(item=item, status=BorrowTransaction.Status.OPEN)
            else:
                raise BorrowTransaction.DoesNotExist
        except (BorrowTransaction.DoesNotExist, Item.DoesNotExist):
            return Response({"detail": "Open transaction not found"}, status=status.HTTP_404_NOT_FOUND)

        tx.status = BorrowTransaction.Status.RETURNED
        tx.returned_at = timezone.now()
        tx.save(update_fields=["status", "returned_at"])

        return Response(BorrowTransactionSerializer(tx).data)


class BorrowerView(APIView):
    def get(self, request):
        q = request.GET.get("q")
        queryset = Borrower.objects.all()
        if q:
            # Case-insensitive search for both name and RFID UID
            q_upper = q.strip().upper()
            queryset = queryset.filter(
                Q(name__icontains=q) | 
                Q(rfid_uid__iexact=q) |  # Exact match (case-insensitive)
                Q(rfid_uid__icontains=q_upper)  # Also try uppercase version
            )
        return Response(BorrowerSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = BorrowerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        borrower = Borrower.objects.create(**serializer.validated_data)
        return Response(BorrowerSerializer(borrower).data, status=status.HTTP_201_CREATED)


class BorrowerDetailView(APIView):
    """Admin-only borrower management (edit/delete)."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, borrower_id: int):
        if not request.user.is_staff:
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        borrower = get_object_or_404(Borrower, id=borrower_id)
        serializer = BorrowerSerializer(borrower, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, borrower_id: int):
        if not request.user.is_staff:
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        borrower = get_object_or_404(Borrower, id=borrower_id)
        
        # Check if borrower has any open (borrowed) transactions
        open_transactions = borrower.transactions.filter(status=BorrowTransaction.Status.OPEN)
        if open_transactions.exists():
            open_count = open_transactions.count()
            return Response(
                {
                    "detail": f"Cannot delete borrower. They currently have {open_count} borrowed item(s). Please return all items first.",
                    "open_transactions_count": open_count
                },
                status=status.HTTP_409_CONFLICT,
            )
        
        # If no open transactions, delete all returned transactions first, then delete borrower
        try:
            # Delete all returned transactions for this borrower
            borrower.transactions.filter(status=BorrowTransaction.Status.RETURNED).delete()
            # Now delete the borrower (should have no transactions left)
            borrower.delete()
        except ProtectedError:
            # This should rarely happen now, but keep as fallback
            return Response(
                {"detail": "Borrower cannot be deleted due to system constraints."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ItemView(APIView):
    def get(self, request):
        q = request.GET.get("q")
        queryset = Item.objects.all()
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(qr_code__icontains=q))
        return Response(ItemSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = ItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = Item.objects.create(**serializer.validated_data)
        return Response(ItemSerializer(item).data, status=status.HTTP_201_CREATED)


class ItemDetailView(APIView):
    """Admin-only item management (edit/delete)."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id: int):
        if not request.user.is_staff:
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        item = get_object_or_404(Item, id=item_id)
        serializer = ItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, item_id: int):
        if not request.user.is_staff:
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        item = get_object_or_404(Item, id=item_id)
        try:
            item.delete()
        except ProtectedError:
            return Response(
                {"detail": "Item cannot be deleted because it is linked to existing transactions."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BorrowTransactionDetailView(APIView):
    """Admin-only editing and deletion of transactions."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, transaction_id: int):
        if not request.user.is_staff:
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        tx = get_object_or_404(BorrowTransaction, id=transaction_id)
        data = request.data or {}
        updated_fields: list[str] = []

        borrower_rfid = data.get("borrower_rfid")
        if isinstance(borrower_rfid, str) and borrower_rfid.strip():
            borrower = get_object_or_404(Borrower, rfid_uid__iexact=borrower_rfid.strip())
            if borrower != tx.borrower:
                tx.borrower = borrower
                updated_fields.append("borrower")

        item_qr = data.get("item_qr")
        if isinstance(item_qr, str) and item_qr.strip():
            item = get_object_or_404(Item, qr_code__iexact=item_qr.strip())
            if item != tx.item:
                tx.item = item
                updated_fields.append("item")

        status_value = data.get("status")
        if isinstance(status_value, str) and status_value.strip():
            status_clean = status_value.strip().upper()
            if status_clean not in BorrowTransaction.Status.values:
                return Response({"detail": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)
            if tx.status != status_clean:
                tx.status = status_clean
                updated_fields.append("status")
                if status_clean == BorrowTransaction.Status.RETURNED:
                    tx.returned_at = timezone.now()
                else:
                    tx.returned_at = None
                updated_fields.append("returned_at")

        if updated_fields:
            # Remove duplicates while preserving order
            unique_fields = list(dict.fromkeys(updated_fields))
            tx.save(update_fields=unique_fields)

        return Response(BorrowTransactionSerializer(tx).data)

    def delete(self, request, transaction_id: int):
        if not request.user.is_staff:
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        tx = get_object_or_404(BorrowTransaction, id=transaction_id)
        tx.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ScanIdView(APIView):
    """Create borrower from RFID scan and immediately create open transaction (log book entry)"""
    def post(self, request):
        serializer = ScanIdSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        borrower_rfid = serializer.validated_data["borrower_rfid"].strip()
        name = serializer.validated_data.get("name", "").strip() or f"RFID {borrower_rfid}"
        email = serializer.validated_data.get("email", "").strip()

        # Record scan for UI use (registration assist)
        RFIDScan.objects.create(uid=borrower_rfid, name=name, email=email)
        # Keep the table small (retain most recent 200 entries)
        excess_ids = list(
            RFIDScan.objects.order_by("-created_at").values_list("id", flat=True)[200:]
        )
        if excess_ids:
            RFIDScan.objects.filter(id__in=excess_ids).delete()

        # Require borrower to exist (no auto-registration)
        try:
            borrower = Borrower.objects.get(rfid_uid=borrower_rfid)
        except Borrower.DoesNotExist:
            return Response(
                {"detail": "Borrower not registered. Please register first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(BorrowerSerializer(borrower).data, status=status.HTTP_200_OK)


class RFIDScanView(APIView):
    """Log raw RFID scans and fetch the most recent scan."""

    def get(self, request):
        scan = RFIDScan.objects.order_by("-created_at").first()
        if not scan:
            return Response({}, status=status.HTTP_204_NO_CONTENT)
        return Response(RFIDScanSerializer(scan).data)

    def post(self, request):
        serializer = RFIDScanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scan = RFIDScan.objects.create(**serializer.validated_data)

        excess_ids = list(
            RFIDScan.objects.order_by("-created_at").values_list("id", flat=True)[200:]
        )
        if excess_ids:
            RFIDScan.objects.filter(id__in=excess_ids).delete()

        return Response(RFIDScanSerializer(scan).data, status=status.HTTP_201_CREATED)


class BorrowerRegistrationView(APIView):
    """Register a new borrower with RFID and optional QR code data"""
    def post(self, request):
        try:
            serializer = BorrowerRegistrationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            rfid_uid = serializer.validated_data["rfid_uid"].strip()
            name = serializer.validated_data["name"].strip()
            email = serializer.validated_data.get("email", "").strip()
            qr_data_raw = serializer.validated_data.get("qr_data", "")
            qr_data = ""
            if isinstance(qr_data_raw, str):
                qr_data = qr_data_raw.strip()
            
            # Parse QR data if provided.
            # Supported formats:
            # 1) JSON: {"name":"...","email":"..."}
            # 2) Pipe-delimited school ID: "LAST,FIRST [MIDDLE]|...|email_like|..."
            if qr_data:
                try:
                    qr_info = json.loads(qr_data)
                    if isinstance(qr_info, dict):
                        name = qr_info.get("name", name)
                        email = qr_info.get("email", email)
                except (json.JSONDecodeError, ValueError):
                    # Non-JSON: try pipe-delimited parsing
                    if "|" in qr_data:
                        parts = [p.strip() for p in qr_data.split("|")]
                        if len(parts) >= 1 and parts[0]:
                            raw_name = parts[0]
                            if "," in raw_name:
                                last, first = [s.strip() for s in raw_name.split(",", 1)]
                                # Normalize capitalization
                                name = f"{first.title()} {last.title()}".strip()
                            else:
                                name = raw_name.title()
                        # Try to extract an email-like value if present
                        if len(parts) >= 3 and parts[2]:
                            possible_email = parts[2].strip()
                            if "@" in possible_email:
                                email = possible_email
                    else:
                        # Treat as plain text name
                        if not name or name == "":
                            name = qr_data
            
            # Check if borrower already exists
            existing_borrower = Borrower.objects.filter(rfid_uid=rfid_uid).first()
            if existing_borrower:
                return Response({
                    "detail": f"Borrower with this RFID UID already exists (ID: {existing_borrower.id})",
                    "existing_borrower_id": existing_borrower.id
                }, status=status.HTTP_409_CONFLICT)
            
            # Try to create the borrower with error handling
            try:
                borrower = Borrower.objects.create(
                    name=name,
                    rfid_uid=rfid_uid,
                    email=email
                )
            except Exception as e:
                # Catch any database constraint violations
                error_msg = str(e)
                if "unique" in error_msg.lower():
                    return Response({
                        "detail": f"RFID UID already exists in database: {error_msg}",
                        "error_type": "unique_constraint"
                    }, status=status.HTTP_409_CONFLICT)
                elif "IntegrityError" in error_msg or "constraint" in error_msg.lower():
                    return Response({
                        "detail": f"Database constraint violation: {error_msg}",
                        "error_type": "integrity_error"
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    raise
            
            return Response(BorrowerSerializer(borrower).data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            # Catch any unexpected errors
            import traceback
            error_details = traceback.format_exc()
            return Response({
                "detail": f"Unexpected error during registration: {str(e)}",
                "error_type": "unexpected_error",
                "error_details": error_details
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ItemRegistrationView(APIView):
    """Register a new item and generate QR code"""
    def post(self, request):
        serializer = ItemRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        name = serializer.validated_data["name"].strip()
        description = serializer.validated_data.get("description", "").strip()
        
        # Generate unique QR code
        qr_code = f"ITEM-{uuid.uuid4().hex[:16].upper()}"
        
        # Ensure uniqueness
        while Item.objects.filter(qr_code=qr_code).exists():
            qr_code = f"ITEM-{uuid.uuid4().hex[:16].upper()}"
        
        item = Item.objects.create(
            name=name,
            qr_code=qr_code,
            description=description,
            is_active=True
        )
        
        return Response(ItemSerializer(item).data, status=status.HTTP_201_CREATED)


class ItemQRCodeView(APIView):
    """Generate and return QR code image for an item"""
    def get(self, request, item_id):
        try:
            item = Item.objects.get(id=item_id)
        except Item.DoesNotExist:
            return Response({"detail": "Item not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(item.qr_code)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Return as HTTP response
        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="item_{item.id}_qr.png"'
        return response


@login_required
def dashboard(request):
    # Show all transactions as a log book (most recent first)
    all_transactions = BorrowTransaction.objects.all()[:100]
    context = {
        "open_transactions": BorrowTransaction.objects.filter(status=BorrowTransaction.Status.OPEN)[:50],
        "recent_returns": BorrowTransaction.objects.filter(status=BorrowTransaction.Status.RETURNED)[:50],
        "all_transactions": all_transactions,  # Log book - all transactions
        "borrower_count": Borrower.objects.count(),
        "item_count": Item.objects.count(),
    }
    return render(request, "core/dashboard.html", context)


@login_required
def borrow_page(request):
    """Borrow item page"""
    return render(request, "core/borrow.html")


@login_required
def return_page(request):
    """Return item page"""
    return render(request, "core/return.html")


@login_required
def register_borrower_page(request):
    """Register borrower page"""
    return render(request, "core/register_borrower.html")


@login_required
def register_item_page(request):
    """Register item page"""
    return render(request, "core/register_item.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    form = AuthenticationForm(request, data=request.POST or None)
    next_value = request.POST.get("next") or request.GET.get("next")
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_username()}!")
            if next_value and url_has_allowed_host_and_scheme(next_value, allowed_hosts={request.get_host()}):
                return redirect(next_value)
            return redirect("core:dashboard")
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "core/login.html", {"form": form, "next_value": next_value})


def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    form = UserCreationForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully. You are now logged in.")
            return redirect("core:dashboard")
        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "core/register.html", {"form": form})


@login_required
def logout_view(request):
    if request.method == "POST":
        username = request.user.get_username()
        logout(request)
        messages.success(request, f"Signed out of {username}.")
        return redirect("core:login")

    return render(request, "core/logout.html")


    """Register item page"""
    return render(request, "core/register_item.html")


