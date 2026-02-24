"""
Tests for REST API endpoints.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from users.models import User, ConsentRecord, UserAuthMethod, AuthMethod
from attendance.models import Location, AttendanceSession, Course, CourseEnrollment


class APIAuthenticationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='api@test.com', password='Test@1234',
            institutional_id='API-001', role=User.Role.STUDENT,
        )
        self.token = Token.objects.create(user=self.user)
    
    def test_token_authentication(self):
        """Token auth works."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        resp = self.client.get('/api/health/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'ok')
    
    def test_unauthenticated_denied(self):
        """Unauthenticated requests are denied."""
        resp = self.client.get('/api/locations/')
        self.assertEqual(resp.status_code, 401)


class LocationAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='api@test.com', password='Test@1234',
            institutional_id='API-001', role=User.Role.STUDENT,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.loc = Location.objects.create(name='Test Hall', code='TH-01')
    
    def test_list_locations(self):
        """Can list locations."""
        resp = self.client.get('/api/locations/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['results']), 1)


class MarkAttendanceAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='Test@1234',
            institutional_id='ADM-001', role=User.Role.ADMIN,
        )
        self.student = User.objects.create_user(
            email='stu@test.com', password='Test@1234',
            institutional_id='STU-001', role=User.Role.STUDENT,
        )
        self.token = Token.objects.create(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.loc = Location.objects.create(name='Test Hall', code='TH-01')
    
    def test_mark_attendance_creates_record(self):
        """IoT device can mark attendance."""
        resp = self.client.post('/api/mark-attendance/', {
            'user_id': self.student.pk,
            'location_id': self.loc.pk,
            'auth_method': 'rfid',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['success'])
    
    def test_mark_attendance_duplicate(self):
        """Duplicate attendance returns 200 with success=false."""
        self.client.post('/api/mark-attendance/', {
            'user_id': self.student.pk,
            'location_id': self.loc.pk,
        })
        resp = self.client.post('/api/mark-attendance/', {
            'user_id': self.student.pk,
            'location_id': self.loc.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['success'])
