import json
from unittest import mock

from django.urls import reverse
from django.test import TestCase, Client
from django.contrib.auth.models import User

from core.models import DeviceInstance, DeviceConfig

class DevicePushClaimTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user', password='pass')
        self.admin = User.objects.create_superuser(username='admin', password='pass')
        self.device = DeviceInstance.objects.create(ip='10.0.0.5', pairing_code='ABC123', firmware='1.0')
        DeviceConfig.objects.create(api_host='http://example:8000', ssid='XX', password='YY')

    def test_claim_device_success(self):
        self.client.login(username='user', password='pass')
        url = reverse('api-device-instance-claim')
        res = self.client.post(url, json.dumps({'device_id': self.device.id, 'pairing_code': 'ABC123'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.claimed_by.username, 'user')

    def test_claim_device_fail(self):
        self.client.login(username='user', password='pass')
        url = reverse('api-device-instance-claim')
        res = self.client.post(url, json.dumps({'device_id': self.device.id, 'pairing_code': 'WRONG'}), content_type='application/json')
        self.assertEqual(res.status_code, 403)

    @mock.patch('urllib.request.urlopen')
    def test_push_device_config_admin(self, mock_urlopen):
        # Mock successful response
        class DummyResp:
            def __init__(self):
                pass
            def read(self):
                return b'OK'
            def getcode(self):
                return 200
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        mock_urlopen.return_value = DummyResp()

        self.client.login(username='admin', password='pass')
        url = reverse('api-device-instance-push-config')
        res = self.client.post(url, json.dumps({'device_id': self.device.id}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('status', res.json())
        self.assertEqual(res.json()['status'], 'ok')

    def test_push_requires_admin(self):
        self.client.login(username='user', password='pass')
        url = reverse('api-device-instance-push-config')
        res = self.client.post(url, json.dumps({'device_id': self.device.id}), content_type='application/json')
        self.assertEqual(res.status_code, 403)

    def test_device_post_stores_pairing_code(self):
        # Simulate a device heartbeat posting a pairing code
        url = reverse('api-device-instances')
        payload = {'ip': '10.0.0.9', 'pairing_code': 'XYZ999', 'firmware': '1.0', 'ssid': 'XX'}
        res = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        di = DeviceInstance.objects.get(ip='10.0.0.9')
        self.assertEqual(di.pairing_code, 'XYZ999')

    def test_device_post_stores_wifi_fields(self):
        url = reverse('api-device-instances')
        payload = {
            'ip': '10.0.0.11',
            'pairing_code': 'WIFI1',
            'firmware': '1.0',
            'ssid': 'NEIGHBOR',
            'wifi_event': 'STA_GOT_IP',
            'rssi': -58,
            'disconnect_reason': '',
            'server_reachable': True,
        }
        res = self.client.post(url, json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        di = DeviceInstance.objects.get(ip='10.0.0.11')
        self.assertEqual(di.last_wifi_event, 'STA_GOT_IP')
        self.assertEqual(di.last_rssi, -58)
        self.assertTrue(di.server_reachable)

    @mock.patch('urllib.request.urlopen')
    def test_provision_by_owner_and_forbidden(self, mock_urlopen):
        # Mock device response
        class DummyResp:
            def __init__(self): pass
            def read(self): return b'OK'
            def getcode(self): return 200
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
        mock_urlopen.return_value = DummyResp()

        # Create device and claim it by user
        device = DeviceInstance.objects.create(ip='10.0.0.20', pairing_code='P1')
        self.client.login(username='user', password='pass')
        claim_url = reverse('api-device-instance-claim')
        res_claim = self.client.post(claim_url, json.dumps({'device_id': device.id, 'pairing_code': 'P1'}), content_type='application/json')
        self.assertEqual(res_claim.status_code, 200)

        # Owner can provision
        prov_url = reverse('api-device-instance-provision', args=[device.id])
        res = self.client.post(prov_url, json.dumps({}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')

        # Another non-owner non-admin cannot provision
        other = User.objects.create_user(username='other', password='pass')
        self.client.login(username='other', password='pass')
        res2 = self.client.post(prov_url, json.dumps({}), content_type='application/json')
        self.assertEqual(res2.status_code, 403)

    @mock.patch('urllib.request.urlopen')
    def test_full_claim_and_push_flow(self, mock_urlopen):
        """End-to-end: device posts heartbeat with pairing code, user claims it, admin pushes config."""
        # Mock device response for push
        class DummyResp:
            def __init__(self):
                pass
            def read(self):
                return b'OK'
            def getcode(self):
                return 200
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        mock_urlopen.return_value = DummyResp()

        # Device heartbeat (server should create DeviceInstance)
        hb_url = reverse('api-device-instances')
        payload = {'ip': '10.0.0.10', 'pairing_code': 'XYZ123', 'firmware': '1.0', 'ssid': 'TEST_SSID'}
        res = self.client.post(hb_url, json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        device = DeviceInstance.objects.get(ip='10.0.0.10')
        self.assertEqual(device.pairing_code, 'XYZ123')

        # User claims the device with the correct code
        self.client.login(username='user', password='pass')
        claim_url = reverse('api-device-instance-claim')
        res_claim = self.client.post(claim_url, json.dumps({'device_id': device.id, 'pairing_code': 'XYZ123'}), content_type='application/json')
        self.assertEqual(res_claim.status_code, 200)
        device.refresh_from_db()
        self.assertEqual(device.claimed_by.username, 'user')

        # Admin pushes config to the device by id
        self.client.login(username='admin', password='pass')
        push_url = reverse('api-device-instance-push-config')
        res_push = self.client.post(push_url, json.dumps({'device_id': device.id}), content_type='application/json')
        self.assertEqual(res_push.status_code, 200)
        self.assertEqual(res_push.json().get('status'), 'ok')

    @mock.patch('urllib.request.urlopen')
    def test_push_timeout_handling(self, mock_urlopen):
        # Simulate a timeout when attempting to contact the device
        import socket
        mock_urlopen.side_effect = socket.timeout()

        self.client.login(username='admin', password='pass')
        push_url = reverse('api-device-instance-push-config')
        res = self.client.post(push_url, json.dumps({'device_id': self.device.id}), content_type='application/json')
        # View should translate a low-level timeout into a 504 Gateway Timeout with an explanatory detail
        self.assertEqual(res.status_code, 504)
        self.assertIn('Timed out', res.json().get('detail', ''))

    def test_devices_page_requires_login(self):
        # Anonymous should be redirected to login
        url = reverse('core:devices')
        res = self.client.get(url)
        self.assertIn(res.status_code, (302, 301))
        # Logged in user should see page
        self.client.login(username='user', password='pass')
        res2 = self.client.get(url)
        self.assertEqual(res2.status_code, 200)
