"""Configuração do Django — uso local, banco SQLite."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("PATENTOMETRIA_SECRET_KEY", "dev-local-somente-altere-em-producao")
DEBUG = os.environ.get("PATENTOMETRIA_DEBUG", "1") == "1"

# ALLOWED_HOSTS por ambiente: "host1,host2". Serve para abrir a aplicação na rede
# local sem depender de DEBUG=True; o padrão fica no loopback.
ALLOWED_HOSTS = [h.strip() for h in
                 os.environ.get("PATENTOMETRIA_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
                 if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "studies",
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

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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
        "NAME": os.environ.get("PATENTOMETRIA_DB", BASE_DIR / "db.sqlite3"),
    }
}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 20000

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
