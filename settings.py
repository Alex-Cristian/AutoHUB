from pathlib import Path
import dj_database_url
import os
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = 'django-insecure-autohub-marketplace-change-in-production-2024-xyz'

DEBUG = False

def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name, default=''):
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


RUNNING_ON_RENDER = env_bool('RENDER', False)

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', '127.0.0.1,localhost,autoemg.com,www.autoemg.com,.onrender.com')

# ===== CSRF & SESSION — fix mobil =====
CSRF_COOKIE_AGE = 31449600          # 1 an — token nu mai expiră între page load și submit
CSRF_COOKIE_HTTPONLY = False         # permite browserului mobil să citească cookie-ul
CSRF_COOKIE_SAMESITE = 'Lax'        # compatibil cu redirect-uri și browsere mobile
SESSION_COOKIE_AGE = 2592000        # 30 zile — userii rămân logați
SESSION_SAVE_EVERY_REQUEST = True   # resetează timer-ul la fiecare request
SESSION_COOKIE_SAMESITE = 'Lax'     # compatibil cu browsere mobile
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', 'https://autoemg.com,https://www.autoemg.com')
USE_X_FORWARDED_HOST = env_bool('USE_X_FORWARDED_HOST', True)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CANONICAL_HOST = os.getenv('CANONICAL_HOST', 'autoemg.com').strip()
CANONICAL_SITE_URL = os.getenv('CANONICAL_SITE_URL', f'https://{CANONICAL_HOST}').rstrip('/')
CANONICAL_REDIRECT_HOSTS = env_list('CANONICAL_REDIRECT_HOSTS', f'{CANONICAL_HOST},www.{CANONICAL_HOST}')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'django.contrib.staticfiles',
    'cloudinary',
    'cloudinary_storage',
    # Local
    'core.apps.CoreConfig',
    'accounts.apps.AccountsConfig',
    'services.apps.ServicesConfig',
    'bookings.apps.BookingsConfig',
    'invoices.apps.InvoicesConfig',
]


MIDDLEWARE = [
    'core.middleware.CanonicalHostMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'autohub.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.global_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'autohub.wsgi.application'

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
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

SESSION_ENGINE = os.getenv('SESSION_ENGINE', 'django.contrib.sessions.backends.db')

LANGUAGE_CODE = 'ro'
TIME_ZONE = 'Europe/Bucharest'
USE_I18N = True
USE_TZ = True
SITE_ID = 1

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATIC_ROOT = BASE_DIR / 'staticfiles'

USE_CLOUDINARY = os.getenv('USE_CLOUDINARY', 'True').lower() == 'true'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

if USE_CLOUDINARY:
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME', ''),
        'API_KEY': os.getenv('CLOUDINARY_API_KEY', ''),
        'API_SECRET': os.getenv('CLOUDINARY_API_SECRET', ''),
        'SECURE': True,
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')

SITE_BASE_URL = os.getenv('SITE_BASE_URL', CANONICAL_SITE_URL if RUNNING_ON_RENDER else 'http://127.0.0.1:8000')
APP_URL = os.getenv('APP_URL', SITE_BASE_URL)
AUTH_SECRET = os.getenv('AUTH_SECRET', SECRET_KEY)
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', '')
GOOGLE_AUTHORIZATION_URL = os.getenv('GOOGLE_AUTHORIZATION_URL', 'https://accounts.google.com/o/oauth2/v2/auth')
GOOGLE_TOKEN_URL = os.getenv('GOOGLE_TOKEN_URL', 'https://oauth2.googleapis.com/token')
GOOGLE_USERINFO_URL = os.getenv('GOOGLE_USERINFO_URL', 'https://openidconnect.googleapis.com/v1/userinfo')
GOOGLE_JWKS_URL = os.getenv('GOOGLE_JWKS_URL', 'https://www.googleapis.com/oauth2/v3/certs')
GOOGLE_DISCOVERY_URL = os.getenv('GOOGLE_DISCOVERY_URL', 'https://accounts.google.com/.well-known/openid-configuration')
OAUTH_DEBUG_ERRORS = os.getenv('OAUTH_DEBUG_ERRORS', str(DEBUG)).strip().lower() in {'1', 'true', 'yes', 'on'}

DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB

SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', RUNNING_ON_RENDER)

if USE_CLOUDINARY and all([
    os.getenv('CLOUDINARY_CLOUD_NAME'),
    os.getenv('CLOUDINARY_API_KEY'),
    os.getenv('CLOUDINARY_API_SECRET'),
]):
    STORAGES = {
        'default': {
            'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
