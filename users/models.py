"""
User Enrollment, Consent, and Authentication methods (FR-1, FR-2, FR-11, FR-12, FR-13).
"""
import base64
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    def get_fernet():
        """AES-256–style encryption for biometric data (FR-11)."""
        key = settings.BIOMETRIC_ENCRYPTION_KEY.encode()[:32].ljust(32, b'0')
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b'smartid_salt', iterations=100000)
        key = base64.urlsafe_b64encode(kdf.derive(key))
        return Fernet(key)
except ImportError:
    def get_fernet():
        """Fallback when cryptography not installed (dev only). Use: pip install cryptography."""
        class _SimpleCipher:
            def encrypt(self, b): return base64.urlsafe_b64encode(b)          # returns bytes like Fernet
            def decrypt(self, b): return base64.urlsafe_b64decode(b)
        return _SimpleCipher()


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **kwargs):
        if not email:
            raise ValueError('Users must have an email')
        user = self.model(email=self.normalize_email(email), **kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **kwargs):
        kwargs.setdefault('is_staff', True)
        kwargs.setdefault('is_superuser', True)
        return self.create_user(email, password, **kwargs)


class User(AbstractUser):
    """Extended user with institutional ID and role (FR-1)."""
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        PROFESSOR = 'professor', 'Professor'
        ADMIN = 'admin', 'Administrator'
        PARENT = 'parent', 'Parent'

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'

    username = None
    email = models.EmailField(unique=True)
    institutional_id = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    parent_contact = models.CharField(max_length=20, blank=True, help_text="Parent/guardian phone number (students only)")
    department = models.ForeignKey(
        'attendance.Department', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='members',
    )
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['institutional_id']

    objects = UserManager()

    class Meta:
        indexes = [
            models.Index(fields=['role', 'is_active']),      # dashboard queries
            models.Index(fields=['institutional_id']),        # lookup by ID
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.institutional_id})"


class FailedLoginAttempt(models.Model):
    """One row per failed web login (regular or admin). Used for analytics (FR-10)."""
    identifier = models.CharField(max_length=255, help_text='Email or username attempted')
    is_admin_attempt = models.BooleanField(default=False, help_text='True if attempt was on admin login page')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['-created_at']), models.Index(fields=['is_admin_attempt'])]

    def __str__(self):
        return f"Failed {'admin ' if self.is_admin_attempt else ''}login: {self.identifier} @ {self.created_at}"


class ConsentRecord(models.Model):
    """Digital consent for biometric/RFID data (FR-2)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='consent')
    accepted_at = models.DateTimeField(auto_now_add=True)
    biometric_consent = models.BooleanField(default=False)
    rfid_consent = models.BooleanField(default=False)
    data_retention_ack = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"Consent for {self.user.institutional_id}"


class AuthMethod(models.TextChoices):
    FACE = 'face', 'Facial Recognition'
    FINGERPRINT = 'fingerprint', 'Fingerprint'
    RFID = 'rfid', 'RFID Card'


class UserAuthMethod(models.Model):
    """
    Attendance authentication method(s) per user.
    primary_method identifies the user (e.g. RFID card scan).
    secondary_method authenticates/confirms identity (e.g. face or fingerprint).
    For single-factor roles secondary_method is blank.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='auth_method_preference')
    method = models.CharField(max_length=20, choices=AuthMethod.choices, default=AuthMethod.RFID,
                              help_text='Primary method — identifies the user')
    secondary_method = models.CharField(max_length=20, choices=AuthMethod.choices, blank=True,
                                        help_text='Secondary method — confirms identity (blank = single-factor)')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'User auth methods'

    def __str__(self):
        sec = f' + {self.secondary_method}' if self.secondary_method else ''
        return f"{self.user.institutional_id} -> {self.method}{sec}"


class RFIDCredential(models.Model):
    """Stored RFID identifier (encrypted reference)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rfid_credential')
    encrypted_tag = models.TextField()  # encrypted RFID tag value
    created_at = models.DateTimeField(auto_now_add=True)

    def set_tag(self, raw_tag: str):
        f = get_fernet()
        self.encrypted_tag = f.encrypt(raw_tag.encode()).decode()
        self.save(update_fields=['encrypted_tag'])

    def check_tag(self, raw_tag: str) -> bool:
        try:
            f = get_fernet()
            return f.decrypt(self.encrypted_tag.encode()).decode() == raw_tag
        except Exception:
            return False


class BiometricEmbedding(models.Model):
    """Encrypted face/fingerprint embedding only (FR-11); no raw data."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='biometric_embedding')
    method = models.CharField(max_length=20, choices=AuthMethod.choices)
    encrypted_data = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def set_embedding(self, raw_data: bytes):
        f = get_fernet()
        self.encrypted_data = f.encrypt(raw_data).decode()
        self.save(update_fields=['encrypted_data'])

    def get_embedding(self):
        f = get_fernet()
        return f.decrypt(self.encrypted_data.encode())


class ParentStudentLink(models.Model):
    """Links a parent user to their student child(ren)."""
    parent = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='children_links',
        limit_choices_to={'role': 'parent'},
    )
    student = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='parent_links',
        limit_choices_to={'role': 'student'},
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['parent', 'student']]
        indexes = [models.Index(fields=['parent'])]

    def __str__(self):
        return f"{self.parent.get_full_name()} \u2192 {self.student.get_full_name()}"


class UniversityRecord(models.Model):
    """
    Placeholder for university student database integration.
    Admin pre-populates these rows; a real API lookup replaces this later.
    Queried by registration number during student enrollment to auto-fill fields.
    """
    registration_number = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    department = models.ForeignKey(
        'attendance.Department', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='university_records',
    )
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True, help_text='Additional info from university registry')
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['registration_number']

    def __str__(self):
        return f"{self.registration_number} \u2014 {self.full_name}"
