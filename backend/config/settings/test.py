"""Tests : base PostgreSQL de test, tâches Celery synchrones, hachage rapide."""

from .base import *  # noqa: F403
from .base import INSTALLED_APPS

DEBUG = False
SECRET_KEY = "tests-uniquement"
ALLOWED_HOSTS = [".localhost", "localhost", "testserver"]
SCHOOL_BASE_DOMAINS = ["localhost"]
# Modèles d'école réservés aux tests du socle multi-écoles.
INSTALLED_APPS = [*INSTALLED_APPS, "tests.sample"]
CELERY_TASK_ALWAYS_EAGER = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
