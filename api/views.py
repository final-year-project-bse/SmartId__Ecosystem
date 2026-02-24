"""
REST API Views for SmartID Ecosystem.
Designed for IoT devices (Raspberry Pi) and mobile apps.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.utils import timezone

from users.models import User
from attendance.models import (
    Location, AttendanceSession, AttendanceRecord, AccessLog, Course, CourseEnrollment,
)
from .serializers import (
    UserSerializer, LocationSerializer, CourseSerializer,
    AttendanceSessionSerializer, AttendanceRecordSerializer,
    MarkAttendanceSerializer, StudentStatsSerializer,
)


# ===========================================================================
# ViewSets (CRUD endpoints)
# ===========================================================================

class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve locations."""
    queryset = Location.objects.all().order_by('name')
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]


class AttendanceSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve attendance sessions."""
    queryset = AttendanceSession.objects.select_related(
        'location', 'course', 'created_by'
    ).annotate(record_count=Count('records')).order_by('-started_at')
    serializer_class = AttendanceSessionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        # Filter by active sessions
        active = self.request.query_params.get('active')
        if active == 'true':
            qs = qs.filter(ended_at__isnull=True)
        elif active == 'false':
            qs = qs.filter(ended_at__isnull=False)
        # Filter by location
        location_id = self.request.query_params.get('location')
        if location_id:
            qs = qs.filter(location_id=location_id)
        return qs


class AttendanceRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve attendance records."""
    queryset = AttendanceRecord.objects.select_related(
        'user', 'session', 'location'
    ).order_by('-marked_at')
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        # Filter by user (for students viewing their own)
        user_id = self.request.query_params.get('user')
        if user_id:
            qs = qs.filter(user_id=user_id)
        # Filter by session
        session_id = self.request.query_params.get('session')
        if session_id:
            qs = qs.filter(session_id=session_id)
        return qs


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve courses."""
    queryset = Course.objects.filter(is_active=True).select_related(
        'professor', 'location'
    ).order_by('code')
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]


# ===========================================================================
# Custom API endpoints (IoT device actions)
# ===========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_attendance(request):
    """
    IoT device endpoint: Mark attendance for a user at a location.
    
    POST /api/mark-attendance/
    Body: {
        "user_id": 1 OR "institutional_id": "STU-001",
        "location_id": 2,
        "auth_method": "rfid"  // optional: face, fingerprint, rfid
    }
    """
    serializer = MarkAttendanceSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    location = get_object_or_404(Location, pk=data['location_id'])
    
    # Find user
    if data.get('user_id'):
        user = get_object_or_404(User, pk=data['user_id'], is_active=True)
    else:
        user = get_object_or_404(User, institutional_id=data['institutional_id'], is_active=True)
    
    # Get or create active session
    session = AttendanceSession.objects.filter(
        location=location, ended_at__isnull=True
    ).first()
    if not session:
        session = AttendanceSession.objects.create(
            location=location, created_by=request.user,
        )
    
    # Create attendance record (unique per user per session)
    record, created = AttendanceRecord.objects.get_or_create(
        user=user, session=session, defaults={'location': location}
    )
    
    # Log access
    AccessLog.objects.create(
        user=user, location=location, success=True,
        auth_method=data.get('auth_method', 'rfid'),
    )
    
    if created:
        return Response({
            'success': True,
            'message': f'Attendance marked for {user.get_full_name()}.',
            'record': AttendanceRecordSerializer(record).data,
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'success': False,
            'message': 'Attendance already recorded for this session.',
            'record': AttendanceRecordSerializer(record).data,
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_stats(request, user_id=None):
    """
    Get attendance statistics for a student.
    
    GET /api/student-stats/<user_id>/
    or
    GET /api/student-stats/  (for current user if student)
    """
    if user_id:
        user = get_object_or_404(User, pk=user_id, role=User.Role.STUDENT)
    else:
        user = request.user
        if user.role != User.Role.STUDENT:
            return Response(
                {'error': 'Only students can view their own stats without user_id.'},
                status=status.HTTP_403_FORBIDDEN,
            )
    
    enrollments = CourseEnrollment.objects.filter(
        student=user
    ).select_related('course')
    
    stats = []
    for enrollment in enrollments:
        course = enrollment.course
        total_sessions = AttendanceSession.objects.filter(
            course=course, ended_at__isnull=False
        ).count()
        attended = AttendanceRecord.objects.filter(
            user=user, session__course=course
        ).count()
        pct = round(attended / total_sessions * 100, 2) if total_sessions else 0
        stats.append({
            'course_code': course.code,
            'course_name': course.name,
            'total_sessions': total_sessions,
            'attended': attended,
            'percentage': pct,
        })
    
    serializer = StudentStatsSerializer(stats, many=True)
    return Response({
        'user': UserSerializer(user).data,
        'stats': serializer.data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_check(request):
    """
    API health check endpoint.
    
    GET /api/health/
    """
    return Response({
        'status': 'ok',
        'timestamp': timezone.now().isoformat(),
        'user': request.user.email,
    })
