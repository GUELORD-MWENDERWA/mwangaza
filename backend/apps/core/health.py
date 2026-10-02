"""Santé du serveur pour la console de la plateforme (5.2) : base de données, Redis (file des
tâches), tâches en arrière-plan (Celery) et place libre sur le disque des fichiers.

Chaque contrôle donne `status` (`ok`, `warning`, `error`, ou `off` : sans objet, ex. tâches
exécutées tout de suite en développement) et `value` (millisecondes, nombre de travailleurs,
pourcentage libre). Un contrôle en panne ne fait jamais échouer la page."""

import shutil
import time
from pathlib import Path

import redis
from django.conf import settings
from django.db import connection

# Sous ces pourcentages de place libre : avertissement, puis panne (plus de reçus ni de logos).
DISK_WARNING_PERCENT = 20
DISK_ERROR_PERCENT = 10
TIMEOUT_SECONDS = 1
CHECKS = ["database", "redis", "workers", "disk"]
STATUSES = ["ok", "warning", "error", "off"]


def _elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _database_latency() -> int:
    start = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return _elapsed_ms(start)


def _redis_latency() -> int:
    start = time.perf_counter()
    client = redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_connect_timeout=TIMEOUT_SECONDS,
        socket_timeout=TIMEOUT_SECONDS,
    )
    try:
        client.ping()
    finally:
        client.close()
    return _elapsed_ms(start)


def _workers() -> int:
    from config.celery import app

    return len(app.control.ping(timeout=TIMEOUT_SECONDS) or [])


def _disk_free_percent() -> int:
    media = Path(settings.MEDIA_ROOT)
    path = media if media.exists() else settings.BASE_DIR
    usage = shutil.disk_usage(path)
    return round(usage.free * 100 / usage.total)


def _check(name: str, measure, judge) -> dict:
    try:
        value = measure()
    except Exception:
        return {"name": name, "status": "error", "value": None}
    return {"name": name, "status": judge(value), "value": value}


def _ok(_value) -> str:
    return "ok"


def _disk(free: int) -> str:
    if free < DISK_ERROR_PERCENT:
        return "error"
    return "warning" if free < DISK_WARNING_PERCENT else "ok"


def report() -> dict:
    checks = [
        _check("database", _database_latency, _ok),
        _check("redis", _redis_latency, _ok),
    ]
    if settings.CELERY_TASK_ALWAYS_EAGER:
        checks.append({"name": "workers", "status": "off", "value": None})
    else:
        checks.append(_check("workers", _workers, lambda count: "ok" if count else "error"))
    checks.append(_check("disk", _disk_free_percent, _disk))
    statuses = {check["status"] for check in checks}
    status = next((s for s in ("error", "warning") if s in statuses), "ok")
    return {"status": status, "checks": checks}
