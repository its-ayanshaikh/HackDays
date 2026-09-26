"""
Django settings for AskMyData project.

Secrets are read from a .env file (see .env.example). Nothing sensitive is
hardcoded here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env at the project root.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-change-me")

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "askmydata.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "askmydata.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# The app itself needs NO relational DB — all analytical data comes from
# Snowflake. Django still needs a small DB for its internal machinery
# (sessions, admin). We default to zero-setup SQLite. If you prefer MySQL,
# set DB_ENGINE=mysql in .env and fill the DB_* values.
if os.getenv("DB_ENGINE", "sqlite").lower() == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "askmydata"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Snowflake / Cortex configuration (read from .env)
# ---------------------------------------------------------------------------
SNOWFLAKE = {
    "ACCOUNT": os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "USER": os.getenv("SNOWFLAKE_USER", ""),
    "PASSWORD": os.getenv("SNOWFLAKE_PASSWORD", ""),
    "ROLE": os.getenv("SNOWFLAKE_ROLE", ""),
    "WAREHOUSE": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    "DATABASE": os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_SAMPLE_DATA"),
    "SCHEMA": os.getenv("SNOWFLAKE_SCHEMA", "TPCH_SF1"),
    "CORTEX_MODEL": os.getenv("SNOWFLAKE_CORTEX_MODEL", "mistral-large2"),
}

# ---------------------------------------------------------------------------
# LLM provider (read from .env)
# ---------------------------------------------------------------------------
# Snowflake Cortex is preferred, but self-service trial accounts have it
# disabled. LLM_PROVIDER=auto tries Cortex first and falls back to a free
# external LLM (Groq / Gemini) so the demo always runs. The data is always
# queried on Snowflake regardless of which LLM answers.
LLM = {
    "PROVIDER": os.getenv("LLM_PROVIDER", "auto"),  # auto | cortex | groq | gemini
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
    "GROQ_MODEL": os.getenv("GROQ_MODEL", ""),  # blank = auto-detect a live model
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
    "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
}
