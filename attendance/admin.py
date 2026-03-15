from django.contrib import admin
from .models import (
    Location, AttendanceSession, AttendanceRecord, AccessLog,
    Course, CourseEnrollment, LeaveRequest, TimetableSlot,
)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'location_type')


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('location', 'course', 'slot', 'started_at', 'ended_at', 'created_by')


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'session', 'location', 'marked_at', 'status')
    list_filter = ('status', 'location')


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'accessed_at', 'success', 'auth_method')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'professor', 'location', 'is_active')
    list_filter = ('is_active', 'day_of_week')
    search_fields = ('code', 'name')


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at')
    list_filter = ('course',)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'date', 'status', 'reviewed_by', 'created_at')
    list_filter = ('status', 'course')
    search_fields = ('student__email', 'student__institutional_id')


@admin.register(TimetableSlot)
class TimetableSlotAdmin(admin.ModelAdmin):
    list_display = ('course', 'professor', 'location', 'day_of_week', 'start_time', 'end_time')
    list_filter = ('day_of_week', 'location')
    search_fields = ('course__code', 'course__name')
    ordering = ('day_of_week', 'start_time')
