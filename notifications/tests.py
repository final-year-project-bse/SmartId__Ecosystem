"""
Tests for notifications app: list, mark read, mark all read, utility functions.
"""
from django.test import TestCase, Client
from django.urls import reverse
from users.models import User
from .models import Notification
from .utils import notify, notify_admins


class NotificationUtilTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='stu@test.edu', password='pass',
            institutional_id='STU001', role=User.Role.STUDENT,
            first_name='Stu', last_name='Dent',
        )
        self.admin = User.objects.create_user(
            email='adm@test.edu', password='pass',
            institutional_id='ADM001', role=User.Role.ADMIN,
            first_name='Admin', last_name='User',
        )

    def test_notify_creates_notification(self):
        n = notify(self.user, 'Test', 'Test message')
        self.assertEqual(n.user, self.user)
        self.assertFalse(n.read)

    def test_notify_admins(self):
        notify_admins('Admin Alert', 'Something happened')
        self.assertEqual(Notification.objects.filter(user=self.admin).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)


class NotificationViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='stu@test.edu', password='pass',
            institutional_id='STU001', role=User.Role.STUDENT,
            first_name='Stu', last_name='Dent',
        )
        self.client.login(username='stu@test.edu', password='pass')
        self.n1 = Notification.objects.create(user=self.user, title='N1', message='Msg1')
        self.n2 = Notification.objects.create(user=self.user, title='N2', message='Msg2')

    def test_list_loads(self):
        resp = self.client.get(reverse('notifications:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'N1')

    def test_mark_read(self):
        resp = self.client.post(reverse('notifications:mark_read', args=[self.n1.pk]))
        self.assertEqual(resp.status_code, 302)
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.read)

    def test_mark_all_read(self):
        resp = self.client.post(reverse('notifications:mark_all_read'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Notification.objects.filter(user=self.user, read=False).count(), 0)
