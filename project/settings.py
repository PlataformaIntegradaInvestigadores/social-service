import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()  # Carga las variables de entorno del archivo .env

# Configuración de Redis
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv(
    "REDIS_PASSWORD"
)  # Lee la contraseña de Redis del archivo .env


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")
JWT_SIGNING_KEY = os.getenv("JWT_SIGNING_KEY", SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
# Convert string "True" from .env to boolean True
DEBUG = os.getenv("DEBUG") == "True"

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("ALLOWED_HOSTS", "*").split(",") if host.strip()
]


# Application definition


INSTALLED_APPS = [
    "daphne",
    "corsheaders",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "drf_spectacular",
    "rest_framework",
    "channels",
    "apps",
    "apps.concensus",
    "apps.custom_auth",
    "apps.jobs",
    "apps.feeds",
]
# ada

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "project.urls"

# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:4200",
# ]

# CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = False

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:4200,http://127.0.0.1:4200,http://localhost:8082,http://127.0.0.1:8082,https://centinela.epn.edu.ec",
    ).split(",")
    if origin.strip()
]

AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)

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

WSGI_APPLICATION = "project.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        "OPTIONS": {
            # PostgreSQL specific options
            "sslmode": "prefer",
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=1440),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": os.getenv("JWT_ALGORITHM", "HS256"),
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

REST_FRAMEWORK = {
    # Configuración para Swagger
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.custom_auth.authentication.DualUserJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

# Configuración de DRF Spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "Social Consensus API",
    "DESCRIPTION": "API para la aplicación Social Consensus",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Recorta el prefijo interno del spec y lo reemplaza por la ruta publica
    # detras del gateway (nginx.conf: /api/social/ -> /api/), para que
    # "Try it out" en Swagger UI pegue a la URL real.
    "SCHEMA_PATH_PREFIX": "/api",
    "SCHEMA_PATH_PREFIX_TRIM": True,
    "SERVERS": [{"url": "/api/social", "description": "Gateway"}],
    # OTHER SETTINGS
}

# URL base para servir archivos media
MEDIA_URL = "/media/"

# Ruta del sistema de archivos donde se almacenarán los archivos media
MEDIA_ROOT = os.path.join(BASE_DIR, "apps/media")

DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

ASGI_APPLICATION = "project.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    # Cadena de conexión correcta
                    "address": f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0",
                }
            ],
        },
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "apps.custom_auth": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

# Configuración del microservicio de embeddings
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")

# Configuración del GRS (predictive_model_backend) para recomendación de tópicos
GRS_SERVICE_URL = os.getenv(
    "GRS_SERVICE_URL", "http://localhost:8003/api/v1/recommendations"
)

# Configuración de vectores
VECTOR_DIMENSIONS = 768  # Dimensiones del modelo de embeddings

# Configuración de Celery
CELERY_BROKER_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/1"
CELERY_RESULT_BACKEND = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/1"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Token compartido para sincronizacion interna desde el microservicio
# profile_identity_backend hacia las tablas legacy usadas por concensus/feed/jobs.
PROFILE_SYNC_INTERNAL_TOKEN = os.getenv("PROFILE_SYNC_INTERNAL_TOKEN", "")

# Fuente canonica de identidad usada por social para resolver snapshots de autor.
PROFILE_IDENTITY_BASE_URL = os.getenv(
    "PROFILE_IDENTITY_BASE_URL", "http://identity-service:8002"
)
