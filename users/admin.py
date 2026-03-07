from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, ConsentRecord, UserAuthMethod, RFIDCredential, BiometricEmbedding, ParentStudentLink


def _is_admin_account(user):
    """True if this user is an administrator and must stay active."""
    return (
        getattr(user, 'role', None) == User.Role.ADMIN
        or getattr(user, 'is_staff', False)
        or getattr(user, 'is_superuser', False)
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'institutional_id', 'role', 'first_name', 'last_name', 'is_active', 'is_staff')
    list_editable = ('role', 'is_active')  # is_active cannot be turned off for admins (enforced in save_model)
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email', 'institutional_id', 'first_name', 'last_name')
    ordering = ('email',)
    fieldsets = BaseUserAdmin.fieldsets + (
        (None, {'fields': ('institutional_id', 'role', 'phone', 'profile_picture')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {'fields': ('email', 'institutional_id', 'role')}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Administrator accounts must always stay active
        if _is_admin_account(obj) and not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=['is_active'])


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
