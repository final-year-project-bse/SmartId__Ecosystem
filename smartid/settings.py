"""
SmartID Ecosystem - Django settings (SRS OE/CO compliant).
"""
import os
from pathlib import Path
_env = os.environ.get

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = _env('SECRET_KEY', 'django-insecure-dev-key-change-in-production')
DEBUG = _env('DEBUG', 'True').lower() not in ('0', 'false', 'no')
ALLOWED_HOSTS = _env('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'users',
    'attendance',
    'dashboard',
    'notifications',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'dashboard.middleware.QueryTimingMiddleware',       # NFR-P2 performance guard
]

ROOT_URLCONF = 'smartid.urls'
WSGI_APPLICATION = 'smartid.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notifications.context_processors.unread_notification_count',
            ],
        },
    },
]

# Database: set DB_ENGINE=postgresql or mysql to override (default: sqlite).
# PostgreSQL: pip install psycopg2-binary, set DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT.
# MySQL: pip install mysqlclient, set same env vars.
_db_engine = _env('DB_ENGINE', 'sqlite').lower()
if _db_engine == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _env('DB_NAME', 'smartid'),
            'USER': _env('DB_USER', 'postgres'),
            'PASSWORD': _env('DB_PASSWORD', ''),
            'HOST': _env('DB_HOST', '127.0.0.1'),
            'PORT': _env('DB_PORT', '5432'),
            'OPTIONS': {},
        }
    }
elif _db_engine == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': _env('DB_NAME', 'smartid'),
            'USER': _env('DB_USER', 'root'),
            'PASSWORD': _env('DB_PASSWORD', ''),
            'HOST': _env('DB_HOST', '127.0.0.1'),
            'PORT': _env('DB_PORT', '3306'),
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'users.User'
AUTHENTICATION_BACKENDS = ['users.backends.EmailOrRegistrationBackend']
LOGIN_REDIRECT_URL = 'dashboard:home'
LOGIN_URL = 'users:login'
LOGOUT_REDIRECT_URL = 'users:login'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

try:
    import crispy_forms  # noqa: F401
    INSTALLED_APPS = list(INSTALLED_APPS) + ['crispy_forms', 'crispy_bootstrap5']
    CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
    CRISPY_TEMPLATE_PACK = 'bootstrap5'
except ImportError:
    pass

# Session timeout — read from SystemSetting at startup; fallback 10 min (SEC-4)
def _session_timeout():
    try:
        from dashboard.models import SystemSetting
        return SystemSetting.load().session_timeout_minutes * 60
    except Exception:
        return 600

SESSION_COOKIE_AGE = _session_timeout()
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Email (optional, for notifications — FR-9, FR-10)
# Default: console backend (prints to stdout). Set EMAIL_HOST to use SMTP.
_email_host = _env('EMAIL_HOST', '')
if _email_host:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = _email_host
    EMAIL_PORT = int(_env('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = _env('EMAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    EMAIL_HOST_USER = _env('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = _env('EMAIL_HOST_PASSWORD', '')
    EMAIL_TIMEOUT = int(_env('EMAIL_TIMEOUT', '30'))
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = _env('DEFAULT_FROM_EMAIL', 'smartid@campus.edu')
# When True, in-app notifications also trigger an email to the recipient(s).
NOTIFICATIONS_SEND_EMAIL = _env('NOTIFICATIONS_SEND_EMAIL', 'false').lower() in ('1', 'true', 'yes')

# Biometric storage: encrypted embeddings only (FR-11)
BIOMETRIC_ENCRYPTION_KEY = _env('BIOMETRIC_ENCRYPTION_KEY', SECRET_KEY[:32].ljust(32, '0'))

# ── REST Framework (API for IoT devices & mobile) ──
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}
