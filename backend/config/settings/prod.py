"""Production : tout vient de l'environnement ; refuse de démarrer sans secret."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import SECRET_KEY, env, env_bool

if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY est obligatoire en production.")

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
# 0 pour l'essai de la production sur la machine (`make prod-local`) : sinon le navigateur
# imposerait HTTPS à itig.localhost, y compris au serveur de développement.
SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", str(60 * 60 * 24 * 30)))
# Caddy écrit l'adresse du visiteur dans X-Real-IP (`infra/Caddyfile`).
CLIENT_IP_HEADER = env("DJANGO_CLIENT_IP_HEADER", "HTTP_X_REAL_IP")
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# Seulement dans l'essai sur plusieurs appareils (`infra/docker-compose.reseau.yml`).
DEMO_DATA = env_bool("DJANGO_DEMO_DATA", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
