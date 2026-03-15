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
