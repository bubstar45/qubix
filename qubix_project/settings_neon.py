# qubix_project/settings_neon.py
import os
import dj_database_url
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Import everything from main settings but we'll override database
from .settings import *

# Get your Neon connection string from Render
# It looks like: postgresql://username:password@host:5432/database
NEON_DATABASE_URL = 'postgresql://neondb_owner:npg_aeCtv5zn8JuN@ep-odd-base-ammvafzf-pooler.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

# Override database to use Neon
DATABASES = {
    'default': dj_database_url.config(default=NEON_DATABASE_URL)
}

# Disable HTTPS requirements temporarily for local migration
DEBUG = True
SECURE_SSL_REDIRECT = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0