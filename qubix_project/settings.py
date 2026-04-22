import os
import dj_database_url
from pathlib import Path
import warnings
warnings.filterwarnings('ignore', '.*Unexpectedly, UWP app.*')

BASE_DIR = Path(__file__).resolve().parent.parent

# ============= SECURITY: Use environment variable for secret key =============
# For production, don't hardcode the secret key
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-fallback-key')

# ============= PRODUCTION: Set DEBUG to False =============
DEBUG = os.environ.get('DEBUG', 'False') == 'True'  # Default to False

# ============= PRODUCTION: Add your domain =============
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'qubix-lmr7.onrender.com',  # ← ADD YOUR RENDER DOMAIN
    '.onrender.com',  # Allows all Render subdomains
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_tailwind',
    'core',
    'blog',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # ← MUST BE HERE
    'core.middleware.TimezoneMiddleware',  # ✅ Now user is available
    'core.middleware.SessionTimeoutMiddleware',  # ✅ Now user is available
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'qubix_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.portfolio_data',
                'core.views.add_impersonation_banner',
            ],
        },
    },
]

WSGI_APPLICATION = 'qubix_project.wsgi.application'

# ============= DATABASE =============
# Keep SQLite for now (can upgrade to PostgreSQL later)
DATABASES = {
    'default': dj_database_url.config(default='sqlite:///db.sqlite3')
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

# ============= TIME ZONE: Use user's timezone =============
# Set default to UTC, but users can have their own
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ============= Static & Media Files =============
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============= Custom User Model =============
AUTH_USER_MODEL = 'core.CustomUser'

# ============= Crispy Forms =============
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# ============= EMAIL Settings (Keep your SendGrid) =============
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = os.environ.get('SENDGRID_API_KEY', '')
DEFAULT_FROM_EMAIL = 'lisam00333m@gmail.com'  # ← CHANGE to your domain

# ============= Login/Logout URLs =============
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'landing'

# ============= Messages =============
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.ERROR: 'danger',
}

# ============= Session Settings (Auto-logout after 30 min) =============
SESSION_COOKIE_AGE = 1800  # 30 minutes
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ============= PRODUCTION OPTIMIZATIONS for Render Free Tier =============
if not DEBUG:
    # Reduce memory usage
    CONN_MAX_AGE = 60  # Close database connections after 60 seconds
    DATA_UPLOAD_MAX_NUMBER_FIELDS = 1024
    
    # Disable unused features to save memory
    USE_THOUSAND_SEPARATOR = False
    
    # Static files optimization
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    
    # Session optimization
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'
    SESSION_CACHE_ALIAS = 'default'
    
# ============= PRODUCTION SECURITY SETTINGS =============
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = 'DENY'

# Extreme memory optimization for Render free tier
if not DEBUG:
    # Disable all unused features
    MIDDLEWARE = [m for m in MIDDLEWARE if 'debug' not in m.lower()]
    
    # Reduce database queries
    CONN_MAX_AGE = 0  # Close connection after each request
    
    # Disable password validators (they use memory)
    AUTH_PASSWORD_VALIDATORS = []
    
    # Use less memory for sessions
    SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'    