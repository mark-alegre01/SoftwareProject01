from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import DeviceInstance


class DeviceTokenAuthentication(BaseAuthentication):
    """Authenticate requests from ESP32 devices using X-Device-Token header or ?token=..."""

    def authenticate(self, request):
        token = request.headers.get("X-Device-Token") or request.query_params.get("token")
        if not token:
            return None
        try:
            device = DeviceInstance.objects.get(api_token=token)
        except DeviceInstance.DoesNotExist:
            raise AuthenticationFailed("Invalid device token")
        # Return the device as the "user" and None as auth (no Django User)
        return (device, None)
