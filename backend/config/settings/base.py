"""Réglages communs à tous les environnements.

Les valeurs propres à une machine viennent des variables d'environnement (voir `.env.example`).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name: str, default: str | None = None) -> str | None:
    # Une ligne `NOM=` laissée vide dans `.env` vaut « absente » : la valeur par défaut s'applique.
    value = os.environ.get(name, "").strip()
    return value or default


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in (env(name) or default).split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY")
# Anciennes clés, séparées par des virgules, après un changement de `DJANGO_SECRET_KEY` : les
# sessions, les clés TOTP chiffrées et les codes de secours restent lisibles.
SECRET_KEY_FALLBACKS = env_list("DJANGO_SECRET_KEY_FALLBACKS")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
# En-tête où le proxy (Caddy) écrit l'adresse du visiteur, ex. `HTTP_X_REAL_IP` ; vide : la
# connexion elle-même (`REMOTE_ADDR`). Seulement si Django n'est joignable que par ce proxy.
CLIENT_IP_HEADER = env("DJANGO_CLIENT_IP_HEADER")

INSTALLED_APPS = [
    # Administration Django du super-admin, avec la double authentification.
    "apps.accounts.apps.PlatformAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "apps.core",
    "apps.schools",
    "apps.accounts",
    "apps.audit",
    "apps.students",
    "apps.finance",
    "apps.sync",
    "apps.notifications",
    "apps.portal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.middleware.TenantMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Adresse IP et navigateur de la requête pour le journal d'audit.
    "apps.audit.middleware.AuditMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Domaines sous lesquels chaque sous-domaine est une école : {code}.mwangaza.school.
# Le domaine seul et les sous-domaines réservés (parents, admin, www…) n'ont pas d'école.
SCHOOL_BASE_DOMAINS = env_list("DJANGO_SCHOOL_BASE_DOMAINS", "mwangaza.school")
# Adresse d'une école, pour les liens de l'administration (« Ouvrir en tant qu'école ») et de
# `make demo`.
SCHOOL_URL = env("DJANGO_SCHOOL_URL", "https://{code}.mwangaza.school")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
                "apps.core.context_processors.platform",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "mwangaza"),
        "USER": env("POSTGRES_USER", "mwangaza"),
        "PASSWORD": env("POSTGRES_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": False,
        "CONN_MAX_AGE": 60,
        # Sans la compilation JIT de PostgreSQL : sur les rapports (impayés, des milliers de
        # frais dus), elle coûtait plus que la requête elle-même (0,75 s sur 0,85 s).
        "OPTIONS": {"options": "-c jit=off"},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Un compte par personne, identifié par son numéro de téléphone (`apps/accounts`).
AUTH_USER_MODEL = "accounts.User"
# Portail des parents (un seul domaine pour toutes les écoles), écrit sur la fiche d'inscription.
PORTAL_URL = env("DJANGO_PORTAL_URL", "https://parents.mwangaza.school")
# Indicatif du pays pour un numéro tapé sous sa forme nationale (0971234567) : RDC.
PHONE_DEFAULT_COUNTRY_CODE = "243"

# Connexion par téléphone, avec la limitation des tentatives (API et administration Django).
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.PhoneBackend"]

# Argon2 ; un ancien mot de passe (PBKDF2, avant la 1.3) est converti à la connexion suivante.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ["phone", "last_name", "middle_name", "first_name"]},
    },
    # Au moins 10 caractères (Mon compte, M4).
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Langue et fuseau : français par défaut, anglais disponible ; Goma est en UTC+2.
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
# Posé par la Gestion et le Portail (`packages/i18n`) : le serveur suit la langue de l'interface.
LANGUAGE_COOKIE_NAME = "django_language"
TIME_ZONE = "Africa/Lubumbashi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    # Fermé par défaut : chaque endpoint ouvre explicitement ce qu'il expose.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    # Erreurs au format `{code, detail}` (`apps/core/errors.py`).
    "EXCEPTION_HANDLER": "apps.core.errors.api_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Mwangaza API",
    "DESCRIPTION": "API de la plateforme de gestion scolaire Mwangaza.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Schémas séparés pour l'envoi (`…Request`) et la réponse ; dans une réponse, tout champ est
    # obligatoire (`apps/core/schema.py`) : types exacts pour le client du front (`packages/api`).
    "COMPONENT_SPLIT_REQUEST": True,
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.core.schema.responses_always_have_every_field",
    ],
    # Une seule liste de devises, sous un seul nom (devises de l'école, devise principale).
    "ENUM_NAME_OVERRIDES": {
        "CurrencyEnum": "apps.core.money.Currency",
        "SchoolStatusEnum": "apps.schools.models.School.Status",
        "YearStatusEnum": "apps.schools.models.AcademicYear.Status",
        "EnrollmentStatusEnum": "apps.students.models.Enrollment.Status",
        "FeeCategoryEnum": "apps.finance.models.FeeType.Category",
        "DiscountKindEnum": "apps.finance.models.Discount.Kind",
        "TermKindEnum": "apps.schools.models.Term.Kind",
        "CreditStateEnum": "apps.finance.serializers.CREDIT_STATES",
        "CancellationStatusEnum": "apps.finance.models.CancellationRequest.Status",
        "ClosingStateEnum": "apps.finance.serializers.CLOSING_STATES",
        "HealthCheckEnum": "apps.core.health.CHECKS",
        "HealthStatusEnum": "apps.core.health.STATUSES",
    },
}

CELERY_BROKER_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TIMEZONE = TIME_ZONE

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
    # Les messages de Django passent par la console ci-dessus : sans ce réglage, sa console à lui
    # (en DEBUG) les écrirait une seconde fois.
    "loggers": {"django": {"handlers": []}},
}
