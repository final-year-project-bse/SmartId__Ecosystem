"""
Tests for dashboard app: role-based access, user CRUD, reports, analytics,
system health, privacy compliance, alert rules, and performance middleware.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from users.models import User, ConsentRecord
from attendance.models import Location, AttendanceSession, AttendanceRecord
from dashboard.models import SystemDevice, SystemSetting, AlertRule


# ===========================================================================
# Existing tests — preserved
# ===========================================================================

class DashboardAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='adm@test.edu', password='adminpass',
            institutional_id='ADM001', role=User.Role.ADMIN,
            first_name='Admin', last_name='User',
        )
        self.student = User.objects.create_user(
            email='stu@test.edu', password='stupass',
            institutional_id='STU001', role=User.Role.STUDENT,
            first_name='Student', last_name='User',
        )
        self.prof = User.objects.create_user(
            email='prof@test.edu', password='profpass',
            institutional_id='PRF001', role=User.Role.PROFESSOR,
            first_name='Prof', last_name='User',
        )

    def test_student_home(self):
        self.client.login(username='stu@test.edu', password='stupass')
        resp = self.client.get(reverse('dashboard:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'My Dashboard')

    def test_admin_sees_dashboard(self):
        self.client.login(username='adm@test.edu', password='adminpass')
        resp = self.client.get(reverse('dashboard:home'))
        self.assertEqual(resp.status_code, 200)

    def test_analytics_admin_only(self):
        self.client.login(username='stu@test.edu', password='stupass')
        resp = self.client.get(reverse('dashboard:analytics'))
        self.assertEqual(resp.status_code, 302)  # redirected

        self.client.login(username='adm@test.edu', password='adminpass')
        resp = self.client.get(reverse('dashboard:analytics'))
        self.assertEqual(resp.status_code, 200)

    def test_manage_users_admin_only(self):
        self.client.login(username='prof@test.edu', password='profpass')
        resp = self.client.get(reverse('dashboard:manage_users'))
        self.assertEqual(resp.status_code, 302)

        self.client.login(username='adm@test.edu', password='adminpass')
        resp = self.client.get(reverse('dashboard:manage_users'))
        self.assertEqual(resp.status_code, 200)

    def test_reports_staff_access(self):
        self.client.login(username='prof@test.edu', password='profpass')
        resp = self.client.get(reverse('dashboard:reports'))
        self.assertEqual(resp.status_code, 200)

        self.client.login(username='stu@test.edu', password='stupass')
        resp = self.client.get(reverse('dashboard:reports'))
        self.assertEqual(resp.status_code, 302)


class UserCRUDTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='adm@test.edu', password='adminpass',
            institutional_id='ADM002', role=User.Role.ADMIN,
            first_name='Admin', last_name='CRUD',
        )
        self.client.login(username='adm@test.edu', password='adminpass')

    def test_create_user_page(self):
        resp = self.client.get(reverse('dashboard:create_user'))
        self.assertEqual(resp.status_code, 200)

    def test_enroll_user_with_consent_rfid(self):
        """Admin enrolls a user with RFID method — redirects to RFID registration."""
        resp = self.client.post(reverse('dashboard:create_user'), {
            'email': 'new@test.edu',
            'institutional_id': 'NEW001',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'student',
            'phone': '',
            'password1': 'securepass123',
            'password2': 'securepass123',
            'auth_method': 'rfid',
            'consent_rfid': True,
            'data_retention': True,
        })
        user = User.objects.get(email='new@test.edu')
        # Should redirect to RFID enrollment
        self.assertEqual(resp.status_code, 302)
        self.assertIn('enroll-rfid', resp.url)
        # Verify consent record was created
        self.assertTrue(hasattr(user, 'consent'))
        self.assertTrue(user.consent.rfid_consent)
        self.assertTrue(user.consent.data_retention_ack)
        # Verify auth method was set
        self.assertTrue(hasattr(user, 'auth_method_preference'))
        self.assertEqual(user.auth_method_preference.method, 'rfid')

    def test_enroll_user_with_consent_face(self):
        """Admin enrolls a user with face auth — no RFID redirect."""
        resp = self.client.post(reverse('dashboard:create_user'), {
            'email': 'face@test.edu',
            'institutional_id': 'FACE001',
            'first_name': 'Face',
            'last_name': 'User',
            'role': 'student',
            'phone': '',
            'password1': 'securepass123',
            'password2': 'securepass123',
            'auth_method': 'face',
            'consent_biometric': True,
            'data_retention': True,
        })
        self.assertEqual(resp.status_code, 302)
        # Should redirect to manage_users (not RFID)
        self.assertIn('manage-users', resp.url)
        user = User.objects.get(email='face@test.edu')
        self.assertTrue(user.consent.biometric_consent)
        self.assertEqual(user.auth_method_preference.method, 'face')

    def test_enroll_missing_consent_rejected(self):
        """RFID enrollment without RFID consent should be rejected."""
        resp = self.client.post(reverse('dashboard:create_user'), {
            'email': 'bad@test.edu',
            'institutional_id': 'BAD001',
            'first_name': 'Bad',
            'last_name': 'User',
            'role': 'student',
            'phone': '',
            'password1': 'securepass123',
            'password2': 'securepass123',
            'auth_method': 'rfid',
            # Missing consent_rfid
            'data_retention': True,
        })
        # Should stay on the form page (not redirect)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email='bad@test.edu').exists())

    def test_rfid_card_registration(self):
        """Admin can register an RFID card after user enrollment."""
        # First create a user
        user = User.objects.create_user(
            email='rfid@test.edu', password='pass',
            institutional_id='RFID001', role=User.Role.STUDENT,
            first_name='RFID', last_name='User',
        )
        resp = self.client.post(
            reverse('dashboard:enroll_rfid', args=[user.pk]),
            {'rfid_tag': 'ABCDEF123456'},
        )
        self.assertEqual(resp.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(hasattr(user, 'rfid_credential'))
        self.assertTrue(user.rfid_credential.check_tag('ABCDEF123456'))

    def test_rfid_enrollment_skip_if_exists(self):
        """If user already has RFID, redirect to manage_users."""
        from users.models import RFIDCredential
        user = User.objects.create_user(
            email='has_rfid@test.edu', password='pass',
            institutional_id='HAS001', role=User.Role.STUDENT,
            first_name='Has', last_name='RFID',
        )
        cred = RFIDCredential.objects.create(user=user, encrypted_tag='dummy')
        resp = self.client.get(reverse('dashboard:enroll_rfid', args=[user.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_edit_user(self):
        target = User.objects.create_user(
            email='edit@test.edu', password='pass',
            institutional_id='EDT001', role=User.Role.STUDENT,
            first_name='Edit', last_name='Me',
        )
        resp = self.client.post(reverse('dashboard:edit_user', args=[target.pk]), {
            'email': 'edit@test.edu',
            'institutional_id': 'EDT001',
            'first_name': 'Edited',
            'last_name': 'Name',
            'role': 'student',
            'phone': '',
            'is_active': True,
        })
        self.assertEqual(resp.status_code, 302)
        target.refresh_from_db()
        self.assertEqual(target.first_name, 'Edited')

    def test_toggle_active(self):
        target = User.objects.create_user(
            email='tog@test.edu', password='pass',
            institutional_id='TOG001', role=User.Role.STUDENT,
            first_name='Tog', last_name='Gle',
        )
        resp = self.client.post(reverse('dashboard:toggle_user_active', args=[target.pk]))
        self.assertEqual(resp.status_code, 302)
        target.refresh_from_db()
        self.assertFalse(target.is_active)


# ===========================================================================
# CONTROL PLANE — System Health Tests
# ===========================================================================

class SystemHealthTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='adm@health.edu', password='adminpass',
            institutional_id='ADM003', role=User.Role.ADMIN,
            first_name='Admin', last_name='Health',
        )
        self.student = User.objects.create_user(
            email='stu@health.edu', password='stupass',
            institutional_id='STU003', role=User.Role.STUDENT,
            first_name='Student', last_name='Health',
        )

    def test_admin_access_system_health(self):
        self.client.login(username='adm@health.edu', password='adminpass')
        resp = self.client.get(reverse('dashboard:system_health'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'System Health')

    def test_student_denied_system_health(self):
        self.client.login(username='stu@health.edu', password='stupass')
        resp = self.client.get(reverse('dashboard:system_health'))
        self.assertEqual(resp.status_code, 302)

    def test_system_setting_singleton(self):
        s1 = SystemSetting.load()
        s1.rfid_enabled = False
        s1.save()
        s2 = SystemSetting.load()
        self.assertEqual(s1.pk, s2.pk)
        self.assertFalse(s2.rfid_enabled)

    def test_toggle_auth_method(self):
        self.client.login(username='adm@health.edu', password='adminpass')
        # Ensure default
        s = SystemSetting.load()
        self.assertTrue(s.rfid_enabled)
        # Toggle off
        resp = self.client.post(reverse('dashboard:toggle_auth_method'), {'method': 'rfid'})
        self.assertEqual(resp.status_code, 302)
        s = SystemSetting.load()
        self.assertFalse(s.rfid_enabled)
        # Toggle back on
        resp = self.client.post(reverse('dashboard:toggle_auth_method'), {'method': 'rfid'})
        s = SystemSetting.load()
        self.assertTrue(s.rfid_enabled)

    def test_register_device(self):
        self.client.login(username='adm@health.edu', password='adminpass')
        resp = self.client.post(reverse('dashboard:register_device'), {
            'name': 'Test Pi',
            'device_type': 'raspberry_pi',
            'serial_number': 'SN-001-TEST',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(SystemDevice.objects.filter(serial_number='SN-001-TEST').exists())

    def test_register_duplicate_serial_blocked(self):
        self.client.login(username='adm@health.edu', password='adminpass')
        SystemDevice.objects.create(
            name='Existing', device_type='rfid_reader', serial_number='DUP-001',
        )
        resp = self.client.post(reverse('dashboard:register_device'), {
            'name': 'Duplicate', 'device_type': 'rfid_reader', 'serial_number': 'DUP-001',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(SystemDevice.objects.filter(serial_number='DUP-001').count(), 1)


# ===========================================================================
# OVERSIGHT PLANE — Privacy Compliance Tests
# ===========================================================================

class PrivacyComplianceTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='adm@priv.edu', password='adminpass',
            institutional_id='ADM004', role=User.Role.ADMIN,
            first_name='Admin', last_name='Privacy',
        )
        self.stu_with_consent = User.objects.create_user(
            email='consent@priv.edu', password='pass',
            institutional_id='CON001', role=User.Role.STUDENT,
            first_name='Consent', last_name='User',
        )
        ConsentRecord.objects.create(
            user=self.stu_with_consent,
            biometric_consent=True, rfid_consent=True, data_retention_ack=True,
        )
        self.stu_no_consent = User.objects.create_user(
            email='noconsent@priv.edu', password='pass',
            institutional_id='NOC001', role=User.Role.STUDENT,
            first_name='NoConsent', last_name='User',
        )

    def test_admin_access_privacy_compliance(self):
        self.client.login(username='adm@priv.edu', password='adminpass')
        resp = self.client.get(reverse('dashboard:privacy_compliance'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Privacy Compliance')

    def test_compliance_counts(self):
        self.client.login(username='adm@priv.edu', password='adminpass')
        resp = self.client.get(reverse('dashboard:privacy_compliance'))
        # Admin + 2 students = 3 total; 1 consented
        self.assertEqual(resp.context['total_users'], 3)
        self.assertEqual(resp.context['consented_count'], 1)
        self.assertEqual(resp.context['missing_count'], 2)

    def test_flagged_users_visible(self):
        self.client.login(username='adm@priv.edu', password='adminpass')
        resp = self.client.get(reverse('dashboard:privacy_compliance'))
        self.assertContains(resp, 'Missing')
        self.assertContains(resp, 'Signed')

    def test_student_denied_privacy_compliance(self):
        self.client.login(username='consent@priv.edu', password='pass')
        resp = self.client.get(reverse('dashboard:privacy_compliance'))
        self.assertEqual(resp.status_code, 302)


# ===========================================================================
# INTELLIGENCE PLANE — Alert Rule Tests
# ===========================================================================

class AlertRuleTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='adm@alert.edu', password='adminpass',
            institutional_id='ADM005', role=User.Role.ADMIN,
            first_name='Admin', last_name='Alerts',
        )
        self.location = Location.objects.create(name='Room 101', code='R101')
        self.client.login(username='adm@alert.edu', password='adminpass')

    def test_alert_rules_page(self):
        resp = self.client.get(reverse('dashboard:alert_rules'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Automated Alert Rules')

    def test_create_alert_rule(self):
        resp = self.client.post(reverse('dashboard:alert_rules'), {
            'name': 'Low Attendance R101',
            'location_id': self.location.pk,
            'threshold_pct': '75',
            'time_window': 'daily',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AlertRule.objects.filter(name='Low Attendance R101').exists())
        rule = AlertRule.objects.get(name='Low Attendance R101')
        self.assertEqual(rule.threshold_pct, 75)
        self.assertEqual(rule.location, self.location)
        self.assertTrue(rule.is_active)

    def test_toggle_alert_rule(self):
        rule = AlertRule.objects.create(
            name='Test Toggle', location=self.location,
            threshold_pct=50, created_by=self.admin,
        )
        self.assertTrue(rule.is_active)
        resp = self.client.post(reverse('dashboard:toggle_alert_rule', args=[rule.pk]))
        self.assertEqual(resp.status_code, 302)
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)

    def test_delete_alert_rule(self):
        rule = AlertRule.objects.create(
            name='Delete Me', location=self.location,
            threshold_pct=50, created_by=self.admin,
        )
        resp = self.client.post(reverse('dashboard:delete_alert_rule', args=[rule.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(AlertRule.objects.filter(pk=rule.pk).exists())

    def test_check_alert_rules_triggers(self):
        """With zero attendance, a rule with threshold>0 should trigger."""
        User.objects.create_user(
            email='stu@alert.edu', password='pass',
            institutional_id='STU005', role=User.Role.STUDENT,
            first_name='Stu', last_name='Alert',
        )
        AlertRule.objects.create(
            name='Trigger Test', location=self.location,
            threshold_pct=50, time_window='daily', created_by=self.admin,
        )
        resp = self.client.post(reverse('dashboard:check_alert_rules'))
        self.assertEqual(resp.status_code, 302)
        rule = AlertRule.objects.get(name='Trigger Test')
        self.assertIsNotNone(rule.last_triggered)

    def test_invalid_rule_rejected(self):
        resp = self.client.post(reverse('dashboard:alert_rules'), {
            'name': '',
            'location_id': self.location.pk,
            'threshold_pct': '0',
            'time_window': 'daily',
        })
        self.assertEqual(resp.status_code, 200)  # stays on form page
        self.assertEqual(AlertRule.objects.count(), 0)


# ===========================================================================
# Performance Middleware Test
# ===========================================================================

class PerformanceMiddlewareTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='adm@perf.edu', password='adminpass',
            institutional_id='ADM006', role=User.Role.ADMIN,
            first_name='Admin', last_name='Perf',
        )
        self.client.login(username='adm@perf.edu', password='adminpass')

    def test_response_has_timing_header(self):
        resp = self.client.get(reverse('dashboard:home'))
        self.assertIn('X-Request-Time-Ms', resp)
        elapsed = float(resp['X-Request-Time-Ms'])
        self.assertGreaterEqual(elapsed, 0)
        # Should complete well under 3 s with test DB
        self.assertLess(elapsed, 3000)


# ===========================================================================
# RBAC Audit — confirm all new admin routes are protected
# ===========================================================================

class RBACNewRoutesTest(TestCase):
    """Verify that students/professors cannot access admin-only new routes."""
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            email='stu@rbac.edu', password='stupass',
            institutional_id='STU_RBAC', role=User.Role.STUDENT,
            first_name='Student', last_name='RBAC',
        )
        self.prof = User.objects.create_user(
            email='prof@rbac.edu', password='profpass',
            institutional_id='PRF_RBAC', role=User.Role.PROFESSOR,
            first_name='Prof', last_name='RBAC',
        )

    def _assert_denied(self, url_name, **kwargs):
        for cred in [('stu@rbac.edu', 'stupass'), ('prof@rbac.edu', 'profpass')]:
            self.client.login(username=cred[0], password=cred[1])
            resp = self.client.get(reverse(url_name, **kwargs))
            self.assertEqual(resp.status_code, 302,
                             f'{cred[0]} should be denied access to {url_name}')

    def test_system_health_denied(self):
        self._assert_denied('dashboard:system_health')

    def test_privacy_compliance_denied(self):
        self._assert_denied('dashboard:privacy_compliance')

    def test_alert_rules_denied(self):
        self._assert_denied('dashboard:alert_rules')
