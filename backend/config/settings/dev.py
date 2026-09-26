"""Développement local : sous-domaines `{code}.localhost`, API derrière le proxy Vite."""

from .base import *  # noqa: F403
from .base import env, env_bool

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-uniquement-ne-pas-utiliser-en-production")
ALLOWED_HOSTS = [".localhost", "localhost", "127.0.0.1"]
SCHOOL_BASE_DOMAINS = ["localhost"]

# Sans Redis, les tâches Celery s'exécutent tout de suite dans le processus Django.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)

# Après « Log in » de l'API navigable (`/api/auth/login/`, développement seulement) : le compte
# connecté et ses droits, au lieu de la page de profil de Django qui n'existe pas.
LOGIN_REDIRECT_URL = "/api/me/"
