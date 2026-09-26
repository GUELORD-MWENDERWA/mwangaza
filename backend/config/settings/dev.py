"""Développement local : sous-domaines `{code}.localhost`, API derrière le proxy Vite."""

from .base import *  # noqa: F403
from .base import env, env_bool

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-uniquement-ne-pas-utiliser-en-production")
ALLOWED_HOSTS = [".localhost", "localhost", "127.0.0.1"]
SCHOOL_BASE_DOMAINS = ["localhost"]
SCHOOL_URL = "http://{code}.localhost:5173"

# Sans Redis, les tâches Celery s'exécutent tout de suite dans le processus Django.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)
