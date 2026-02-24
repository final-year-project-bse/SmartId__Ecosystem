"""
Device (Pi) API authentication.
Pi sends X-Device-Id (SystemDevice.pk) and X-Device-Key (api_key) headers.
"""
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from dashboard.models import SystemDevice


class IsDeviceAuthenticated(BasePermission):
    """
    Allow access only if request is authenticated as a registered device.
    Expects headers: X-Device-Id (int), X-Device-Key (str api_key).
    Sets request.device to the SystemDevice instance.
    """

    def has_permission(self, request: Request, view) -> bool:
        device_id = request.headers.get('X-Device-Id')
        device_key = request.headers.get('X-Device-Key')
        if not device_id or not device_key:
            return False
        try:
            device = SystemDevice.objects.get(pk=int(device_id), api_key=device_key.strip())
            request.device = device
            return True
        except (SystemDevice.DoesNotExist, ValueError, TypeError):
            return False
