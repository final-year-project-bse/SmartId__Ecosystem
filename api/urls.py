"""
REST API URL Configuration.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from . import views
from . import device_views

app_name = 'api'

# Router for ViewSets
router = DefaultRouter()
router.register(r'locations', views.LocationViewSet, basename='location')
router.register(r'sessions', views.AttendanceSessionViewSet, basename='session')
router.register(r'records', views.AttendanceRecordViewSet, basename='record')
router.register(r'courses', views.CourseViewSet, basename='course')

urlpatterns = [
    # ── Authentication ──
    path('auth/token/', obtain_auth_token, name='token'),
    
    # ── Health Check ──
    path('health/', views.health_check, name='health'),
    
    # ── IoT Device Actions ──
    path('mark-attendance/', views.mark_attendance, name='mark_attendance'),
    
    # ── Device (Pi) Face + RFID attendance ──
    path('device/active-session/', device_views.device_active_session, name='device_active_session'),
    path('device/rfid-scan/', device_views.device_rfid_scan, name='device_rfid_scan'),
    path('device/face-match/', device_views.device_face_match, name='device_face_match'),
    path('device/offline-batch/', device_views.device_offline_batch, name='device_offline_batch'),
    
    # ── Student Stats ──
    path('student-stats/', views.student_stats, name='student_stats_self'),
    path('student-stats/<int:user_id>/', views.student_stats, name='student_stats'),
    
    # ── ViewSet routes ──
    path('', include(router.urls)),
]
