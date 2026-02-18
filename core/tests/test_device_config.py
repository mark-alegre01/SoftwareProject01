from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from core.models import DeviceInstance


class TestDeviceConfigAPIs(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('urllib.request.urlopen')
    def test_test_api_host_success(self, mock_urlopen):
        # Mock a successful response that behaves like a context manager
        class _R:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def getcode(self):
                return 200
        mock_urlopen.return_value = _R()

        url = reverse('api-device-config-test')
        res = self.client.post(url, data={"url": "http://127.0.0.1:8001/"}, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get('status'), 'ok')

    @patch('urllib.request.urlopen', side_effect=TimeoutError)
    def test_test_api_host_timeout(self, mock_urlopen):
        url = reverse('api-device-config-test')
        res = self.client.post(url, data={"url": "http://10.0.0.1:1234/"}, content_type='application/json')
        self.assertIn(res.status_code, (502, 504))

    @patch('urllib.request.urlopen')
    def test_push_connection_reset(self, mock_urlopen):
        # simulate connection reset and ensure server returns 502/bad gateway
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError(ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host'))
        from django.urls import reverse
        res = self.client.post(reverse('api-device-config-test'), data={"url": "http://10.0.0.1/"}, content_type='application/json')
        self.assertIn(res.status_code, (502, 504))

    @patch('socket.create_connection')
    def test_tcp_probe_failure(self, mock_create_conn):
        # simulate TCP connect failing before POST attempt; exercise ProvisionDeviceView which uses push_config_to_target
        mock_create_conn.side_effect = OSError('No route to host')
        from django.urls import reverse
        from django.contrib.auth.models import User
        from core.models import DeviceInstance
        # create admin user and device
        User.objects.create_user('admin', password='x', is_staff=True)
        self.client.login(username='admin', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.1')
        res = self.client.post(reverse('api-device-instance-provision', args=[d.id]))
        self.assertEqual(res.status_code, 502)
        self.assertIn('TCP connect failed', res.json().get('detail', ''))

    @patch('socket.create_connection')
    @patch('urllib.request.urlopen')
    def test_push_connection_reset_to_device(self, mock_urlopen, mock_create_conn):
        # simulate TCP connect success and then a connection reset when attempting POST
        class _Sock:
            def close(self):
                pass
        mock_create_conn.return_value = _Sock()
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError(ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host'))
        from django.urls import reverse
        from django.contrib.auth.models import User
        from core.models import DeviceInstance
        User.objects.create_user('admin4', password='x', is_staff=True)
        self.client.login(username='admin4', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.5')
        res = self.client.post(reverse('api-device-instance-provision', args=[d.id]))
        self.assertEqual(res.status_code, 502)
        self.assertIn('Connection reset', res.json().get('detail', ''))

    @patch('core.views.push_command_to_target')
    def test_device_control_admin(self, mock_cmd):
        mock_cmd.return_value = (True, {'code':200,'body':'{"status":"ok"}'}, 200)
        User.objects.create_user('admin2', password='x', is_staff=True)
        self.client.login(username='admin2', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.5')
        res = self.client.post(reverse('api-device-instance-control'), data={"device_id": d.id, "action": "disconnect"}, content_type='application/json')
        self.assertEqual(res.status_code, 200)

    @patch('core.views.push_command_to_target')
    def test_device_control_startap(self, mock_cmd):
        """Admin can instruct device to enter AP (hotspot) mode via action 'startap'"""
        mock_cmd.return_value = (True, {'code':200,'body':'{"status":"ok"}'}, 200)
        User.objects.create_user('admin_ap', password='x', is_staff=True)
        self.client.login(username='admin_ap', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.8')
        res = self.client.post(reverse('api-device-instance-control'), data={"device_id": d.id, "action": "startap"}, content_type='application/json')
        self.assertEqual(res.status_code, 200)

    @patch('core.views.push_command_to_target')
    def test_device_control_owner(self, mock_cmd):
        mock_cmd.return_value = (True, {'code':200,'body':'{"status":"ok"}'}, 200)
        owner = User.objects.create_user('owner', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.6', claimed_by=owner)
        self.client.login(username='owner', password='x')
        res = self.client.post(reverse('api-device-instance-control'), data={"device_id": d.id, "action": "reboot"}, content_type='application/json')
        self.assertEqual(res.status_code, 200)

    @patch('core.views.push_command_to_target')
    def test_device_control_forbidden_nonowner(self, mock_cmd):
        mock_cmd.return_value = (True, {'code':200,'body':'{"status":"ok"}'}, 200)
        owner = User.objects.create_user('owner2', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.7', claimed_by=owner)
        non_owner = User.objects.create_user('other', password='x')
        self.client.login(username='other', password='x')
        res = self.client.post(reverse('api-device-instance-control'), data={"device_id": d.id, "action": "reboot"}, content_type='application/json')
        self.assertEqual(res.status_code, 403)

    @patch('core.views.push_command_to_target')
    def test_device_control_owner_startap(self, mock_cmd):
        """Owner can instruct device to enter AP (hotspot) mode via action 'startap'"""
        mock_cmd.return_value = (True, {'code':200,'body':'{"status":"ok"}'}, 200)
        owner = User.objects.create_user('owner_ap', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.9', claimed_by=owner)
        self.client.login(username='owner_ap', password='x')
        res = self.client.post(reverse('api-device-instance-control'), data={"device_id": d.id, "action": "startap"}, content_type='application/json')
        self.assertEqual(res.status_code, 200)

    def test_reboot_fallback_to_reboot_endpoint(self):
        # Simulate device returning 400 on /control but succeeding on /reboot
        import urllib.error, io
        from unittest.mock import patch

        def fake_urlopen(req, timeout=...):
            url = req.full_url
            # First call to /control -> HTTP 400 with body
            if url.endswith('/control'):
                raise urllib.error.HTTPError(url, 400, 'Bad Request', hdrs=None, fp=io.BytesIO(b'{"error":"bad payload"}'))
            # Second call to /reboot -> returns 200
            class _R:
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
                def read(self):
                    return b'{"status":"reboot-scheduled"}'
                def getcode(self):
                    return 200
            return _R()

        from django.urls import reverse
        from django.contrib.auth.models import User
        User.objects.create_user('admin5', password='x', is_staff=True)
        self.client.login(username='admin5', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.55')
        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            res = self.client.post(reverse('api-device-instance-control'), data={"device_id": d.id, "action": "reboot"}, content_type='application/json')
            self.assertEqual(res.status_code, 200)

    def test_reboot_fallback_alternative_payload(self):
        # Simulate /control returning Unknown action then accept form-encoded action=reboot
        import urllib.error, io
        from unittest.mock import patch

        call_state = {'n': 0}
        def fake_urlopen(req, timeout=...):
            call_state['n'] += 1
            url = req.full_url
            # First attempt: always return HTTP 400 Unknown action
            if call_state['n'] == 1:
                raise urllib.error.HTTPError(url, 400, 'Bad Request', hdrs=None, fp=io.BytesIO(b'{"detail":"Unknown action"}'))
            # Second or later attempt: simulate success (fallback accepted)
            class _R:
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
                def read(self):
                    return b'{"status":"rebooting"}'
                def getcode(self):
                    return 200
            return _R()

        from django.urls import reverse
        from django.contrib.auth.models import User
        User.objects.create_user('admin6', password='x', is_staff=True)
        self.client.login(username='admin6', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.66')
        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            res = self.client.post(reverse('api-device-instance-control'), data={"device_id": d.id, "action": "reboot"}, content_type='application/json')
            self.assertEqual(res.status_code, 200)

    def test_startap_fallback_on_connection_reset(self):
        # Simulate /control connection reset then fallback /startap succeeds
        import urllib.error, io
        from unittest.mock import patch

        call_state = {'n': 0}
        def fake_urlopen(req, timeout=...):
            call_state['n'] += 1
            url = getattr(req, 'full_url', '')
            # First attempt to /control -> connection reset
            if url.endswith('/control') and call_state['n'] == 1:
                raise urllib.error.URLError(ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host'))
            # Second attempt to /startap -> success
            class _R:
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
                def read(self):
                    return b'{"status":"ok"}'
                def getcode(self):
                    return 200
            return _R()

        from django.urls import reverse
        from django.contrib.auth.models import User
        User.objects.create_user('admin7', password='x', is_staff=True)
        self.client.login(username='admin7', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.70')
        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            res = self.client.post(reverse('api-device-instance-control'), data={"device_id": d.id, "action": "startap"}, content_type='application/json')
            self.assertEqual(res.status_code, 200)

    def test_provision_reboot_on_reset(self):
        # Simulate connection reset on first push, then reboot succeeds and subsequent push succeeds
        import urllib.error, io
        from unittest.mock import patch

        call_state = {'n': 0}
        def fake_urlopen(req, timeout=...):
            call_state['n'] += 1
            # First POST attempt -> connection reset
            if call_state['n'] == 1:
                raise urllib.error.URLError(ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host'))
            # Second POST after reboot -> success
            class _R:
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
                def read(self):
                    return b'{}'
                def getcode(self):
                    return 200
            return _R()

        from django.urls import reverse
        from django.contrib.auth.models import User
        User.objects.create_user('admin_reboot', password='x', is_staff=True)
        self.client.login(username='admin_reboot', password='x')
        d = DeviceInstance.objects.create(ip='10.0.0.101')
        # Patch push_command_to_target to simulate successful reboot command and ensure TCP probe passes
        class _Sock:
            def close(self):
                pass
        with patch('socket.create_connection', return_value=_Sock()), patch('urllib.request.urlopen', side_effect=fake_urlopen), patch('core.views.push_command_to_target') as mock_cmd:
            mock_cmd.return_value = (True, {'code':200,'body':'{"status":"reboot-scheduled"}'}, 200)
            res = self.client.post(reverse('api-device-instance-provision', args=[d.id]), data={"reboot_on_reset": True}, content_type='application/json')
            self.assertEqual(res.status_code, 200)

    @patch('core.views.push_config_to_target')
    def test_push_all(self, mock_push):
        mock_push.return_value = (True, {'code':200,'body':'{}'}, 200)
        User.objects.create_user('admin3', password='x', is_staff=True)
        self.client.login(username='admin3', password='x')
        DeviceInstance.objects.create(ip='10.0.0.11')
        DeviceInstance.objects.create(ip='10.0.0.12')
        res = self.client.post(reverse('api-device-config-push-all'), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        j = res.json()
        self.assertIn('results', j)