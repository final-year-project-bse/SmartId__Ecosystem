"""
Tests for attendance app: web attendance, session management, student/teacher/parent portals, course mgmt.
"""
from django.test import TestCase, Client
from django.urls import reverse
from users.models import User, ParentStudentLink
from .models import Location, AttendanceSession, AttendanceRecord, Course, CourseEnrollment, LeaveRequest


class AttendancePageTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='stu@test.edu', password='pass',
            institutional_id='STU001', role=User.Role.STUDENT,
            first_name='Stu', last_name='Dent',
        )
        self.location = Location.objects.create(name='Room 101', code='R101')
        self.client.login(username='stu@test.edu', password='pass')

    def test_attendance_page_loads(self):
        resp = self.client.get(reverse('attendance:attendance_page'))
        self.assertEqual(resp.status_code, 200)

    def test_mark_attendance(self):
        resp = self.client.post(reverse('attendance:attendance_page'), {
            'location_id': self.location.pk,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AttendanceRecord.objects.filter(user=self.user).exists())

    def test_duplicate_attendance(self):
        self.client.post(reverse('attendance:attendance_page'), {'location_id': self.location.pk})
        self.client.post(reverse('attendance:attendance_page'), {'location_id': self.location.pk})
        self.assertEqual(AttendanceRecord.objects.filter(user=self.user).count(), 1)


class SessionManagementTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prof = User.objects.create_user(
            email='prof@test.edu', password='pass',
            institutional_id='PRF001', role=User.Role.PROFESSOR,
            first_name='Prof', last_name='One',
        )
        self.location = Location.objects.create(name='Lab A', code='LABA')
        self.client.login(username='prof@test.edu', password='pass')

    def test_sessions_page_loads(self):
        resp = self.client.get(reverse('attendance:manage_sessions'))
        self.assertEqual(resp.status_code, 200)

    def test_start_session(self):
        resp = self.client.post(reverse('attendance:start_session'), {
            'location_id': self.location.pk,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AttendanceSession.objects.filter(location=self.location, ended_at__isnull=True).exists())

    def test_end_session(self):
        session = AttendanceSession.objects.create(location=self.location, created_by=self.prof)
        resp = self.client.post(reverse('attendance:end_session', args=[session.pk]))
        self.assertEqual(resp.status_code, 302)
        session.refresh_from_db()
        self.assertIsNotNone(session.ended_at)

    def test_student_cannot_manage_sessions(self):
        stu = User.objects.create_user(
            email='stu2@test.edu', password='pass',
            institutional_id='STU002', role=User.Role.STUDENT,
            first_name='Stu', last_name='Two',
        )
        self.client.login(username='stu2@test.edu', password='pass')
        resp = self.client.get(reverse('attendance:manage_sessions'))
        self.assertEqual(resp.status_code, 302)


class StudentPortalTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            email='stu@test.com', password='Test@1234',
            institutional_id='STU-001', role=User.Role.STUDENT,
            first_name='Alice', last_name='Student',
        )
        self.prof = User.objects.create_user(
            email='prof@test.com', password='Test@1234',
            institutional_id='PROF-001', role=User.Role.PROFESSOR,
            first_name='Bob', last_name='Professor',
        )
        self.loc = Location.objects.create(name='Hall A', code='HA')
        self.course = Course.objects.create(
            name='CS101', code='CS101', professor=self.prof, location=self.loc,
        )
        CourseEnrollment.objects.create(student=self.student, course=self.course)
        self.client.login(username='stu@test.com', password='Test@1234')
    
    def test_student_history_loads(self):
        resp = self.client.get(reverse('attendance:student_history'))
        self.assertEqual(resp.status_code, 200)
    
    def test_student_stats_loads(self):
        resp = self.client.get(reverse('attendance:student_stats'))
        self.assertEqual(resp.status_code, 200)
    
    def test_student_timetable_loads(self):
        resp = self.client.get(reverse('attendance:student_timetable'))
        self.assertEqual(resp.status_code, 200)
    
    def test_student_leave_request_loads(self):
        resp = self.client.get(reverse('attendance:student_leaves'))
        self.assertEqual(resp.status_code, 200)
    
    def test_student_can_submit_leave(self):
        resp = self.client.post(reverse('attendance:student_leaves'), {
            'course_id': self.course.pk,
            'date': '2026-03-01',
            'reason': 'Medical',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(LeaveRequest.objects.filter(student=self.student).exists())


class TeacherPortalTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.prof = User.objects.create_user(
            email='prof@test.com', password='Test@1234',
            institutional_id='PROF-001', role=User.Role.PROFESSOR,
            first_name='Bob', last_name='Professor',
        )
        self.student = User.objects.create_user(
            email='stu@test.com', password='Test@1234',
            institutional_id='STU-001', role=User.Role.STUDENT,
        )
        self.loc = Location.objects.create(name='Hall A', code='HA')
        self.course = Course.objects.create(
            name='CS101', code='CS101', professor=self.prof, location=self.loc,
        )
        CourseEnrollment.objects.create(student=self.student, course=self.course)
        self.client.login(username='prof@test.com', password='Test@1234')
    
    def test_teacher_dashboard_loads(self):
        resp = self.client.get(reverse('attendance:teacher_dashboard'))
        self.assertEqual(resp.status_code, 200)
    
    def test_teacher_schedule_loads(self):
        resp = self.client.get(reverse('attendance:teacher_schedule'))
        self.assertEqual(resp.status_code, 200)
    
    def test_teacher_analytics_loads(self):
        resp = self.client.get(reverse('attendance:teacher_analytics'))
        self.assertEqual(resp.status_code, 200)
    
    def test_teacher_class_attendance_loads(self):
        resp = self.client.get(reverse('attendance:teacher_class_attendance', args=[self.course.pk]))
        self.assertEqual(resp.status_code, 200)
    
    def test_teacher_roster_loads(self):
        resp = self.client.get(reverse('attendance:teacher_roster', args=[self.course.pk]))
        self.assertEqual(resp.status_code, 200)
    
    def test_teacher_leave_review_loads(self):
        resp = self.client.get(reverse('attendance:teacher_leaves'))
        self.assertEqual(resp.status_code, 200)


class ParentPortalTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.parent = User.objects.create_user(
            email='parent@test.com', password='Test@1234',
            institutional_id='PAR-001', role=User.Role.PARENT,
            first_name='Carol', last_name='Parent',
        )
        self.student = User.objects.create_user(
            email='stu@test.com', password='Test@1234',
            institutional_id='STU-001', role=User.Role.STUDENT,
            first_name='Alice', last_name='Student',
        )
        ParentStudentLink.objects.create(parent=self.parent, student=self.student)
        self.prof = User.objects.create_user(
            email='prof@test.com', password='Test@1234',
            institutional_id='PROF-001', role=User.Role.PROFESSOR,
        )
        self.loc = Location.objects.create(name='Hall A', code='HA')
        self.course = Course.objects.create(
            name='CS101', code='CS101', professor=self.prof, location=self.loc,
        )
        CourseEnrollment.objects.create(student=self.student, course=self.course)
        self.client.login(username='parent@test.com', password='Test@1234')
    
    def test_parent_dashboard_loads(self):
        resp = self.client.get(reverse('attendance:parent_dashboard'))
        self.assertEqual(resp.status_code, 200)
    
    def test_parent_student_attendance_loads(self):
        resp = self.client.get(reverse('attendance:parent_student_attendance', args=[self.student.pk]))
        self.assertEqual(resp.status_code, 200)
    
    def test_parent_student_stats_loads(self):
        resp = self.client.get(reverse('attendance:parent_student_stats', args=[self.student.pk]))
        self.assertEqual(resp.status_code, 200)
    
    def test_parent_student_timetable_loads(self):
        resp = self.client.get(reverse('attendance:parent_student_timetable', args=[self.student.pk]))
        self.assertEqual(resp.status_code, 200)
    
    def test_parent_student_leaves_loads(self):
        resp = self.client.get(reverse('attendance:parent_student_leaves', args=[self.student.pk]))
        self.assertEqual(resp.status_code, 200)
    
    def test_parent_cannot_access_unlinked_student(self):
        other_stu = User.objects.create_user(
            email='other@test.com', password='Test@1234',
            institutional_id='STU-002', role=User.Role.STUDENT,
        )
        resp = self.client.get(reverse('attendance:parent_student_stats', args=[other_stu.pk]))
        self.assertEqual(resp.status_code, 404)


class CourseManagementTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='Test@1234',
            institutional_id='ADM-001', role=User.Role.ADMIN,
        )
        self.prof = User.objects.create_user(
            email='prof@test.com', password='Test@1234',
            institutional_id='PROF-001', role=User.Role.PROFESSOR,
        )
        self.student = User.objects.create_user(
            email='stu@test.com', password='Test@1234',
            institutional_id='STU-001', role=User.Role.STUDENT,
        )
        self.loc = Location.objects.create(name='Hall A', code='HA')
        self.client.login(username='admin@test.com', password='Test@1234')
    
    def test_manage_courses_loads(self):
        resp = self.client.get(reverse('attendance:manage_courses'))
        self.assertEqual(resp.status_code, 200)
    
    def test_admin_can_create_course(self):
        resp = self.client.post(reverse('attendance:manage_courses'), {
            'name': 'Test Course',
            'code': 'TC101',
            'professor_id': self.prof.pk,
            'location_id': self.loc.pk,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Course.objects.filter(code='TC101').exists())
    
    def test_manage_course_enrollment_loads(self):
        course = Course.objects.create(
            name='CS101', code='CS101', professor=self.prof, location=self.loc,
        )
        resp = self.client.get(reverse('attendance:manage_course_enrollment', args=[course.pk]))
        self.assertEqual(resp.status_code, 200)
    
    def test_admin_can_enroll_student(self):
        course = Course.objects.create(
            name='CS101', code='CS101', professor=self.prof, location=self.loc,
        )
        resp = self.client.post(reverse('attendance:manage_course_enrollment', args=[course.pk]), {
            'action': 'enroll',
            'student_id': self.student.pk,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(CourseEnrollment.objects.filter(student=self.student, course=course).exists())
