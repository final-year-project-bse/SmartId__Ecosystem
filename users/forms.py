"""
Enrollment, authentication, and admin user management forms (FR-1, FR-2, UC-6).
"""
import re
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from .models import User, ConsentRecord, AuthMethod

# Registration number format: XX00-XXX-000 (e.g. FA22-BSE-069)
REGISTRATION_NUMBER_REGEX = re.compile(r'^[A-Za-z]{2}\d{2}-[A-Za-z]{3}-\d{3}$')


def validate_registration_number(value):
    """Validate and return normalized registration number (uppercase)."""
    if not value:
        return value
    raw = (value or '').strip().upper()
    if not REGISTRATION_NUMBER_REGEX.match(raw):
        raise forms.ValidationError(
            'Registration number must match format XX00-XXX-000 (e.g. FA22-BSE-069).'
        )
    return raw


# ---------------------------------------------------------------------------
# Enrollment (UC-1)
# ---------------------------------------------------------------------------

class EnrollmentForm(forms.ModelForm):
    """User registration with institutional ID and auth method (FR-1)."""
    institutional_id = forms.CharField(max_length=50, label='Institutional ID')
    auth_method = forms.ChoiceField(choices=AuthMethod.choices, label='Preferred authentication method')
    consent_biometric = forms.BooleanField(required=False, label='I consent to biometric data capture (if selected)')
    consent_rfid = forms.BooleanField(required=False, label='I consent to RFID data storage (if selected)')
    data_retention = forms.BooleanField(required=True, label='I accept the data retention and deletion policy')
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('email', 'institutional_id', 'first_name', 'last_name', 'role')

    def clean_password2(self):
        if self.cleaned_data.get('password1') != self.cleaned_data.get('password2'):
            raise forms.ValidationError('Passwords do not match.')
        return self.cleaned_data['password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user

    def clean_institutional_id(self):
        id_val = self.cleaned_data.get('institutional_id')
        id_val = validate_registration_number(id_val)
        if User.objects.filter(institutional_id=id_val).exists():
            raise forms.ValidationError('A user with this registration number already exists.')
        return id_val

    def clean(self):
        data = super().clean()
        method = data.get('auth_method')
        if method == AuthMethod.RFID and not data.get('consent_rfid'):
            raise forms.ValidationError('RFID consent is required when selecting RFID authentication.')
        if method in (AuthMethod.FACE, AuthMethod.FINGERPRINT) and not data.get('consent_biometric'):
            raise forms.ValidationError('Biometric consent is required for face or fingerprint authentication.')
        if not data.get('data_retention'):
            raise forms.ValidationError('You must accept the data retention policy.')
        return data


class ConsentForm(forms.ModelForm):
    """Consent management (FR-2, FR-12)."""
    class Meta:
        model = ConsentRecord
        fields = ('biometric_consent', 'rfid_consent', 'data_retention_ack')


class RFIDEnrollForm(forms.Form):
    """Capture RFID tag during enrollment (after consent)."""
    rfid_tag = forms.CharField(max_length=100, widget=forms.PasswordInput(attrs={'autocomplete': 'off'}))


class CustomAuthenticationForm(AuthenticationForm):
    """Login with email or registration number (e.g. FA22-BSE-069) and password."""
    username = forms.CharField(
        label='Email or registration number',
        widget=forms.TextInput(attrs={
            'autocomplete': 'username',
            'placeholder': 'e.g. you@uni.edu or FA22-BSE-069',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Email or registration number'


# ---------------------------------------------------------------------------
# Admin user management (UC-6)
# ---------------------------------------------------------------------------

class AdminUserCreateForm(forms.ModelForm):
    """
    Admin enrolls a new user (FR-1, FR-2, UC-6).
    Includes Digital Consent Form fields and authentication method selection
    so the entire enrollment lifecycle is admin-controlled.
    """
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)

    # ── Digital Consent Form (FR-2) ──
    auth_method = forms.ChoiceField(
        choices=AuthMethod.choices,
        label='Authentication Method',
        help_text='Select the primary authentication method for this user.',
    )
    consent_biometric = forms.BooleanField(
        required=False,
        label='Biometric data consent (face / fingerprint)',
        help_text='Required if authentication method is Face or Fingerprint.',
    )
    consent_rfid = forms.BooleanField(
        required=False,
        label='RFID data consent',
        help_text='Required if authentication method is RFID.',
    )
    data_retention = forms.BooleanField(
        required=True,
        label='Data retention policy acknowledged',
        help_text='The user acknowledges that their data will be stored and managed per institutional policy.',
    )
    # Optional: RFID tag when method is RFID (wizard step 3)
    rfid_tag = forms.CharField(
        required=False,
        max_length=100,
        label='RFID tag',
        help_text='Scan or enter the RFID card tag. Can be done later from User Management.',
        widget=forms.PasswordInput(attrs={'autocomplete': 'off', 'placeholder': 'Scan card or enter tag'}),
    )

    class Meta:
        model = User
        fields = ('email', 'institutional_id', 'first_name', 'last_name', 'role', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['institutional_id'].label = 'Registration number'
        self.fields['institutional_id'].help_text = 'Format: XX00-XXX-000 (e.g. FA22-BSE-069). Students use this to sign in.'

    def clean_institutional_id(self):
        id_val = self.cleaned_data.get('institutional_id')
        id_val = validate_registration_number(id_val)
        if User.objects.filter(institutional_id=id_val).exists():
            raise forms.ValidationError('A user with this registration number already exists.')
        return id_val

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        if p1:
            validate_password(p1)
        return p2

    def clean(self):
        data = super().clean()
        method = data.get('auth_method')
        if method == AuthMethod.RFID and not data.get('consent_rfid'):
            raise forms.ValidationError('RFID consent is required when selecting RFID authentication.')
        if method in (AuthMethod.FACE, AuthMethod.FINGERPRINT) and not data.get('consent_biometric'):
            raise forms.ValidationError('Biometric consent is required for face or fingerprint authentication.')
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class AdminUserEditForm(forms.ModelForm):
    """Admin edits an existing user (no password field)."""
    class Meta:
        model = User
        fields = ('email', 'institutional_id', 'first_name', 'last_name', 'role', 'phone', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['institutional_id'].label = 'Registration number'
        self.fields['institutional_id'].help_text = 'Format: XX00-XXX-000 (e.g. FA22-BSE-069).'

    def clean_institutional_id(self):
        id_val = self.cleaned_data.get('institutional_id')
        id_val = validate_registration_number(id_val)
        qs = User.objects.filter(institutional_id=id_val)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A user with this registration number already exists.')
        return id_val

    def clean_email(self):
        email = self.cleaned_data.get('email')
        qs = User.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email


class ProfileEditForm(forms.ModelForm):
    """Users edit their own profile."""
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone')


# ---------------------------------------------------------------------------
# Role-specific enrollment forms (redesigned enrollment system)
# ---------------------------------------------------------------------------

def _dept_choices():
    """Return active department queryset for use in department dropdowns."""
    from attendance.models import Department
    return Department.objects.filter(is_active=True).order_by('name')


class _BasePasswordMixin(forms.Form):
    """Shared password fields for all role forms."""
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'placeholder': 'Set password'}))
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password'}))

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1', '')
        p2 = self.cleaned_data.get('password2', '')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        if p1:
            validate_password(p1)
        return p2

    def set_password_on(self, user):
        user.set_password(self.cleaned_data['password1'])
        user.save(update_fields=['password'])


class _BaseConsentMixin(forms.Form):
    """Shared consent fields."""
    consent_biometric = forms.BooleanField(required=False, label='I consent to biometric data capture (face / fingerprint)')
    consent_rfid = forms.BooleanField(required=False, label='I consent to RFID card data storage')
    data_retention = forms.BooleanField(required=True, label='I acknowledge the data retention and deletion policy')


class StudentEnrollForm(_BasePasswordMixin, _BaseConsentMixin, forms.ModelForm):
    """
    Enroll a student. Attendance method is auto-assigned by gender:
      Male   → RFID (primary) + Face Recognition (secondary)
      Female → RFID (primary) + Fingerprint (secondary)
    """
    gender = forms.ChoiceField(
        choices=[('', '— Select —'), ('male', 'Male'), ('female', 'Female')],
        label='Gender',
    )
    age = forms.IntegerField(min_value=1, max_value=100, label='Age')
    department = forms.ModelChoiceField(queryset=None, label='Department', empty_label='— Select department —')
    parent_contact = forms.CharField(max_length=20, label='Parent / Guardian Contact', required=False,
                                     widget=forms.TextInput(attrs={'placeholder': '+92-XXX-XXXXXXX'}))

    class Meta:
        model = User
        fields = ('institutional_id', 'first_name', 'last_name', 'email', 'phone', 'age', 'gender', 'department', 'parent_contact')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = _dept_choices()
        self.fields['institutional_id'].label = 'Registration Number'
        self.fields['institutional_id'].help_text = 'Format: XX00-XXX-000 (e.g. FA22-BSE-069)'
        self.fields['email'].required = True

    def clean_institutional_id(self):
        val = validate_registration_number(self.cleaned_data.get('institutional_id', ''))
        if User.objects.filter(institutional_id=val).exists():
            raise forms.ValidationError('A student with this registration number already exists.')
        return val

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def clean_gender(self):
        val = self.cleaned_data.get('gender', '')
        if not val:
            raise forms.ValidationError('Please select gender.')
        return val

    def clean(self):
        data = super().clean()
        gender = data.get('gender')
        # Consent requirements for 2-factor methods (both RFID + biometric)
        if not data.get('consent_rfid'):
            raise forms.ValidationError('RFID consent is required — RFID is used to identify the student.')
        if not data.get('consent_biometric'):
            raise forms.ValidationError('Biometric consent is required — face/fingerprint is used to confirm identity.')
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        user.gender = self.cleaned_data['gender']
        user.age = self.cleaned_data['age']
        user.department = self.cleaned_data.get('department')
        user.parent_contact = self.cleaned_data.get('parent_contact', '')
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class TeacherEnrollForm(_BasePasswordMixin, _BaseConsentMixin, forms.ModelForm):
    """
    Enroll a professor/teacher. Attendance method auto-assigned by gender:
      Male   → Face Recognition (timetable identifies, face confirms)
      Female → RFID only
    """
    gender = forms.ChoiceField(
        choices=[('', '— Select —'), ('male', 'Male'), ('female', 'Female')],
        label='Gender',
    )
    department = forms.ModelChoiceField(queryset=None, label='Department', empty_label='— Select department —')

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'gender', 'department')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = _dept_choices()
        self.fields['email'].required = True

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def clean_gender(self):
        val = self.cleaned_data.get('gender', '')
        if not val:
            raise forms.ValidationError('Please select gender.')
        return val

    def clean(self):
        data = super().clean()
        gender = data.get('gender')
        if gender == 'male' and not data.get('consent_biometric'):
            raise forms.ValidationError('Biometric consent is required for male teachers — face recognition is used.')
        if gender == 'female' and not data.get('consent_rfid'):
            raise forms.ValidationError('RFID consent is required for female teachers.')
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PROFESSOR
        user.gender = self.cleaned_data['gender']
        user.department = self.cleaned_data.get('department')
        # Auto-generate institutional_id for teachers (email-based)
        base = self.cleaned_data['email'].split('@')[0][:20].upper()
        inst_id = f'TCH-{base}'
        counter = 1
        while User.objects.filter(institutional_id=inst_id).exists():
            inst_id = f'TCH-{base}-{counter}'
            counter += 1
        user.institutional_id = inst_id
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class ParentEnrollForm(_BasePasswordMixin, forms.ModelForm):
    """
    Enroll a parent. Linked to student by registration number.
    Gets dashboard access + email/SMS attendance reports.
    """
    student_reg_number = forms.CharField(
        max_length=50, label='Student Registration Number',
        help_text='The registration number of the student this parent is linked to.',
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['phone'].label = 'Parent Phone Number'
        self.fields['phone'].required = True

    def clean_student_reg_number(self):
        reg = self.cleaned_data.get('student_reg_number', '').strip().upper()
        if not User.objects.filter(institutional_id=reg, role=User.Role.STUDENT).exists():
            raise forms.ValidationError('No enrolled student found with this registration number.')
        return reg

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PARENT
        # Auto-generate institutional_id for parents
        base = self.cleaned_data['email'].split('@')[0][:20].upper()
        inst_id = f'PAR-{base}'
        counter = 1
        while User.objects.filter(institutional_id=inst_id).exists():
            inst_id = f'PAR-{base}-{counter}'
            counter += 1
        user.institutional_id = inst_id
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class AdminEnrollForm(_BasePasswordMixin, forms.ModelForm):
    """
    Enroll an admin account. Only existing admins can do this.
    Attendance method: Fingerprint only (enrolled via Pi hardware).
    """
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.ADMIN
        base = self.cleaned_data['email'].split('@')[0][:20].upper()
        inst_id = f'ADM-{base}'
        counter = 1
        while User.objects.filter(institutional_id=inst_id).exists():
            inst_id = f'ADM-{base}-{counter}'
            counter += 1
        user.institutional_id = inst_id
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user
