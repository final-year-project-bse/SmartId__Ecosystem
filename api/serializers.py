"""
REST API Serializers for SmartID Ecosystem.
"""
from rest_framework import serializers
from users.models import User
from attendance.models import (
    Location, AttendanceSession, AttendanceRecord, Course, CourseEnrollment,
)


class UserSerializer(serializers.ModelSerializer):
    """Basic user info (no sensitive fields)."""
    class Meta:
        model = User
        fields = ['id', 'email', 'institutional_id', 'first_name', 'last_name', 'role', 'is_active']
        read_only_fields = ['id', 'email', 'institutional_id', 'role']


class LocationSerializer(serializers.ModelSerializer):
    """Location for attendance marking."""
    class Meta:
        model = Location
        fields = ['id', 'name', 'code', 'location_type']
        read_only_fields = ['id']


class CourseSerializer(serializers.ModelSerializer):
    """Course details."""
    professor_name = serializers.CharField(source='professor.get_full_name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = Course
        fields = [
            'id', 'name', 'code', 'professor', 'professor_name',
            'location', 'location_name', 'day_of_week', 'start_time', 'end_time',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class AttendanceSessionSerializer(serializers.ModelSerializer):
    """Attendance session for a location."""
    location_name = serializers.CharField(source='location.name', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True, allow_null=True)
    record_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = AttendanceSession
        fields = [
            'id', 'location', 'location_name', 'course', 'course_code',
            'started_at', 'ended_at', 'created_by', 'record_count',
        ]
        read_only_fields = ['id', 'started_at', 'created_by']


class AttendanceRecordSerializer(serializers.ModelSerializer):
    """Single attendance record."""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'user', 'user_name', 'session', 'location', 'location_name',
            'marked_at', 'status',
        ]
        read_only_fields = ['id', 'marked_at']


class MarkAttendanceSerializer(serializers.Serializer):
    """IoT device marks attendance for a user at a location."""
    user_id = serializers.IntegerField(required=False)
    institutional_id = serializers.CharField(required=False, max_length=50)
    location_id = serializers.IntegerField()
    auth_method = serializers.ChoiceField(
        choices=['face', 'fingerprint', 'rfid'],
        default='rfid',
    )
    
    def validate(self, data):
        if not data.get('user_id') and not data.get('institutional_id'):
            raise serializers.ValidationError('Either user_id or institutional_id is required.')
        return data


class StudentStatsSerializer(serializers.Serializer):
    """Student attendance statistics."""
    course_code = serializers.CharField()
    course_name = serializers.CharField()
    total_sessions = serializers.IntegerField()
    attended = serializers.IntegerField()
    percentage = serializers.FloatField()


# ---------------------------------------------------------------------------
# Device (Pi) API — Face + RFID attendance
# ---------------------------------------------------------------------------

class DeviceRFIDScanSerializer(serializers.Serializer):
    """Pi sends RFID scan: add user to pending queue."""
    session_id = serializers.IntegerField()
    rfid_tag = serializers.CharField(max_length=200)
    timestamp = serializers.DateTimeField(required=False)  # optional; server uses now if omitted


class DeviceFaceMatchSerializer(serializers.Serializer):
    """Pi sends face embedding; server matches to pending queue and marks attendance."""
    session_id = serializers.IntegerField()
    embedding = serializers.ListField(
        child=serializers.FloatField(),
        allow_empty=False,
        help_text='Face embedding vector (e.g. 128 floats)',
    )
    timestamp = serializers.DateTimeField(required=False)


class DeviceOfflineEventSerializer(serializers.Serializer):
    """Single event in offline batch."""
    type = serializers.ChoiceField(choices=['rfid_scan', 'face_match'])
    session_id = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
    rfid_tag = serializers.CharField(required=False, allow_blank=True, max_length=200)
    embedding = serializers.ListField(
        child=serializers.FloatField(),
        required=False,
        allow_empty=True,
    )


class DeviceOfflineBatchSerializer(serializers.Serializer):
    """Pi sends queued events when back online."""
    events = DeviceOfflineEventSerializer(many=True)


class DeviceFingerprintEnrollSerializer(serializers.Serializer):
    """Pi enrolled a user's fingerprint into sensor; report slot mapping to server."""
    user_id = serializers.IntegerField(required=False)
    institutional_id = serializers.CharField(required=False, max_length=50)
    slot_position = serializers.IntegerField(min_value=0, max_value=127)

    def validate(self, data):
        if not data.get('user_id') and not data.get('institutional_id'):
            raise serializers.ValidationError('Either user_id or institutional_id is required.')
        return data


class DeviceFingerprintScanSerializer(serializers.Serializer):
    """Pi matched a fingerprint to a slot; server resolves user and marks attendance."""
    session_id = serializers.IntegerField()
    slot_position = serializers.IntegerField(min_value=0, max_value=127)
    confidence = serializers.IntegerField(required=False, default=0,
                                          help_text='Sensor confidence score (0-300)')
    timestamp = serializers.DateTimeField(required=False)
