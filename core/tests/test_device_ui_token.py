from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from ..models import DeviceInstance

User = get_user_model()


class DeviceUITokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('user1', 'u@example.com', 'pass')
        self.staff = User.objects.create_user('admin', 'a@example.com', 'pass')
        self.staff.is_staff = True
        self.staff.save()
        self.dev = DeviceInstance.objects.create(ip='10.0.0.5')

    def test_non_owner_cannot_get_token(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.post(reverse('api-device-instance-token'), {'device_id': self.dev.id}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_owner_can_get_token(self):
        # claim device
        self.dev.claimed_by = self.user
        self.dev.save()
        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.post(reverse('api-device-instance-token'), {'device_id': self.dev.id, 'regenerate': False}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('api_token', res.json())

    def test_staff_can_regenerate_token(self):
        client = APIClient()
        client.force_authenticate(user=self.staff)
        old = self.dev.api_token
        res = client.post(reverse('api-device-instance-token'), {'device_id': self.dev.id, 'regenerate': True}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('api_token', res.json())
        self.assertNotEqual(res.json()['api_token'], old)
