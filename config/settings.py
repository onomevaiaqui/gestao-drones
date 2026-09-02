import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(nome, padrao=False):
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in ("1", "true", "yes", "on")


DEBUG = env_bool("SISMOD_DEBUG", True)
SECRET_KEY = os.getenv("SISMOD_SECRET_KEY", "dev-only-change-this-key" if DEBUG else "").strip()
if not SECRET_KEY:
    raise RuntimeError("Defina SISMOD_SECRET_KEY antes de iniciar o SISMOD em produção.")
ALLOWED_HOSTS = [
    item.strip() for item in os.getenv("SISMOD_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if item.strip()
]
CSRF_TRUSTED_ORIGINS = [
    item.strip() for item in os.getenv("SISMOD_CSRF_TRUSTED_ORIGINS", "").split(",")
    if item.strip()
]

# Em produção (SISMOD_DEBUG=false), HTTPS e cookies seguros ficam ativos por
# padrão. As opções podem ser ajustadas no ambiente quando houver proxy reverso.
SECURE_SSL_REDIRECT = env_bool("SISMOD_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SISMOD_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("SISMOD_CSRF_COOKIE_SECURE", not DEBUG)
SECURE_HSTS_SECONDS = int(os.getenv("SISMOD_SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SISMOD_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SISMOD_SECURE_HSTS_PRELOAD", not DEBUG)
if env_bool("SISMOD_BEHIND_HTTPS_PROXY", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.ModoAcessoMiddleware",
    "core.middleware.LicencaSISMODMiddleware",
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

if os.getenv("SISMOD_DB_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("SISMOD_DB_NAME", "sismod"), "USER": os.getenv("SISMOD_DB_USER", "sismod"),
        "PASSWORD": os.getenv("SISMOD_DB_PASSWORD", ""), "HOST": os.getenv("SISMOD_DB_HOST"),
        "PORT": os.getenv("SISMOD_DB_PORT", "5432"), "CONN_MAX_AGE": 60,
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

SISMOD_MEDIA_STORAGE = os.getenv("SISMOD_MEDIA_STORAGE", "local").strip().lower()
if SISMOD_MEDIA_STORAGE not in ("local", "s3", "minio"):
    raise RuntimeError("SISMOD_MEDIA_STORAGE deve ser local, s3 ou minio.")
if SISMOD_MEDIA_STORAGE == "local":
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    opcoes_s3 = {
        "bucket_name": os.getenv("SISMOD_STORAGE_BUCKET", "").strip(),
        "access_key": os.getenv("SISMOD_STORAGE_ACCESS_KEY", "").strip(),
        "secret_key": os.getenv("SISMOD_STORAGE_SECRET_KEY", "").strip(),
        "region_name": os.getenv("SISMOD_STORAGE_REGION", "us-east-1").strip(),
        "default_acl": "private",
        "querystring_auth": True,
        "file_overwrite": False,
    }
    endpoint = os.getenv("SISMOD_STORAGE_ENDPOINT_URL", "").strip().rstrip("/")
    if endpoint:
        opcoes_s3["endpoint_url"] = endpoint
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": opcoes_s3},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

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
DJI_DOCK_ENABLED = os.getenv("DJI_DOCK_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
DJI_DOCK_COMMANDS_ENABLED = os.getenv("DJI_DOCK_COMMANDS_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
DJI_DOCK_OFFLINE_AFTER_SECONDS = int(os.getenv("DJI_DOCK_OFFLINE_AFTER_SECONDS", "120"))
DJI_DOCK_SIMULATOR_ENABLED = os.getenv("DJI_DOCK_SIMULATOR_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
DJI_DOCK_MQTT_USERNAME = os.getenv("DJI_DOCK_MQTT_USERNAME", "").strip()
DJI_DOCK_MQTT_PASSWORD = os.getenv("DJI_DOCK_MQTT_PASSWORD", "").strip()
DJI_DOCK_MQTT_CLIENT_ID = os.getenv("DJI_DOCK_MQTT_CLIENT_ID", "sismod-dock-consumer").strip()
DJI_DOCK_MQTT_TOPIC = os.getenv(
    "DJI_DOCK_MQTT_TOPIC",
    "sys/product/+/status,thing/product/+/osd,thing/product/+/state,thing/product/+/events,thing/product/+/services_reply",
).strip()
DJI_DOCK_MQTT_CA_CERT = os.getenv("DJI_DOCK_MQTT_CA_CERT", "").strip()
DJI_DOCK_WPML_URL_TTL_SECONDS = int(os.getenv("DJI_DOCK_WPML_URL_TTL_SECONDS", "3600"))
DJI_DOCK_COMMAND_TTL_SECONDS = int(os.getenv("DJI_DOCK_COMMAND_TTL_SECONDS", "300"))
DJI_DRC_ENABLED = env_bool("DJI_DRC_ENABLED", False)
DJI_DRC_SIMULATOR_ENABLED = env_bool("DJI_DRC_SIMULATOR_ENABLED", True)
DJI_DRC_COMMANDS_ENABLED = env_bool("DJI_DRC_COMMANDS_ENABLED", False)
DJI_DRC_SESSION_TTL_SECONDS = int(os.getenv("DJI_DRC_SESSION_TTL_SECONDS", "900"))
DJI_DRC_HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("DJI_DRC_HEARTBEAT_TIMEOUT_SECONDS", "3"))

# Livestream DJI. Permanece desligada até existir um servidor de mídia público.
DJI_LIVESTREAM_ENABLED = os.getenv("DJI_LIVESTREAM_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
DJI_LIVESTREAM_RTMP_BASE_URL = os.getenv("DJI_LIVESTREAM_RTMP_BASE_URL", "").strip().rstrip("/")
DJI_LIVESTREAM_PLAYBACK_BASE_URL = os.getenv("DJI_LIVESTREAM_PLAYBACK_BASE_URL", "").strip().rstrip("/")

# Licenciamento offline. Em desenvolvimento permanece desligado; nas instalações
# comerciais deve ser ativado e receber somente a chave pública do fornecedor.
SISMOD_LICENSE_ENFORCEMENT = os.getenv("SISMOD_LICENSE_ENFORCEMENT", "false").strip().lower() in ("1", "true", "yes", "on")
SISMOD_LICENSE_PUBLIC_KEY = os.getenv("SISMOD_LICENSE_PUBLIC_KEY", "").strip()
