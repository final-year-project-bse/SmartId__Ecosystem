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
        kwargs.setdefault('role', self.model.Role.ADMIN)
        return self.create_user(email, password, **kwargs)


class User(AbstractUser):
    """Extended user with institutional ID and role (FR-1)."""
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        PROFESSOR = 'professor', 'Professor'
        ADMIN = 'admin', 'Administrator'
        PARENT = 'parent', 'Parent'

    username = None
    email = models.EmailField(unique=True)
    institutional_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    phone = models.CharField(max_length=20, blank=True)
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
        return f"{self.get_full_name()} ({self.institutional_id or '—'})"


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
    """Preferred authentication method per user (FR-1, FR-3)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='auth_method_preference')
    method = models.CharField(max_length=20, choices=AuthMethod.choices, default=AuthMethod.RFID)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'User auth methods'

    def __str__(self):
        return f"{self.user.institutional_id} -> {self.get_method_display()}"


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
