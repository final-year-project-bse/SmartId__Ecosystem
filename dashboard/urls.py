from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('reports/', views.reports, name='reports'),
    path('analytics/', views.analytics, name='analytics'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('manage-users/create/', views.create_user, name='create_user'),
    path('manage-users/fetch-university-record/', views.fetch_university_record, name='fetch_university_record'),
    path('departments/', views.manage_departments, name='manage_departments'),
    path('manage-users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('manage-users/<int:user_id>/toggle/', views.toggle_user_active, name='toggle_user_active'),
    path('manage-users/<int:user_id>/reset-password/', views.reset_user_password, name='reset_user_password'),
    path('manage-users/<int:user_id>/enroll-rfid/', views.enroll_rfid, name='enroll_rfid'),
    path('manage-users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('manage-users/<int:parent_id>/parent-links/', views.manage_parent_links, name='manage_parent_links'),
    path('locations/', views.manage_locations, name='manage_locations'),
    path('locations/<int:location_id>/edit/', views.edit_location, name='edit_location'),
    path('locations/<int:location_id>/delete/', views.delete_location, name='delete_location'),
    path('timetable/', views.timetable_master, name='timetable_master'),
    path('fingerprint-slots/', views.fingerprint_slots, name='fingerprint_slots'),
    path('fingerprint-slots/<int:slot_id>/delete/', views.delete_fingerprint_slot, name='delete_fingerprint_slot'),

    # ── Control Plane — System Health (Module 9) ──
    path('system-health/', views.system_health, name='system_health'),
    path('system-health/toggle-auth/', views.toggle_auth_method, name='toggle_auth_method'),
    path('system-health/register-device/', views.register_device, name='register_device'),
    path('system-health/devices/<int:device_id>/delete/', views.delete_device, name='delete_device'),

    # ── Oversight Plane — Privacy Compliance ──
    path('privacy-compliance/', views.privacy_compliance, name='privacy_compliance'),

    # ── Intelligence Plane — Alert Configuration ──
    path('alert-rules/', views.alert_rules, name='alert_rules'),
    path('alert-rules/<int:rule_id>/toggle/', views.toggle_alert_rule, name='toggle_alert_rule'),
    path('alert-rules/<int:rule_id>/delete/', views.delete_alert_rule, name='delete_alert_rule'),
    path('alert-rules/check/', views.check_alert_rules, name='check_alert_rules'),
]
