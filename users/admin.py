from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, ConsentRecord, UserAuthMethod, RFIDCredential, BiometricEmbedding, ParentStudentLink, FailedLoginAttempt


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'institutional_id', 'role', 'first_name', 'last_name', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email', 'institutional_id', 'first_name', 'last_name')
    ordering = ('email',)
    fieldsets = BaseUserAdmin.fieldsets + (
        (None, {'fields': ('institutional_id', 'role', 'phone', 'profile_picture')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {'fields': ('email', 'institutional_id', 'role')}),
    )


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'accepted_at', 'biometric_consent', 'rfid_consent', 'data_retention_ack')


@admin.register(UserAuthMethod)
class UserAuthMethodAdmin(admin.ModelAdmin):
    list_display = ('user', 'method', 'updated_at')


@admin.register(RFIDCredential)
class RFIDCredentialAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')


@admin.register(BiometricEmbedding)
class BiometricEmbeddingAdmin(admin.ModelAdmin):
    list_display = ('user', 'method', 'created_at')


@admin.register(ParentStudentLink)
class ParentStudentLinkAdmin(admin.ModelAdmin):
    list_display = ('parent', 'student', 'created_at')


@admin.register(FailedLoginAttempt)
class FailedLoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'is_admin_attempt', 'ip_address', 'created_at')
    list_filter = ('is_admin_attempt', 'created_at')
    search_fields = ('identifier',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
