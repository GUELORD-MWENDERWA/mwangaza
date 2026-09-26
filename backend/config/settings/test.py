"""Tests : base PostgreSQL de test, tâches Celery synchrones, hachage rapide."""

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "tests-uniquement"
ALLOWED_HOSTS = [".localhost", "localhost", "testserver"]
CELERY_TASK_ALWAYS_EAGER = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
