from django.test import TestCase, Client
from django.urls import reverse


class TestPing(TestCase):
    def setUp(self):
        self.client = Client()

    def test_ping_ok(self):
        res = self.client.get(reverse('api-ping'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')
