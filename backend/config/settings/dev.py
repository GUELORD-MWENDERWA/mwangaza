"""Développement local : sous-domaines `{code}.localhost`, API derrière le proxy Vite."""

from .base import *  # noqa: F403
from .base import env, env_bool

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-uniquement-ne-pas-utiliser-en-production")
ALLOWED_HOSTS = [".localhost", "localhost", "127.0.0.1"]
SCHOOL_BASE_DOMAINS = ["localhost"]
PORTAL_URL = "http://localhost:5174"
SCHOOL_URL = "http://{code}.localhost:5173"

# Sans Redis, les tâches Celery s'exécutent tout de suite dans le processus Django.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)

# Clés Web Push de développement seulement (la production a les siennes : `webpush_keys`).
WEBPUSH_VAPID_PUBLIC_KEY = env(
    "WEBPUSH_VAPID_PUBLIC_KEY",
    "BGUkI-Aa0SAgLYnp5ghOuN2F1ill_COXk5EIgho22bdTjgaJozERwRR6Ata0IiZS_MmlDdAsTIO0O7kBVQzRfP0",
)
WEBPUSH_VAPID_PRIVATE_KEY = env(
    "WEBPUSH_VAPID_PRIVATE_KEY", "0-sUEiFwSNpw_8cEGUnQ03QO11T8TMS45bY1ZPPGL_U"
)
