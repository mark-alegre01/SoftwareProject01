from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
from core.views import ScanDevicesView


class TestDeviceScan(TestCase):
    def setUp(self):
        self.client = Client()

    @patch.object(ScanDevicesView, 'get_local_ip', return_value='192.168.1.100')
    @patch.object(ScanDevicesView, 'probe')
    def test_scan_returns_discovered_ips(self, mock_probe, mock_get_local_ip):
        # Simulate probe returning successful for two ips and unreachable for others
        def probe_side(ip):
            if ip.endswith('.42'):
                return {'ip': ip, 'ok': True, 'code': 200, 'body': 'ESP32 device v1.2'}
            if ip.endswith('.55'):
                return {'ip': ip, 'ok': True, 'code': 200, 'body': 'ESP32 device v1.3'}
            return {'ip': ip, 'ok': False}
        mock_probe.side_effect = probe_side

        res = self.client.get(reverse('api-device-instances-scan'))
        self.assertEqual(res.status_code, 200)
        j = res.json()
        devices = j.get('devices', [])
        ips = {d['ip'] for d in devices}
        self.assertIn('192.168.1.42', ips)
        self.assertIn('192.168.1.55', ips)

    def test_register_discovered_device(self):
        # Register an ip discovered by scan - posted to device-instances
        res = self.client.post(reverse('api-device-instances'), data={'ip': '10.0.0.42'}, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        j = res.json()
        self.assertEqual(j.get('ip'), '10.0.0.42')
