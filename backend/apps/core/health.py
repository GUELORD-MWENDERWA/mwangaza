"""Santé du serveur pour la console de la plateforme (5.2) : base de données, Redis (file des
tâches), tâches en arrière-plan (Celery) et place libre sur le disque des fichiers.

Chaque contrôle donne `status` (`ok`, `warning`, `error`, ou `off` : sans objet, ex. tâches
exécutées tout de suite en développement) et `value` (millisecondes, nombre de travailleurs,
pourcentage libre). Un contrôle en panne ne fait jamais échouer la page."""

import re
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
SWAP_WARNING_PERCENT = 60
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
# Mémoire de chaque conteneur (PERF.4) : un conteneur ne voit pas les autres, donc
# `infra/serveur/conteneurs.sh` (cron, toutes les 5 minutes) note `docker stats` dans Redis.
CONTAINERS_KEY = "mwangaza:containers"
# État (arrêt pour manque de mémoire, redémarrages, dernier démarrage), noté par le même cron.
CONTAINER_STATE_KEY = "mwangaza:containers:state"
# Au-dessus de 70 % de sa limite : attention ; au-dessus de 85 % : alerte (Docker l'arrêtera).
CONTAINER_WARNING_PERCENT = 70
CONTAINER_ERROR_PERCENT = 85
# Un redémarrage de moins de 24 heures se voit encore sur l'écran.
RESTART_VISIBLE = timedelta(hours=24)
# Ordre d'affichage : du plus visible par les écoles à ce qui les soutient.
SERVICE_ORDER = ["django", "worker", "worker-heavy", "scheduler", "db", "redis", "caddy"]
# Impression (PERF.1) : au-delà de 10 minutes d'attente, il faut une machine plus grosse (`03` § 9).
PRINT_WAIT_WARNING = timedelta(minutes=10)
UNITS = {"b": 1 / 1024**2, "kib": 1 / 1024, "kb": 1 / 1000, "mib": 1, "mb": 1}
UNITS |= {"gib": 1024, "gb": 1000}
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


def _megabytes(text: str) -> float:
    number, unit = re.fullmatch(r"([\d.]+)\s*([A-Za-z]+)", text.strip()).groups()
    return float(number) * UNITS[unit.lower()]


def _service(name: str) -> str:
    """Nom Docker (`mwangaza-worker-heavy-1`) → nom du service (`worker-heavy`)."""
    return re.sub(r"^mwangaza(?:-dev)?-|-\d+$", "", name.strip().lstrip("/"))


def _states(raw: str | None, now: datetime) -> dict[str, dict]:
    """Lignes `nom;OOMKilled;redémarrages;démarré à` (`docker inspect`) → par service : l'heure
    du dernier démarrage si le conteneur a redémarré depuis moins de 24 h, et s'il a été arrêté
    faute de mémoire. (`OOMKilled` retombe à faux au redémarrage : on lit aussi le compteur.)"""
    states = {}
    for line in (raw or "").splitlines():
        try:
            name, oom, restarts, started = line.split(";")
            at = datetime.fromisoformat(started[:19]).replace(tzinfo=UTC)
            restarted = int(restarts) > 0 and now - at < RESTART_VISIBLE
        except (ValueError, TypeError):
            continue
        oom_killed = oom.strip().lower() == "true"
        states[_service(name)] = {
            "oom_killed": oom_killed,
            "restarted_at": at if (restarted or oom_killed) else None,
        }
    return states


def _containers(raw: str | None, states_raw: str | None = None, now: datetime | None = None):
    """Lignes `nom;utilisé / limite` (`docker stats`) → mémoire en Mo et en %, dans l'ordre de
    `SERVICE_ORDER` (les inconnus à la fin), avec l'état de `_states`. Ligne illisible ignorée."""
    states = _states(states_raw, now or datetime.now(UTC))
    rows = []
    for line in (raw or "").splitlines():
        try:
            name, _, usage = line.partition(";")
            used, limit = (_megabytes(part) for part in usage.split("/"))
        except (ValueError, AttributeError, KeyError):
            continue
        service = _service(name)
        percent = round(used * 100 / limit) if limit else 0
        state = states.get(service, {"oom_killed": False, "restarted_at": None})
        status = "ok"
        if percent > CONTAINER_ERROR_PERCENT or state["oom_killed"]:
            status = "error"
        elif percent > CONTAINER_WARNING_PERCENT:
            status = "warning"
        rows.append(
            {
                "name": service,
                "used_mb": round(used),
                "limit_mb": round(limit),
                "percent": percent,
                "status": status,
                **state,
            }
        )
    rank = {name: index for index, name in enumerate(SERVICE_ORDER)}
    return sorted(rows, key=lambda row: (rank.get(row["name"], len(rank)), row["name"]))


def print_queue(now: datetime) -> dict:
    """Travaux d'impression en attente ou en cours, toutes écoles confondues, et la plus longue
    attente (du dépôt au début du travail, ou jusqu'à maintenant s'il attend encore)."""
    from apps.core.models import PrintJob

    status = PrintJob.Status
    waiting = PrintJob.all_schools.filter(status__in=[status.QUEUED, status.RUNNING])
    pending = waiting.filter(status=status.QUEUED)
    oldest = pending.order_by("created_at").values_list("created_at", flat=True).first()
    longest = round((now - oldest).total_seconds()) if oldest else 0
    late = longest > PRINT_WAIT_WARNING.total_seconds()
    return {
        "status": "warning" if late else "ok",
        "queued": pending.count(),
        "running": waiting.filter(status=status.RUNNING).count(),
        "longest_wait_seconds": longest,
    }


def platform(now: datetime | None = None) -> dict:
    """Planificateur (dernier passage, travaux en attente) et sauvegardes (dernière faite, dernière
    copie hors du serveur), lus dans Redis. Redis en panne : `error` partout, la page reste."""
    now = now or datetime.now(UTC)
    ticked, queue, backup = None, None, dict.fromkeys(BACKUP_KEYS)
    containers = states = None
    try:
        client = _redis()
        try:
            ticked = _stamp(client.get(TICK_KEY))
            queue = client.llen(QUEUE_KEY)
            containers = client.get(CONTAINERS_KEY)
            states = client.get(CONTAINER_STATE_KEY)
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
        "containers": _containers(containers, states, now),
        "print": print_queue(now),
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
