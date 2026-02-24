"""
Dashboard models — Control Plane (IoT devices, system settings) and
Intelligence Plane (alert rules).
"""
import secrets
from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Control Plane — Module 9: IoT Device Registry & System Settings
# ---------------------------------------------------------------------------

class SystemDevice(models.Model):
    """Tracks IoT hardware (Raspberry Pi, sensors) connected to the ecosystem."""

    class DeviceType(models.TextChoices):
        RASPBERRY_PI = 'raspberry_pi', 'Raspberry Pi'
        FINGERPRINT_SENSOR = 'fingerprint_sensor', 'Fingerprint Sensor'
        RFID_READER = 'rfid_reader', 'RFID Reader'
        CAMERA = 'camera', 'Camera (Face Recognition)'

    class Status(models.TextChoices):
        ONLINE = 'online', 'Online'
        OFFLINE = 'offline', 'Offline'
        DEGRADED = 'degraded', 'Degraded'

    name = models.CharField(max_length=120)
    device_type = models.CharField(max_length=30, choices=DeviceType.choices)
    serial_number = models.CharField(max_length=100, unique=True)
    api_key = models.CharField(
        max_length=64, unique=True, blank=True,
        help_text='Secret for device API auth. Generated automatically if blank.',
    )
    location = models.ForeignKey(
        'attendance.Location', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='devices',
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OFFLINE,
    )
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['device_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_device_type_display()}) — {self.get_status_display()}"

    @property
    def is_online(self):
        return self.status == self.Status.ONLINE

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_hex(32)
        super().save(*args, **kwargs)


class SystemSetting(models.Model):
    """
    Singleton-style global configuration.
    Controls which authentication methods are enabled system-wide (FR-3).
    """
    face_recognition_enabled = models.BooleanField(
        default=False, help_text='Enable facial recognition globally',
    )
    fingerprint_enabled = models.BooleanField(
        default=False, help_text='Enable fingerprint authentication globally',
    )
    rfid_enabled = models.BooleanField(
        default=True, help_text='Enable RFID authentication globally',
    )
    session_timeout_minutes = models.PositiveIntegerField(
        default=10, help_text='Auto-logout after N minutes of inactivity (SEC-4)',
    )
    max_failed_attempts = models.PositiveIntegerField(
        default=3, help_text='Lock account after N consecutive failures',
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return 'System Settings'

    def save(self, *args, **kwargs):
        """Enforce singleton — always overwrite pk=1."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Return the singleton instance, creating if absent."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ---------------------------------------------------------------------------
# Intelligence Plane — Module 5 & 8: Automated Alert Configuration
# ---------------------------------------------------------------------------

class AlertRule(models.Model):
    """
    Admin-defined threshold rule. When attendance at a location falls below
    the threshold percentage over the chosen time window, a dashboard
    notification is generated (FR-9, FR-10).
    """

    class TimeWindow(models.TextChoices):
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    name = models.CharField(max_length=150)
    location = models.ForeignKey(
        'attendance.Location', on_delete=models.CASCADE,
        related_name='alert_rules', null=True, blank=True,
        help_text='Required for location-based rules. Leave blank when using a specific course.',
    )
    course = models.ForeignKey(
        'attendance.Course', on_delete=models.CASCADE,
        null=True, blank=True, related_name='alert_rules',
        help_text='Optional: when set, alert is based on this class/course attendance % instead of location.',
    )
    threshold_pct = models.PositiveIntegerField(
        help_text='Alert when attendance % falls below this value (0-100)',
    )
    time_window = models.CharField(
        max_length=10, choices=TimeWindow.choices, default=TimeWindow.DAILY,
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='alert_rules',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_triggered = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'time_window']),
        ]

    def __str__(self):
        scope = self.course.code if self.course else (self.location.name if self.location else '?')
        return f"{self.name} — {scope} < {self.threshold_pct}% ({self.get_time_window_display()})"
