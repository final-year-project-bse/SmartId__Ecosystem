"""
Device (Pi) API: RFID scan → pending queue; face match → mark attendance (on-time/late).
See docs/FACE_ATTENDANCE_REQUIREMENTS.md.
"""
import math
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.request import Request

from api.device_auth import IsDeviceAuthenticated
from api.serializers import (
    DeviceRFIDScanSerializer,
    DeviceFaceMatchSerializer,
    DeviceOfflineBatchSerializer,
    AttendanceRecordSerializer,
)
from users.models import User, RFIDCredential, BiometricEmbedding
from users.models import AuthMethod
from attendance.models import (
    AttendanceSession, AttendanceRecord, PendingRFIDScan,
    AccessLog,
)
from dashboard.models import SystemDevice
from notifications.utils import notify, notify_admins

# On-time window: attendance within this many minutes of session start = on_time
ON_TIME_WINDOW_MINUTES = 20
# Pending RFID older than this (minutes) are ignored when matching face
PENDING_TTL_MINUTES = 5
# Cosine similarity above this = match
FACE_MATCH_THRESHOLD = 0.6


def _user_from_rfid(rfid_tag: str):
    """Resolve user from RFID tag (encrypted credentials)."""
    tag = (rfid_tag or '').strip()
    if not tag:
        return None
    for cred in RFIDCredential.objects.select_related('user').filter(user__is_active=True):
        if cred.check_tag(tag):
            return cred.user
    return None


def _is_on_time(marked_at, session: AttendanceSession) -> bool:
    """True if marked_at is within ON_TIME_WINDOW_MINUTES of session.started_at."""
    if not session.started_at:
        return True
    cutoff = session.started_at + timezone.timedelta(minutes=ON_TIME_WINDOW_MINUTES)
    return marked_at <= cutoff


def _cosine_similarity(a, b):
    """Cosine similarity between two lists of floats. Returns value in [-1, 1]."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_embedding_floats(user: User):
    """Return face embedding as list of floats, or None if no face embedding."""
    try:
        emb = user.biometric_embedding
        if emb.method != AuthMethod.FACE:
            return None
        raw = emb.get_embedding()
        if isinstance(raw, bytes):
            import struct
            n = len(raw) // 4
            return list(struct.unpack(f'{n}f', raw[: n * 4]))
        return None
    except (BiometricEmbedding.DoesNotExist, Exception):
        return None


def _match_face_to_pending(embedding: list, session_id: int, device_id: int, at_time):
    """
    Find best-matching pending RFID scan for this embedding.
    Returns (pending_scan, similarity) or (None, 0).
    """
    cutoff = at_time - timezone.timedelta(minutes=PENDING_TTL_MINUTES)
    pendings = list(
        PendingRFIDScan.objects.filter(
            session_id=session_id, device_id=device_id, scanned_at__gte=cutoff
        ).select_related('user').order_by('scanned_at')
    )
    if not pendings:
        return None, 0.0
    best_pending = None
    best_score = -1.0
    for p in pendings:
        ref = _get_embedding_floats(p.user)
        if ref is None:
            continue
        if len(ref) != len(embedding):
            continue
        sim = _cosine_similarity(embedding, ref)
        if sim > best_score and sim >= FACE_MATCH_THRESHOLD:
            best_score = sim
            best_pending = p
    return best_pending, best_score


def _mark_attendance_and_remove_pending(pending: PendingRFIDScan, session, location, marked_at, device_id: int):
    """Create AttendanceRecord (on_time/late), remove pending, log access."""
    status_val = AttendanceRecord.Status.ON_TIME if _is_on_time(marked_at, session) else AttendanceRecord.Status.LATE
    record, created = AttendanceRecord.objects.get_or_create(
        user=pending.user, session=session, defaults={'location': location, 'marked_at': marked_at, 'status': status_val}
    )
    PendingRFIDScan.objects.filter(pk=pending.pk).delete()
    if not created:
        return record, False
    AccessLog.objects.create(
        user=pending.user, location=location, success=True, auth_method='face',
    )
    return record, True


def _notify_face_mismatch(session, device: SystemDevice, user_expected: User = None):
    """Notify teacher and admins when face did not match RFID."""
    loc = device.location or session.location
    location_name = (loc.name if loc else 'Unknown location')
    msg = (
        f"Face did not match expected identity at {location_name} (device: {device.name}). "
        + (f"RFID was scanned for {user_expected.get_full_name()} ({user_expected.institutional_id})." if user_expected else "")
    )
    notify_admins('Possible card misuse — face mismatch', msg, notification_type='failed_auth')
    if session.course and session.course.professor_id:
        notify(
            session.course.professor,
            'Face mismatch at attendance',
            msg,
            notification_type='failed_auth',
        )


@api_view(['GET'])
@permission_classes([IsDeviceAuthenticated])
def device_active_session(request: Request):
    """
    Pi: get active session for this device's location (for linking to teacher-started session).
    GET with X-Device-Id, X-Device-Key. Returns session_id, started_at, course_code, etc. or 404.
    """
    device: SystemDevice = request.device
    location_id = device.location_id
    if not location_id:
        return Response(
            {'error': 'Device has no location assigned.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    session = AttendanceSession.objects.filter(
        location_id=location_id, ended_at__isnull=True
    ).select_related('location', 'course').order_by('-started_at').first()
    if not session:
        return Response(
            {'error': 'No active session for this location.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    from datetime import timedelta
    on_time_until = session.started_at + timedelta(minutes=ON_TIME_WINDOW_MINUTES) if session.started_at else None
    return Response({
        'session_id': session.pk,
        'location_id': session.location_id,
        'location_name': session.location.name,
        'course_id': session.course_id,
        'course_code': session.course.code if session.course else None,
        'started_at': session.started_at.isoformat() if session.started_at else None,
        'on_time_until': on_time_until.isoformat() if on_time_until else None,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsDeviceAuthenticated])
def device_rfid_scan(request: Request):
    """
    Pi: student scanned RFID. Add user to pending queue for this session/device.
    POST body: { "session_id": int, "rfid_tag": str, "timestamp": optional ISO datetime }
    """
    serializer = DeviceRFIDScanSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    data = serializer.validated_data
    session_id = data['session_id']
    rfid_tag = data['rfid_tag']
    at_time = data.get('timestamp') or timezone.now()
    device: SystemDevice = request.device

    session = AttendanceSession.objects.filter(
        pk=session_id, ended_at__isnull=True
    ).select_related('location', 'course').first()
    if not session:
        return Response(
            {'error': 'Session not found or already ended.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    user = _user_from_rfid(rfid_tag)
    if not user:
        return Response(
            {'error': 'RFID tag not recognized.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        PendingRFIDScan.objects.create(
            user=user, session=session, device_id=device.pk, scanned_at=at_time,
        )
    return Response({
        'success': True,
        'message': f'Pending scan added for {user.institutional_id}.',
        'user_id': user.pk,
        'institutional_id': user.institutional_id,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsDeviceAuthenticated])
def device_face_match(request: Request):
    """
    Pi: face captured and embedding computed. Match to pending queue; mark attendance (on-time/late) or notify mismatch.
    POST body: { "session_id": int, "embedding": [float, ...], "timestamp": optional }
    """
    serializer = DeviceFaceMatchSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    data = serializer.validated_data
    session_id = data['session_id']
    embedding = data['embedding']
    at_time = data.get('timestamp') or timezone.now()
    device: SystemDevice = request.device

    session = AttendanceSession.objects.filter(
        pk=session_id, ended_at__isnull=True
    ).select_related('location', 'course').first()
    if not session:
        return Response(
            {'error': 'Session not found or already ended.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    location = session.location

    pending, score = _match_face_to_pending(embedding, session_id, device.pk, at_time)
    if pending is None:
        # No match: optionally notify if there are recent pendings (possible misuse)
        cutoff = at_time - timezone.timedelta(minutes=PENDING_TTL_MINUTES)
        has_recent = PendingRFIDScan.objects.filter(
            session_id=session_id, device_id=device.pk, scanned_at__gte=cutoff
        ).exists()
        if has_recent:
            _notify_face_mismatch(session, device)
        return Response({
            'success': False,
            'message': 'No matching pending RFID scan for this face.',
            'matched': False,
        }, status=status.HTTP_200_OK)

    with transaction.atomic():
        record, created = _mark_attendance_and_remove_pending(
            pending, session, location, at_time, device.pk,
        )
    status_val = record.status
    return Response({
        'success': True,
        'message': f'Attendance marked ({status_val}) for {record.user.institutional_id}.',
        'matched': True,
        'user_id': record.user_id,
        'institutional_id': record.user.institutional_id,
        'status': status_val,
        'record': AttendanceRecordSerializer(record).data,
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsDeviceAuthenticated])
def device_offline_batch(request: Request):
    """
    Pi: send queued events when back online. Process in order (rfid_scan then face_match).
    POST body: { "events": [ { "type": "rfid_scan"|"face_match", "session_id", "timestamp", "rfid_tag"?, "embedding"? }, ... ] }
    """
    serializer = DeviceOfflineBatchSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    events = serializer.validated_data['events']
    device: SystemDevice = request.device
    results = []

    for ev in events:
        ev_type = ev['type']
        session_id = ev['session_id']
        at_time = ev['timestamp']
        session = AttendanceSession.objects.filter(
            pk=session_id, ended_at__isnull=True
        ).select_related('location', 'course').first()
        if not session:
            results.append({'type': ev_type, 'session_id': session_id, 'ok': False, 'error': 'Session not found or ended'})
            continue
        if ev_type == 'rfid_scan':
            rfid_tag = ev.get('rfid_tag') or ''
            user = _user_from_rfid(rfid_tag)
            if not user:
                results.append({'type': ev_type, 'ok': False, 'error': 'RFID not recognized'})
                continue
            with transaction.atomic():
                PendingRFIDScan.objects.create(
                    user=user, session=session, device_id=device.pk, scanned_at=at_time,
                )
            results.append({'type': ev_type, 'ok': True, 'user_id': user.pk})
        elif ev_type == 'face_match':
            embedding = ev.get('embedding') or []
            if not embedding:
                results.append({'type': ev_type, 'ok': False, 'error': 'Missing embedding'})
                continue
            pending, score = _match_face_to_pending(embedding, session_id, device.pk, at_time)
            if pending is None:
                cutoff = at_time - timezone.timedelta(minutes=PENDING_TTL_MINUTES)
                has_recent = PendingRFIDScan.objects.filter(
                    session_id=session_id, device_id=device.pk, scanned_at__gte=cutoff
                ).exists()
                if has_recent:
                    _notify_face_mismatch(session, device)
                results.append({'type': ev_type, 'ok': False, 'error': 'No matching pending RFID'})
                continue
            with transaction.atomic():
                record, created = _mark_attendance_and_remove_pending(
                    pending, session, session.location, at_time, device.pk,
                )
            results.append({
                'type': ev_type, 'ok': True,
                'user_id': record.user_id, 'status': record.status,
            })

    return Response({
        'success': True,
        'processed': len(results),
        'results': results,
    }, status=status.HTTP_200_OK)
