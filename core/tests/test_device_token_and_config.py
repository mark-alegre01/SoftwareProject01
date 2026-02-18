from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse

from ..models import DeviceConfig, DeviceInstance


class DeviceTokenConfigTests(TestCase):
    def test_device_gets_plain_password_with_token(self):
        # Setup
        cfg, _ = DeviceConfig.objects.get_or_create(id=1)
        cfg.set_password('supersecret')
        cfg.api_host = 'https://example.local'
        cfg.save()

        dev = DeviceInstance.objects.create(ip='192.168.0.100')
        dev.api_token = 'testtoken123'
        dev.save()

        client = APIClient()
        # No token -> should not see password
        resp = client.get(reverse('api-device-config'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('password', resp.json())

        # With device token -> should receive plaintext password
        resp = client.get(reverse('api-device-config'), HTTP_X_DEVICE_TOKEN='testtoken123')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('password'), 'supersecret')

    def test_scan_post_requires_token(self):
        dev = DeviceInstance.objects.create(ip='192.168.0.101')
        dev.api_token = 'posttoken'
        dev.save()

        client = APIClient()
        # No token -> forbidden
        resp = client.post(reverse('api-rfid-scans'), {'uid': 'ABC123'}, format='json')
        self.assertEqual(resp.status_code, 403)

        # With token -> allowed
        resp = client.post(reverse('api-rfid-scans'), {'uid': 'ABC123'}, format='json', HTTP_X_DEVICE_TOKEN='posttoken')
        self.assertEqual(resp.status_code, 201)
