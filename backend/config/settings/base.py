"""Réglages communs à tous les environnements.

Les valeurs propres à une machine viennent des variables d'environnement (voir `.env.example`).
"""

import os
from pathlib import Path

from celery.schedules import crontab

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
# Adresses IP ou réseaux d'où un compte super-admin peut être utilisé (S.3.1,
# `apps/accounts/privileged.py`) ; vide : toutes.
CONSOLE_ALLOWED_IPS = env_list("DJANGO_CONSOLE_ALLOWED_IPS")

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
    "apps.academics",
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
    # Compte super-admin : adresses autorisées et session courte (S.3.1).
    "apps.accounts.privileged.PrivilegedAccountMiddleware",
    # Portée de la base (S.6) des requêtes sans école : console, administration, Portail.
    "apps.core.middleware.RowSecurityMiddleware",
    # PDF lourds en tâche de fond (PERF.1) : après l'école et le compte de la requête.
    "apps.core.printing.PrintJobMiddleware",
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
        # Garde-fou (PERF.1, réglé en production pour le site seulement) : une requête ou une
        # transaction qui traîne est coupée au lieu de garder la base.
        "OPTIONS": {
            "options": "-c jit=off"
            + (
                f" -c statement_timeout={env('DB_STATEMENT_TIMEOUT_MS')}"
                " -c idle_in_transaction_session_timeout=30000"
                if env("DB_STATEMENT_TIMEOUT_MS", "")
                else ""
            )
        },
    }
}
# Production (S.5) : `POSTGRES_USER` est un compte à droits réduits, que le compte des migrations
# crée et tient à jour avec `manage.py setup_app_role` (service `migrate`). Vides ailleurs :
# développement et tests gardent un seul compte.
DATABASE_APP_USER = env("POSTGRES_APP_USER", "")
DATABASE_APP_PASSWORD = env("POSTGRES_APP_PASSWORD", "")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Un compte par personne, identifié par son numéro de téléphone (`apps/accounts`).
AUTH_USER_MODEL = "accounts.User"
# Portail des parents (un seul domaine pour toutes les écoles), écrit sur la fiche d'inscription.
PORTAL_URL = env("DJANGO_PORTAL_URL", "https://parents.mwangaza.school")
# Auteur du logiciel (pas l'identité de la plateforme, qui vient de ses paramètres) : balise
# `<meta name="author">` du site public, ses données structurées et `llms.txt`, jamais signé dans
# la page (`apps/core/site.py`). Titulaire des droits : le « © … Tous droits réservés » du pied.
SOFTWARE_AUTHOR = "Guelord Mwenderwa"
SOFTWARE_AUTHOR_URL = "https://github.com/GUELORD-MWENDERWA"
SOFTWARE_COPYRIGHT = "DTMS"
SOFTWARE_COPYRIGHT_URL = "https://dtms.site"
# Notifications sur l'écran (5.5, Web Push) : paire de clés VAPID de la plateforme, créée une fois
# par `manage.py webpush_keys` et jamais changée (elle invaliderait tous les abonnements). Vides :
# rien n'est envoyé sur les écrans ; le centre de notifications marche quand même.
WEBPUSH_VAPID_PUBLIC_KEY = env("WEBPUSH_VAPID_PUBLIC_KEY", "")
WEBPUSH_VAPID_PRIVATE_KEY = env("WEBPUSH_VAPID_PRIVATE_KEY", "")
# `make demo` : données fictives permises en développement, dans l'essai sur plusieurs appareils et
# sur le serveur de démonstration en ligne (`infra/docker-compose.reseau.yml`), jamais sur le
# serveur des vraies écoles.
DEMO_DATA = False
# Serveur de démonstration en ligne (4.6.2) : mot de passe des comptes fictifs, propre au serveur ;
# défini, `make demo` n'active aucune clé commune de double authentification (`accounts/demo.py`).
DEMO_PASSWORD = ""
# Espaces de démonstration (4.17.2) : nombre maximal sur la plateforme, ceux de `make demo`
# compris. Ils partagent la base des vraies écoles ; au plus 60 blocs de numéros.
DEMO_SPACES_MAX = int(env("DJANGO_DEMO_SPACES_MAX", "5"))
# Indicatif du pays pour un numéro tapé sous sa forme nationale (0971234567) : RDC.
PHONE_DEFAULT_COUNTRY_CODE = "243"

# Connexion par téléphone, avec la limitation des tentatives (API et administration Django).
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.PhoneBackend"]

# Argon2, un hachage à la fois par processus (`core/hashers.py`) ;
# un ancien mot de passe (PBKDF2, avant la 1.3) est converti à la connexion suivante.
PASSWORD_HASHERS = [
    "apps.core.hashers.SerialArgon2PasswordHasher",
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
    # Recherche et sorties lourdes (PDF, Excel, exports), par compte (`core/throttling.py`).
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.core.throttling.SearchThrottle",
        "apps.core.throttling.OutputThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"search": "120/min", "output": "20/min"},
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
        "GradeEntryEnum": "apps.schools.grading.ENTRY_CHOICES",
        "ResitModeEnum": "apps.schools.pass_rules.MODE_CHOICES",
        "ModulesEnum": "apps.accounts.modules.MODULE_CHOICES",
        "CurrencyEnum": "apps.core.money.Currency",
        "ActionEnum": "apps.audit.actions.Action",
        "PlatformActionEnum": "apps.audit.actions.PlatformAction",
        "SchoolStatusEnum": "apps.schools.models.School.Status",
        "SchoolEnvironmentEnum": "apps.schools.models.School.Environment",
        "YearStatusEnum": "apps.schools.models.AcademicYear.Status",
        "EnrollmentStatusEnum": "apps.students.models.Enrollment.Status",
        "ConductGradeEnum": "apps.academics.models.ConductScale.Grade",
        "StudentImportStatusEnum": "apps.students.models.StudentImport.Status",
        "FeeCategoryEnum": "apps.finance.models.FeeType.Category",
        "DiscountKindEnum": "apps.finance.models.Discount.Kind",
        "TermKindEnum": "apps.schools.models.Term.Kind",
        "CreditStateEnum": "apps.finance.serializers.CREDIT_STATES",
        "CancellationStatusEnum": "apps.finance.models.CancellationRequest.Status",
        "PaymentOriginEnum": "apps.finance.models.Payment.Origin",
        "CreditOriginEnum": "apps.finance.models.StudentCredit.Origin",
        "PriorPaymentIssueEnum": "apps.finance.serializers.PRIOR_PAYMENT_ISSUES",
        "ClosingStateEnum": "apps.finance.serializers.CLOSING_STATES",
        "HealthCheckEnum": "apps.core.health.CHECKS",
        "HealthStatusEnum": "apps.core.health.STATUSES",
        "DeviceKindEnum": "apps.sync.models.Device.Kind",
        "NotificationKindEnum": "apps.notifications.models.Notification.Kind",
        "EventKindEnum": "apps.notifications.models.SchoolEvent.Kind",
        "EventAudienceEnum": "apps.notifications.models.SchoolEvent.Audience",
        "SupportSessionStateEnum": "apps.accounts.support.SESSION_STATES",
        "AudienceEnum": "apps.notifications.models.Announcement.Audience",
        "PlatformAudienceEnum": "apps.notifications.models.PlatformAnnouncement.Audience",
    },
}

CELERY_BROKER_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TIMEZONE = TIME_ZONE
# Deux files, deux travailleurs (PERF.5a) : `celery` (rapide : notifications, purges, passage du
# planificateur) et `heavy` (lourde : PDF, import d'une liste, création et remise à zéro d'un espace
# de démonstration). Un travail lourd ne retarde jamais une tâche courte. Chaque tâche est routée
# ici, nommément : un test refuse une tâche sans route ni limites de temps.
FAST_QUEUE, HEAVY_QUEUE = "celery", "heavy"
CELERY_TASK_DEFAULT_QUEUE = FAST_QUEUE
CELERY_TASK_ROUTES = {
    "apps.core.tasks.render_print_job": {"queue": HEAVY_QUEUE},
    "apps.students.tasks.run_student_import": {"queue": HEAVY_QUEUE},
    "apps.schools.tasks.delete_space": {"queue": HEAVY_QUEUE},
    "apps.schools.tasks.fill_demonstration": {"queue": HEAVY_QUEUE},
    "apps.notifications.tasks.deliver": {"queue": FAST_QUEUE},
    "apps.notifications.tasks.alert_console": {"queue": FAST_QUEUE},
    "apps.notifications.tasks.tick": {"queue": FAST_QUEUE},
    "apps.notifications.tasks.purge": {"queue": FAST_QUEUE},
    "apps.core.tasks.purge_print_jobs": {"queue": FAST_QUEUE},
    "apps.sync.tasks.purge": {"queue": FAST_QUEUE},
}
# Filet de sécurité pour une tâche future qui oublierait ses limites (secondes) ; chaque tâche
# d'aujourd'hui a les siennes, dans son décorateur.
CELERY_TASK_SOFT_TIME_LIMIT = 120
CELERY_TASK_TIME_LIMIT = 150
# Un travailleur à la fois sur un message : jamais de tâches mises de côté pendant qu'une longue
# tourne (un travailleur plante en route : la prochaine demande reprend à zéro).
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# Pas de stockage des résultats (`CELERY_RESULT_BACKEND = None`) : rien à faire expirer dans Redis.
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Planificateur (beat), un service à part (`scheduler`) : il ne meurt plus avec un travailleur.
# Les heures propres à chaque école (relances, clôture) sont décidées dans le passage, pas ici
# (`notifications/scheduled.py`).
CELERY_BEAT_SCHEDULE = {
    "notifications-tick": {
        "task": "apps.notifications.tasks.tick",
        "schedule": crontab(minute="*/15"),
        "options": {"expires": 10 * 60},
    },
    "notifications-purge": {
        "task": "apps.notifications.tasks.purge",
        "schedule": crontab(hour=3, minute=30),
    },
    "print-purge": {
        "task": "apps.core.tasks.purge_print_jobs",
        "schedule": crontab(hour=3, minute=50),
    },
    "sync-purge": {
        "task": "apps.sync.tasks.purge",
        "schedule": crontab(hour=3, minute=45),
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
    # Les messages de Django passent par la console ci-dessus : sans ce réglage, sa console à lui
    # (en DEBUG) les écrirait une seconde fois.
    "loggers": {"django": {"handlers": []}},
}
