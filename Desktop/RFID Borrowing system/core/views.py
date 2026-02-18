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
from django.shortcuts import render

import qrcode
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import concurrent.futures
import socket
import urllib.request
import urllib.error
from typing import List, Dict

from .models import Borrower, Item, BorrowTransaction, RFIDScan
from .models import DeviceConfig, DeviceInstance
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
    DeviceConfigSerializer,
    DeviceConfigForDeviceSerializer,
    DeviceInstanceSerializer,
)
from .models import DeviceConfig
from .auth import DeviceTokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


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
        # Allow unauthenticated scans for development/local use
        # In production, you could add authentication here
        
        serializer = RFIDScanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scan = RFIDScan.objects.create(**serializer.validated_data)

        # Update device telemetry if authenticated
        try:
            auth = DeviceTokenAuthentication()
            res = auth.authenticate(request)
            if res:
                device, _ = res
                device.server_reachable = True
                device.last_wifi_event = 'scan_post'
                device.save(update_fields=["server_reachable", "last_wifi_event", "last_seen"])
        except:
            # No authentication, but that's okay for scans
            pass

        excess_ids = list(
            RFIDScan.objects.order_by("-created_at").values_list("id", flat=True)[200:]
        )
        if excess_ids:
            RFIDScan.objects.filter(id__in=excess_ids).delete()

        return Response(RFIDScanSerializer(scan).data, status=status.HTTP_201_CREATED)


class DeviceConfigView(APIView):
    """Get / update the device (ESP32) configuration used by the web app.

    GET: returns current DeviceConfig (creates empty one if missing)
    POST: updates values (admin only)
    """
    def get(self, request):
        obj, _ = DeviceConfig.objects.get_or_create(id=1)
        # If a device authenticates using X-Device-Token, return plaintext password + ssid
        try:
            auth = DeviceTokenAuthentication()
            res = auth.authenticate(request)
            if res:
                device, _ = res
                serializer = DeviceConfigForDeviceSerializer(obj)
                return Response(serializer.data)
        except AuthenticationFailed:
            # Invalid token -> treat as anonymous (do not reveal password)
            pass

        return Response(DeviceConfigSerializer(obj).data)

    def post(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        obj, _ = DeviceConfig.objects.get_or_create(id=1)
        serializer = DeviceConfigSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DeviceInstanceView(APIView):
    """Endpoint for ESPs to register themselves and for UI to list devices.

    POST: an ESP can POST { ip, ssid, api_host, firmware } to register/update its record.
    GET: returns list of registered devices (recent first).
    """
    def get(self, request):
        devices = DeviceInstance.objects.all()[:50]
        return Response(DeviceInstanceSerializer(devices, many=True, context={'request': request}).data)

    def post(self, request):
        data = request.data or {}
        ip = data.get('ip') or request.META.get('REMOTE_ADDR')
        if not ip:
            return Response({"detail": "IP required"}, status=status.HTTP_400_BAD_REQUEST)

        obj, _ = DeviceInstance.objects.update_or_create(
            ip=ip,
            defaults={
                'ssid': data.get('ssid', '')[:128],
                'api_host': data.get('api_host', '')[:256],
                'firmware': data.get('firmware', '')[:64],
                'pairing_code': data.get('pairing_code', '')[:32],
                'last_wifi_event': data.get('wifi_event', '')[:64],
                'last_rssi': data.get('rssi'),
                'last_disconnect_reason': data.get('disconnect_reason', '')[:128],
                'server_reachable': bool(data.get('server_reachable', False)),
            }
        )
        return Response(DeviceInstanceSerializer(obj, context={'request': request}).data, status=status.HTTP_200_OK)


class TestApiHostView(APIView):
    """POST: { url: 'http://host:port/' } - server-side reachability test for an API host."""
    def post(self, request):
        url = (request.data.get('url') or '').strip()
        if not url:
            return Response({"detail": "url required"}, status=status.HTTP_400_BAD_REQUEST)

        import urllib.request, urllib.error, socket
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=6) as r:
                return Response({"status": "ok", "code": r.getcode()})
        except socket.timeout:
            return Response({"detail": "Timed out contacting host"}, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except urllib.error.URLError as e:
            # Provide friendlier messages for common failure modes
            reason = getattr(e, 'reason', None)
            try:
                import errno as _errno
                if isinstance(reason, ConnectionRefusedError) or (isinstance(reason, OSError) and getattr(reason, 'errno', None) in (_errno.ECONNREFUSED, getattr(_errno, 'WSAECONNREFUSED', None))):
                    return Response({"detail": "Connection refused: no service listening at that host/port"}, status=status.HTTP_502_BAD_GATEWAY)
                if isinstance(reason, socket.gaierror):
                    return Response({"detail": "Name resolution failed (host not found)"}, status=status.HTTP_502_BAD_GATEWAY)
            except Exception:
                # fall through to generic message
                pass
            detail = str(reason) if reason else str(e)
            return Response({"detail": detail}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as e:
            # malformed URL or similar client-side issues
            return Response({"detail": "Invalid URL: " + str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class PingView(APIView):
    """Simple health check endpoint for devices/tools to verify server reachability."""
    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class ClaimDeviceView(APIView):
    """Allow an authenticated user to claim a device by providing the pairing code."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        device_id = request.data.get('device_id')
        code = (request.data.get('pairing_code') or '').strip()
        if not device_id or not code:
            return Response({"detail": "device_id and pairing_code required"}, status=status.HTTP_400_BAD_REQUEST)
        device = get_object_or_404(DeviceInstance, id=device_id)
        if device.pairing_code and code == device.pairing_code:
            device.claimed_by = request.user
            device.claimed_at = timezone.now()
            device.save(update_fields=['claimed_by', 'claimed_at'])
            return Response(DeviceInstanceSerializer(device, context={'request': request}).data)
        return Response({"detail": "Invalid pairing code"}, status=status.HTTP_403_FORBIDDEN)


class DeviceInstanceTokenView(APIView):
    """Allow a device owner or admin to retrieve or regenerate the device token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        device_id = request.data.get('device_id')
        regenerate = bool(request.data.get('regenerate', True))
        if not device_id:
            return Response({"detail": "device_id required"}, status=status.HTTP_400_BAD_REQUEST)
        device = get_object_or_404(DeviceInstance, id=device_id)
        # Only owner or staff can request/regenerate token
        if not (request.user.is_staff or (device.claimed_by and device.claimed_by == request.user)):
            return Response({"detail": "Only device owner or admin can generate token."}, status=status.HTTP_403_FORBIDDEN)
        if regenerate:
            token = device.regenerate_token()
        else:
            token = device.api_token
        return Response({"api_token": token})


def push_config_to_target(target_ip, retries: int = 3, reboot_on_reset: bool = False):
    """Helper that posts the canonical DeviceConfig to the target device ip and returns a tuple (ok_bool, response_or_detail, http_code).

    Performs a lightweight TCP probe to ensure the device is reachable quickly, increases the POST timeout, and retries transient errors.
    """
    obj, _ = DeviceConfig.objects.get_or_create(id=1)
    payload = {
        'ssid': obj.ssid or '',
        'password': obj.get_password() or '',
        'api_host': obj.api_host or ''
    }
    import urllib.request, json, urllib.error, socket, time, errno
    url = f"http://{target_ip}/apply-config"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')

    # Quick TCP-level probe to fail fast if device is offline/unreachable
    try:
        sock = socket.create_connection((target_ip, 80), timeout=3)
        sock.close()
    except Exception as e:
        logging.warning("Push to %s TCP connect failed: %s", target_ip, e)
        return False, f"TCP connect failed: {e}", 502

    # Lightweight HTTP GET probe before POST to detect flaky HTTP servers
    try:
        probe_req = urllib.request.Request(f'http://{target_ip}/', method='GET')
        with urllib.request.urlopen(probe_req, timeout=2) as _:
            logging.debug('Pre-POST GET probe to %s succeeded', target_ip)
    except Exception as e:
        # Not fatal; log and continue. Some devices may only accept POST or briefly reset when Wi-Fi changes.
        logging.debug('Pre-POST GET probe to %s failed (continuing): %s', target_ip, e)

    attempt = 0
    while True:
        attempt += 1
        try:
            # Increase timeout a bit for noisy networks
            with urllib.request.urlopen(req, timeout=20) as r:
                resp_body = r.read().decode('utf-8')
                return True, {'code': r.getcode(), 'body': resp_body}, r.getcode()
        except socket.timeout as e:
            logging.warning("Push to %s timed out (attempt %d/%d): %s", target_ip, attempt, retries + 1, e)
            detail = "Timed out connecting to device"
            code = 504
        except urllib.error.URLError as e:
            # Check for wrapped OSError/ConnectionResetError reasons
            reason = getattr(e, 'reason', None)
            if isinstance(reason, ConnectionResetError) or (isinstance(reason, OSError) and getattr(reason, 'errno', None) == errno.WSAECONNRESET):
                logging.warning("Push to %s connection reset (attempt %d/%d): %s", target_ip, attempt, retries + 1, reason)
                detail = f"Connection reset by device (attempt {attempt}/{retries + 1}): {reason}"
                code = 502
                # Optional: if requested, try to reboot the device once and then retry
                if reboot_on_reset and attempt == 1:
                    try:
                        logging.info('Attempting reboot on %s due to connection reset', target_ip)
                        rb_ok, rb_resp, rb_code = push_command_to_target(target_ip, 'reboot')
                        if rb_ok:
                            logging.info('Reboot command accepted by %s; waiting briefly before retry', target_ip)
                            time.sleep(5)
                            # update detail with reboot info
                            detail += f' (reboot attempted, code={rb_code})'
                        else:
                            logging.warning('Reboot command to %s failed: %s', target_ip, rb_resp)
                            detail += f' (reboot attempt failed: {rb_resp})'
                    except Exception as _e:
                        logging.exception('Error attempting reboot on %s', target_ip)
                        detail += f' (reboot attempt exception: {_e})'
            else:
                logging.warning("Push to %s URL error (attempt %d/%d): %s", target_ip, attempt, retries + 1, e)
                detail = str(reason) if reason else str(e)
                code = 502
        except OSError as e:
            # Direct OSError (e.g., ConnectionResetError propagated)
            if isinstance(e, ConnectionResetError) or getattr(e, 'errno', None) == errno.WSAECONNRESET:
                logging.warning("Push to %s connection reset OSError (attempt %d/%d): %s", target_ip, attempt, retries + 1, e)
                detail = "Connection reset by device"
                code = 502
            else:
                logging.exception("OSError when pushing config to %s", target_ip)
                detail = str(e)
                code = 502
        except Exception as e:
            logging.exception("Unexpected error pushing config to %s (attempt %d/%d)", target_ip, attempt, retries + 1)
            detail = str(e)
            code = 502

        # Retry logic for transient errors (timeout/temporary URLError)
        if attempt <= retries and code in (504, 502):
            time.sleep(0.8 * attempt)  # small backoff
            continue

        return False, detail, code


def push_command_to_target(target_ip, action: str, payload: dict = None, timeout: int = 10):
    """POST a control command to the target device at /control. Returns (ok, detail, code)."""
    import urllib.request, urllib.error, json, socket
    url = f"http://{target_ip}/control"
    body = {'action': action}
    if payload:
        body.update(payload)
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp_body = r.read().decode('utf-8')
            return True, {'code': r.getcode(), 'body': resp_body}, r.getcode()
    except socket.timeout:
        logging.warning('Command %s to %s timed out', action, target_ip)
        return False, 'Timed out contacting device', 504
    except urllib.error.HTTPError as e:
        # Capture the HTTP status and any body the device returned
        try:
            body = e.read().decode('utf-8', errors='ignore')
        except Exception:
            body = None
        logging.warning('HTTPError from %s for %s: %s %s', target_ip, action, e.code, body)
        # Fallback: some devices expose a /reboot endpoint instead of /control for reboot action
        if action.lower() == 'reboot':
            # Try multiple fallback strategies to trigger a reboot on various firmwares
            fallbacks = []
            # Try POST /reboot with empty JSON
            fallbacks.append(('POST /reboot (empty JSON)', f'http://{target_ip}/reboot', 'application/json', json.dumps({}).encode('utf-8')))
            # Try POST /control with common alternative json fields
            fallbacks.append(('POST /control json cmd', f'http://{target_ip}/control', 'application/json', json.dumps({'cmd':'reboot'}).encode('utf-8')))
            fallbacks.append(('POST /control json command', f'http://{target_ip}/control', 'application/json', json.dumps({'command':'reboot'}).encode('utf-8')))
            fallbacks.append(('POST /control json action=restart', f'http://{target_ip}/control', 'application/json', json.dumps({'action':'restart'}).encode('utf-8')))
            # Form-encoded
            fallbacks.append(('POST /control form action=reboot', f'http://{target_ip}/control', 'application/x-www-form-urlencoded', 'action=reboot'.encode('utf-8')))
            # Plain text body
            fallbacks.append(('POST /control text reboot', f'http://{target_ip}/control', 'text/plain', b'reboot'))
            # GET /reboot
            fallbacks.append(('GET /reboot', f'http://{target_ip}/reboot', 'GET', None))

            for label, url_fb, ctype, body_fb in fallbacks:
                try:
                    logging.debug('Attempting fallback %s -> %s', label, url_fb)
                    if body_fb is None and ctype == 'GET':
                        req_fb = urllib.request.Request(url_fb, method='GET')
                    else:
                        req_fb = urllib.request.Request(url_fb, data=body_fb, headers={'Content-Type': ctype}, method='POST')
                    with urllib.request.urlopen(req_fb, timeout=timeout) as r2:
                        resp_body = r2.read().decode('utf-8', errors='ignore')
                        logging.info('Fallback %s to %s succeeded: %s', label, target_ip, r2.getcode())
                        return True, {'code': r2.getcode(), 'body': resp_body, 'fallback': label}, r2.getcode()
                except Exception as e2:
                    logging.debug('Fallback %s to %s failed: %s', label, target_ip, e2)
        detail = f'HTTP {e.code}: {e.reason}' + (f". Body: {body[:256]}" if body else '')
        return False, detail, e.code
    except urllib.error.URLError as e:
        # Network-level errors like connection reset or address errors
        reason = getattr(e, 'reason', None)
        try:
            import errno as _errno
            if isinstance(reason, ConnectionResetError) or (isinstance(reason, OSError) and getattr(reason, 'errno', None) in (_errno.WSAECONNRESET, _errno.ECONNRESET if hasattr(_errno, 'ECONNRESET') else None)):
                logging.warning('Command %s to %s connection reset: %s', action, target_ip, reason)
                detail = f'Connection reset by device: {reason}'
                # For certain actions, try alternative endpoints/payloads similar to reboot fallbacks
                if action.lower() in ('reboot', 'startap', 'disconnect', 'stopap'):
                    fallbacks = []
                    # For startap and similar actions, try explicit endpoints and alternative payloads
                    if action.lower() == 'startap':
                        fallbacks.append(('POST /startap (empty JSON)', f'http://{target_ip}/startap', 'application/json', json.dumps({}).encode('utf-8')))
                        fallbacks.append(('GET /startap', f'http://{target_ip}/startap', 'GET', None))
                        fallbacks.append(('POST /control json cmd=startap', f'http://{target_ip}/control', 'application/json', json.dumps({'cmd':'startap'}).encode('utf-8')))
                        fallbacks.append(('POST /control json action=startap', f'http://{target_ip}/control', 'application/json', json.dumps({'action':'startap'}).encode('utf-8')))
                        fallbacks.append(('POST /control form action=startap', f'http://{target_ip}/control', 'application/x-www-form-urlencoded', 'action=startap'.encode('utf-8')))
                    else:
                        # Generic fallback attempts for other control actions
                        fallbacks.append((f'POST /{action} (empty JSON)', f'http://{target_ip}/{action}', 'application/json', json.dumps({}).encode('utf-8')))
                        fallbacks.append((f'GET /{action}', f'http://{target_ip}/{action}', 'GET', None))
                        fallbacks.append((f'POST /control form action={action}', f'http://{target_ip}/control', 'application/x-www-form-urlencoded', f'action={action}'.encode('utf-8')))

                    for label, url_fb, ctype, body_fb in fallbacks:
                        try:
                            logging.debug('Attempting fallback %s -> %s', label, url_fb)
                            if body_fb is None and ctype == 'GET':
                                req_fb = urllib.request.Request(url_fb, method='GET')
                            else:
                                req_fb = urllib.request.Request(url_fb, data=body_fb, headers={'Content-Type': ctype}, method='POST')
                            with urllib.request.urlopen(req_fb, timeout=timeout) as r2:
                                resp_body = r2.read().decode('utf-8', errors='ignore')
                                logging.info('Fallback %s to %s succeeded: %s', label, target_ip, r2.getcode())
                                return True, {'code': r2.getcode(), 'body': resp_body, 'fallback': label}, r2.getcode()
                        except Exception as e2:
                            logging.debug('Fallback %s to %s failed: %s', label, target_ip, e2)
                return False, detail, 502
        except Exception:
            pass
        # Generic URLError fallback
        logging.warning('URLError sending command %s to %s: %s', action, target_ip, e)
        return False, str(e), 502
    except Exception as e:
        logging.exception('Error sending command %s to %s', action, target_ip)
        return False, str(e), 502


class PushDeviceConfigView(APIView):
    """Admin-only: push the canonical DeviceConfig to a device (by id or ip)."""
    def post(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        device_id = request.data.get('device_id')
        ip = request.data.get('ip')
        if not device_id and not ip:
            return Response({"detail": "device_id or ip required"}, status=status.HTTP_400_BAD_REQUEST)

        device = None
        if device_id:
            device = get_object_or_404(DeviceInstance, id=device_id)
            target_ip = device.ip
        else:
            target_ip = ip

        reboot_on_reset = bool(request.data.get('reboot_on_reset', False))
        ok, resp, code = push_config_to_target(target_ip, reboot_on_reset=reboot_on_reset)
        if ok:
            return Response({"status": "ok", "code": resp.get('code'), "body": resp.get('body'), "reboot_attempted": reboot_on_reset})
        # include reboot flag for diagnosis
        return Response({"status": "error", "detail": resp, "reboot_attempted": reboot_on_reset}, status=code)


class DeviceInstanceDetailView(APIView):
    def get(self, request, device_id: int):
        device = get_object_or_404(DeviceInstance, id=device_id)
        return Response(DeviceInstanceSerializer(device, context={'request': request}).data)


class ProvisionDeviceView(APIView):
    """Allow a device owner or admin to trigger a provisioning push."""
    permission_classes = [IsAuthenticated]

    def post(self, request, device_id: int):
        device = get_object_or_404(DeviceInstance, id=device_id)
        # Only owner (claimed_by) or staff can provision
        if not (request.user.is_staff or (device.claimed_by and device.claimed_by == request.user)):
            return Response({"detail": "Only device owner or admin can provision."}, status=status.HTTP_403_FORBIDDEN)

        reboot_on_reset = bool(request.data.get('reboot_on_reset', False))
        ok, resp, code = push_config_to_target(device.ip, reboot_on_reset=reboot_on_reset)
        if ok:
            return Response({"status": "ok", "code": resp.get('code'), "body": resp.get('body'), "reboot_attempted": reboot_on_reset})
        return Response({"status": "error", "detail": resp, "reboot_attempted": reboot_on_reset}, status=code)


class DeviceControlView(APIView):
    """Allow owner/admin to send control commands to a device (disconnect/startap/stopap/etc)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        device_id = request.data.get('device_id')
        ip = request.data.get('ip')
        action = (request.data.get('action') or '').strip()
        if not action or (not device_id and not ip):
            return Response({"detail": "action and (device_id or ip) required"}, status=status.HTTP_400_BAD_REQUEST)

        target_ip = None
        # If device_id provided, allow either device owner (claimed_by) or staff
        if device_id:
            device = get_object_or_404(DeviceInstance, id=device_id)
            if not (request.user.is_staff or (device.claimed_by and device.claimed_by == request.user)):
                return Response({"detail": "Only device owner or admin can send control commands."}, status=status.HTTP_403_FORBIDDEN)
            target_ip = device.ip
        else:
            # Raw IP commands require admin privilege
            if not request.user.is_staff:
                return Response({"detail": "Admin access required for raw IP commands."}, status=status.HTTP_403_FORBIDDEN)
            target_ip = ip

        ok, resp, code = push_command_to_target(target_ip, action, payload=request.data.get('payload'))
        if ok:
            return Response({"status": "ok", "code": resp.get('code'), "body": resp.get('body')})
        return Response({"status": "error", "detail": resp}, status=code)


class PushDeviceConfigAllView(APIView):
    """Admin-only: push current DeviceConfig to all discovered devices."""
    def post(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
        devices = DeviceInstance.objects.all()
        results = []
        for d in devices:
            ok, resp, code = push_config_to_target(d.ip)
            results.append({ 'device_id': d.id, 'ip': d.ip, 'ok': ok, 'detail': resp })
        return Response({ 'results': results })


class ScanDevicesView(APIView):
    """Quick LAN scan to discover ESP devices on the local /24 network.

    GET: returns a list of discovered devices (ip, probe_code, body_snippet)
    """
    def get_local_ip(self) -> str:
        """Return a likely outbound local IP (doesn't require internet access)."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # This does not actually send packets; it's used to determine the local IP used for outbound traffic
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = None
        finally:
            try:
                s.close()
            except Exception:
                pass
        return ip or '127.0.0.1'

    def probe(self, ip: str) -> Dict:
        """Probe a single IP for an HTTP response on port 80. Returns dict with info on success."""
        result = {'ip': ip, 'ok': False, 'code': None, 'body': None}
        try:
            # Quick TCP probe
            sock = socket.create_connection((ip, 80), timeout=0.6)
            sock.close()
        except Exception as e:
            return result

        # If TCP succeeded, try a small HTTP GET to / (and /info) with short timeout
        for path in ('/', '/info', '/device-info'):
            try:
                req = urllib.request.Request(f'http://{ip}{path}', method='GET')
                with urllib.request.urlopen(req, timeout=1.2) as r:
                    body = r.read(1024).decode('utf-8', errors='ignore')
                    result.update({'ok': True, 'code': r.getcode(), 'body': body[:512]})
                    return result
            except Exception:
                continue

        # If TCP succeeded but no HTTP response recognized, mark reachable anyway
        result['ok'] = True
        return result

    def get(self, request):
        # Determine local /24 to scan
        local_ip = self.get_local_ip()
        parts = local_ip.split('.')
        if len(parts) != 4:
            return Response({'detail': 'Unable to determine local network'}, status=status.HTTP_400_BAD_REQUEST)
        base = '.'.join(parts[:3])
        candidates = [f"{base}.{i}" for i in range(1, 255)]

        results: List[Dict] = []
        # Parallelize probes
        with concurrent.futures.ThreadPoolExecutor(max_workers=40) as ex:
            futures = {ex.submit(self.probe, ip): ip for ip in candidates}
            for fut in concurrent.futures.as_completed(futures, timeout=30):
                try:
                    r = fut.result()
                    if r.get('ok'):
                        results.append(r)
                except Exception:
                    continue

        return Response({'devices': results})


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


