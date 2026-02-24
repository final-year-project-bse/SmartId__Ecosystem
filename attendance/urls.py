from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # ── Terminal / RFID ──
    path('terminal/', views.terminal_login, name='terminal_login'),
    path('terminal/success/', views.terminal_success, name='terminal_success'),

    # ── Web attendance ──
    path('', views.attendance_page, name='attendance_page'),
    path('mark/<int:location_id>/', views.mark_attendance, name='mark_attendance'),

    # ── Session management (staff) ──
    path('sessions/', views.manage_sessions, name='manage_sessions'),
    path('sessions/start/', views.start_session, name='start_session'),
    path('sessions/<int:session_id>/end/', views.end_session, name='end_session'),

    # ── Student Portal ──
    path('my/history/', views.student_attendance_history, name='student_history'),
    path('my/stats/', views.student_attendance_stats, name='student_stats'),
    path('my/timetable/', views.student_timetable, name='student_timetable'),
    path('my/leaves/', views.student_leave_request, name='student_leaves'),

    # ── Parent Portal ──
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/<int:student_id>/attendance/', views.parent_student_attendance, name='parent_student_attendance'),
    path('parent/<int:student_id>/stats/', views.parent_student_stats, name='parent_student_stats'),
    path('parent/<int:student_id>/timetable/', views.parent_student_timetable, name='parent_student_timetable'),
    path('parent/<int:student_id>/leaves/', views.parent_student_leaves, name='parent_student_leaves'),

    # ── Teacher Portal ──
    path('teach/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teach/schedule/', views.teacher_schedule, name='teacher_schedule'),
    path('teach/analytics/', views.teacher_analytics, name='teacher_analytics'),
    path('teach/leaves/', views.teacher_leave_review, name='teacher_leaves'),
    path('teach/<int:course_id>/', views.teacher_class_attendance, name='teacher_class_attendance'),
    path('teach/<int:course_id>/roster/', views.teacher_student_roster, name='teacher_roster'),
    path('teach/<int:course_id>/export/', views.teacher_export, name='teacher_export'),
    path('teach/<int:course_id>/notify/', views.teacher_send_notification, name='teacher_notify'),

    # ── Admin: Course management ──
    path('courses/', views.manage_courses, name='manage_courses'),
    path('courses/<int:course_id>/enrollment/', views.manage_course_enrollment, name='manage_course_enrollment'),
]
