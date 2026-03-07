"""
Tests for users app: enrollment, login, admin login, profile, decorators.
"""
from django.test import TestCase, Client
from django.urls import reverse
from .models import User


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            email='test@campus.edu', password='testpass123',
            institutional_id='STU001', role=User.Role.STUDENT,
            first_name='Test', last_name='User',
        )
        self.assertEqual(user.email, 'test@campus.edu')
        self.assertTrue(user.check_password('testpass123'))
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        su = User.objects.create_superuser(
            email='admin@campus.edu', password='admin123',
            institutional_id='ADM001',
        )
        self.assertTrue(su.is_staff)
        self.assertTrue(su.is_superuser)
        self.assertEqual(su.role, User.Role.ADMIN)


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='stu@campus.edu', password='pass1234',
            institutional_id='STU100', role=User.Role.STUDENT,
            first_name='Stu', last_name='Dent',
        )

    def test_login_page_loads(self):
        resp = self.client.get(reverse('users:login'))
        self.assertEqual(resp.status_code, 200)

    def test_login_success(self):
        resp = self.client.post(reverse('users:login'), {
            'username': 'stu@campus.edu', 'password': 'pass1234',
        })
        self.assertEqual(resp.status_code, 302)

    def test_login_failure(self):
        resp = self.client.post(reverse('users:login'), {
            'username': 'stu@campus.edu', 'password': 'wrong',
        })
        self.assertEqual(resp.status_code, 200)

    def test_admin_cannot_use_regular_login(self):
        """Admin credentials must use /login/admin/; they are rejected on /login/."""
        User.objects.create_user(
            email='adm@campus.edu', password='adminpass',
            institutional_id='ADM100', role=User.Role.ADMIN,
            first_name='Ad', last_name='Min',
        )
        resp = self.client.post(reverse('users:login'), {
            'username': 'adm@campus.edu', 'password': 'adminpass',
        })
        self.assertEqual(resp.status_code, 200)  # stays on login page, not redirect to dashboard
        self.assertContains(resp, 'admin login')


class AdminLoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='adm@campus.edu', password='adminpass',
            institutional_id='ADM100', role=User.Role.ADMIN,
            first_name='Ad', last_name='Min',
        )
        self.student = User.objects.create_user(
            email='stu2@campus.edu', password='stupass',
            institutional_id='STU200', role=User.Role.STUDENT,
            first_name='Stu', last_name='Two',
        )

    def test_admin_login_page_loads(self):
        resp = self.client.get(reverse('users:admin_login'))
        self.assertEqual(resp.status_code, 200)

    def test_admin_login_success(self):
        resp = self.client.post(reverse('users:admin_login'), {
            'username': 'adm@campus.edu', 'password': 'adminpass',
        })
        self.assertEqual(resp.status_code, 302)

    def test_non_admin_rejected(self):
        resp = self.client.post(reverse('users:admin_login'), {
            'username': 'stu2@campus.edu', 'password': 'stupass',
        })
        self.assertEqual(resp.status_code, 200)  # stays on page with error


class ProfileViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='prof@campus.edu', password='profpass',
            institutional_id='PRF001', role=User.Role.PROFESSOR,
            first_name='Pro', last_name='Fessor',
        )
        self.client.login(username='prof@campus.edu', password='profpass')

    def test_profile_loads(self):
        resp = self.client.get(reverse('users:profile'))
        self.assertEqual(resp.status_code, 200)

    def test_profile_edit(self):
        resp = self.client.post(reverse('users:profile'), {
            'first_name': 'Updated', 'last_name': 'Name', 'phone': '123456',
        })
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')


class EnrollmentIsAdminControlledTest(TestCase):
    """Enrollment is now admin-only via the dashboard (UC-1, FR-2)."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='adm@enroll.edu', password='adminpass',
            institutional_id='ADM_ENR', role=User.Role.ADMIN,
            first_name='Admin', last_name='Enroll',
        )

    def test_public_enroll_url_gone(self):
        """The old /enroll/ route should no longer exist."""
        from django.urls import resolve, Resolver404
        with self.assertRaises(Resolver404):
            resolve('/enroll/')

    def test_admin_can_reach_enroll_form(self):
        self.client.login(username='adm@enroll.edu', password='adminpass')
        resp = self.client.get(reverse('dashboard:create_user'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Digital Consent')
