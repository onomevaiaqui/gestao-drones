import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = "dev-only-change-this-key"
DEBUG = True
ALLOWED_HOSTS = [
    item.strip() for item in os.getenv("SISMOD_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if item.strip()
]
CSRF_TRUSTED_ORIGINS = [
    item.strip() for item in os.getenv("SISMOD_CSRF_TRUSTED_ORIGINS", "").split(",")
    if item.strip()
]

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
    "core.middleware.ModoAcessoMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# Credenciais externas são carregadas apenas do ambiente e nunca do Git.
DJI_FLIGHT_RECORD_APP_KEY = os.getenv("DJI_FLIGHT_RECORD_APP_KEY", "").strip()

# DJI Open Platforms / Cloud API. Os valores sensíveis existem apenas no .env.
DJI_CLOUD_ENABLED = os.getenv("DJI_CLOUD_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
DJI_CLOUD_APP_ID = os.getenv("DJI_CLOUD_APP_ID", "").strip()
DJI_CLOUD_APP_KEY = os.getenv("DJI_CLOUD_APP_KEY", "").strip()
DJI_CLOUD_APP_LICENSE = os.getenv("DJI_CLOUD_APP_LICENSE", "").strip()
DJI_CLOUD_WORKSPACE_ID = os.getenv("DJI_CLOUD_WORKSPACE_ID", "").strip()
DJI_CLOUD_PUBLIC_URL = os.getenv("DJI_CLOUD_PUBLIC_URL", "").strip().rstrip("/")
DJI_CLOUD_API_HOST = os.getenv("DJI_CLOUD_API_HOST", DJI_CLOUD_PUBLIC_URL).strip().rstrip("/")
DJI_CLOUD_MQTT_HOST = os.getenv("DJI_CLOUD_MQTT_HOST", "").strip()
DJI_CLOUD_MQTT_USERNAME_PREFIX = os.getenv("DJI_CLOUD_MQTT_USERNAME_PREFIX", "sismod-pilot").strip()
DJI_CLOUD_PLATFORM_NAME = os.getenv("DJI_CLOUD_PLATFORM_NAME", "SISMOD").strip()
DJI_CLOUD_WORKSPACE_NAME = os.getenv("DJI_CLOUD_WORKSPACE_NAME", "Operações SISMOD").strip()
DJI_CLOUD_WORKSPACE_DESCRIPTION = os.getenv(
    "DJI_CLOUD_WORKSPACE_DESCRIPTION", "Monitoramento e gestão de operações com drones"
).strip()
