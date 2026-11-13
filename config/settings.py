"""
Configuracion de Django para el Simulador Educativo de Inversiones.

Toda la configuracion sensible o dependiente del entorno se lee desde
variables de entorno (ver .env.example). En desarrollo local, si no se
define DB_ENGINE, el proyecto usa SQLite automaticamente para no requerir
un servidor MySQL instalado. En produccion (cPanel) se debe definir
DB_ENGINE=mysql y las credenciales correspondientes.
"""

from pathlib import Path
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-cambiar-en-produccion')

DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

CSRF_TRUSTED_ORIGINS = config('DJANGO_CSRF_TRUSTED_ORIGINS', default='', cast=Csv())


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Apps del proyecto
    'apps.usuarios',
    'apps.cursos',
    'apps.mercados',
    'apps.operaciones',
    'apps.portafolios',
    'apps.analitica',
    'apps.reportes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Base de datos
# DB_ENGINE=mysql -> MySQL/MariaDB (produccion). Cualquier otro valor (o
# ausencia de la variable) -> SQLite local, para poder desarrollar y
# probar sin depender de un servidor MySQL configurado.

if config('DB_ENGINE', default='sqlite') == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=60, cast=int),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            # timeout alto: SQLite solo admite un escritor a la vez; con un
            # timeout bajo, dos transacciones concurrentes (p. ej. en las
            # pruebas de concurrencia) fallan con "database is locked" en
            # lugar de esperar su turno. En MySQL/InnoDB (produccion) esto
            # no aplica: el motor soporta escrituras concurrentes reales.
            'OPTIONS': {'timeout': 20},
        }
    }


AUTH_USER_MODEL = 'usuarios.Usuario'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'usuarios:login'
LOGIN_REDIRECT_URL = 'usuarios:redireccion_rol'
LOGOUT_REDIRECT_URL = 'usuarios:login'

# Control de intentos de inicio de sesion (bloqueo simple basado en cache)
LOGIN_MAX_INTENTOS = config('LOGIN_MAX_INTENTOS', default=5, cast=int)
LOGIN_BLOQUEO_MINUTOS = config('LOGIN_BLOQUEO_MINUTOS', default=15, cast=int)


# Internacionalizacion

LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True


# Archivos estaticos

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise sirve los estaticos directamente desde Django en produccion:
# necesario porque Passenger/cPanel enruta toda solicitud a la app (no hay
# Apache sirviendo /static/ por su cuenta), y Django no sirve estaticos por
# si mismo cuando DEBUG=False. Ver docs/despliegue_cpanel.md seccion 11.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Cache en memoria local del proceso. Se usa para precalcular metricas de
# analitica y para el control de intentos de login. En hosting compartido
# con un solo proceso Passenger esto es suficiente; si se usan multiples
# procesos, cada uno mantiene su propia cache (ver docs/arquitectura.md).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'simulador-cache',
    }
}


# Seguridad adicional para produccion (se activa automaticamente cuando
# DEBUG=False). Ver docs/despliegue_cpanel.md.
if not DEBUG:
    SECURE_SSL_REDIRECT = config('DJANGO_SECURE_SSL_REDIRECT', default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = config('DJANGO_HSTS_SECONDS', default=3600, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=28800, cast=int)  # 8 horas


# Parametros propios del simulador (valores por defecto documentados en
# docs/reglas_financieras.md; cada curso puede sobreescribir los que
# correspondan a nivel de configuracion de curso).
SIMULADOR = {
    'CAPITAL_INICIAL_USD_DEFAULT': config('CAPITAL_INICIAL_USD_DEFAULT', default='1000000.00'),
    'TASA_LIBRE_RIESGO_ANUAL_DEFAULT': config('TASA_LIBRE_RIESGO_ANUAL_DEFAULT', default='0.10'),
    'COMISION_OPERACION_DEFAULT': config('COMISION_OPERACION_DEFAULT', default='0.00'),
    'PROVEEDOR_DATOS_MERCADO': config('PROVEEDOR_DATOS_MERCADO', default='sintetico'),
}


# Logging: a archivo en produccion, consola en desarrollo. Nunca se
# registran valores de API keys, contrasenas o secretos.
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'simulador.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'] if DEBUG else ['file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'] if DEBUG else ['file'],
            'level': 'WARNING' if not DEBUG else 'INFO',
            'propagate': False,
        },
        'simulador': {
            'handlers': ['console'] if DEBUG else ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
