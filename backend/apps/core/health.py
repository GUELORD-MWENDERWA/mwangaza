"""Santé du serveur pour la console de la plateforme (5.2) : base de données, Redis (file des
tâches), tâches en arrière-plan (Celery) et place libre sur le disque des fichiers.

Chaque contrôle donne `status` (`ok`, `warning`, `error`, ou `off` : sans objet, ex. tâches
exécutées tout de suite en développement) et `value` (millisecondes, nombre de travailleurs,
pourcentage libre). Un contrôle en panne ne fait jamais échouer la page."""

import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import redis
from django.conf import settings
from django.db import connection

# Sous ces pourcentages de place libre : avertissement, puis panne (plus de reçus ni de logos).
DISK_WARNING_PERCENT = 20
DISK_ERROR_PERCENT = 10
TIMEOUT_SECONDS = 1
# Mémoire disponible (libre ou récupérable) et swap utilisé : la panne du 2026-10-13 venait de là.
MEMORY_WARNING_PERCENT = 15
MEMORY_ERROR_PERCENT = 7
SWAP_WARNING_PERCENT = 50
SWAP_ERROR_PERCENT = 80
# Le planificateur passe toutes les 15 minutes ; la sauvegarde, chaque nuit.
SCHEDULER_ERROR_AFTER = timedelta(minutes=35)
BACKUP_WARNING_AFTER = timedelta(hours=30)
BACKUP_ERROR_AFTER = timedelta(hours=54)
# Écrits dans Redis (volume persistant) : le passage du planificateur par `heartbeat`, la
# sauvegarde et sa copie hors du serveur par `infra/backup/sauvegarde.sh` (heure UNIX).
TICK_KEY = "mwangaza:scheduler:tick"
BACKUP_KEYS = {"done_at": "mwangaza:backup:done", "copied_at": "mwangaza:backup:copied"}
QUEUE_KEY = "celery"
CHECKS = ["database", "redis", "workers", "disk", "memory", "swap"]
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


def _meminfo() -> dict[str, int]:
    """/proc/meminfo en kio, sans dépendance."""
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        values[key] = int(rest.split()[0])
    return values


def _memory_free_percent() -> int:
    info = _meminfo()
    return round(info["MemAvailable"] * 100 / info["MemTotal"])


def _swap_used_percent() -> int:
    info = _meminfo()
    if not info["SwapTotal"]:
        return 0
    return round((info["SwapTotal"] - info["SwapFree"]) * 100 / info["SwapTotal"])


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


def _memory(free: int) -> str:
    if free < MEMORY_ERROR_PERCENT:
        return "error"
    return "warning" if free < MEMORY_WARNING_PERCENT else "ok"


def _swap(used: int) -> str:
    if used > SWAP_ERROR_PERCENT:
        return "error"
    return "warning" if used > SWAP_WARNING_PERCENT else "ok"


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
    checks.append(_check("memory", _memory_free_percent, _memory))
    checks.append(_check("swap", _swap_used_percent, _swap))
    statuses = {check["status"] for check in checks}
    status = next((s for s in ("error", "warning") if s in statuses), "ok")
    return {"status": status, "checks": checks}


def _redis():
    return redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_connect_timeout=TIMEOUT_SECONDS,
        socket_timeout=TIMEOUT_SECONDS,
        decode_responses=True,
    )


def heartbeat(now: datetime | None = None) -> None:
    """Passage du planificateur, noté en mémoire (une écriture Redis toutes les 15 minutes, rien
    en base). Ne fait jamais échouer le passage."""
    client = _redis()
    try:
        client.set(TICK_KEY, int((now or datetime.now(UTC)).timestamp()))
    except Exception:
        pass
    finally:
        client.close()


def _stamp(value: str | None) -> datetime | None:
    return datetime.fromtimestamp(int(value), UTC) if value else None


def _age_status(at: datetime | None, now: datetime, warning, error) -> str:
    """Jamais noté : `error` (on ne prétend jamais que c'est bon sans preuve)."""
    if at is None or now - at > error:
        return "error"
    return "warning" if warning and now - at > warning else "ok"


def platform(now: datetime | None = None) -> dict:
    """Planificateur (dernier passage, travaux en attente) et sauvegardes (dernière faite, dernière
    copie hors du serveur), lus dans Redis. Redis en panne : `error` partout, la page reste."""
    now = now or datetime.now(UTC)
    ticked, queue, backup = None, None, dict.fromkeys(BACKUP_KEYS)
    try:
        client = _redis()
        try:
            ticked = _stamp(client.get(TICK_KEY))
            queue = client.llen(QUEUE_KEY)
            backup = {name: _stamp(client.get(key)) for name, key in BACKUP_KEYS.items()}
        finally:
            client.close()
    except Exception:
        pass
    scheduler_status = (
        "off"
        if settings.CELERY_TASK_ALWAYS_EAGER
        else _age_status(ticked, now, None, SCHEDULER_ERROR_AFTER)
    )
    copied = backup["copied_at"]
    return {
        "scheduler": {"status": scheduler_status, "last_tick_at": ticked, "queue_size": queue},
        "backup": {
            "status": _age_status(backup["done_at"], now, BACKUP_WARNING_AFTER, BACKUP_ERROR_AFTER),
            "done_at": backup["done_at"],
            # Pas de copie notée : peut-être pas de bucket configuré, donc seulement « sans objet ».
            "copied_status": "off"
            if copied is None
            else _age_status(copied, now, BACKUP_WARNING_AFTER, BACKUP_ERROR_AFTER),
            "copied_at": copied,
        },
    }
