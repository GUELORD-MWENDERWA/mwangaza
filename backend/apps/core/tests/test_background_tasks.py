"""Tâches de fond et limites de débit (PERF.5a) : chaque tâche est dans la bonne file et a ses
limites de temps ; la recherche et les sorties lourdes sont limitées par compte."""

import pytest
from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle

from config.celery import app

QUEUES = {"celery", "heavy", "ai"}


def ours():
    app.loader.import_default_modules()
    return {n: t for n, t in app.tasks.items() if n.startswith("apps.")}


def test_every_task_is_routed_to_a_queue_and_has_its_own_time_limits():
    from django.conf import settings

    tasks = ours()
    assert tasks  # les tâches des applications sont bien trouvées
    for name, task in tasks.items():
        route = settings.CELERY_TASK_ROUTES.get(name)
        assert route and route["queue"] in QUEUES, f"{name} : pas de file"
        assert task.soft_time_limit and task.time_limit, f"{name} : pas de limites"
        assert task.soft_time_limit < task.time_limit, name


def test_heavy_work_never_shares_the_fast_queue():
    from django.conf import settings

    heavy = {n for n, r in settings.CELERY_TASK_ROUTES.items() if r["queue"] == "heavy"}
    assert heavy == {
        "apps.core.tasks.render_print_job",
        "apps.students.tasks.run_student_import",
        "apps.schools.tasks.delete_space",
        "apps.schools.tasks.fill_demonstration",
        "apps.timetable.tasks.run_timetable",
    }
    # Le travailleur lourd ne reprend jamais un message deux fois en route, sauf le PDF et le
    # calcul de l'horaire, qui ne refont rien s'ils sont déjà pris (`printing.run`, `runs.execute`),
    # et l'appel à l'IA (file `ai`, `services.execute` ne démarre qu'un appel « en attente »).
    assert sorted(n for n, t in ours().items() if t.acks_late) == [
        "apps.ai.tasks.run_call",
        "apps.core.tasks.render_print_job",
        "apps.timetable.tasks.run_timetable",
    ]


def test_light_scheduler_sends_known_tasks_to_their_queue_without_django():
    """Le planificateur (`beat.py`, PERF.8) ne charge pas Django : il pose des noms de tâches.
    Chacun doit exister chez les travailleurs et partir dans sa file."""
    import json
    import os
    import subprocess
    import sys

    from django.conf import settings

    code = (
        "import json, sys, beat\n"
        "beat.app.loader.import_default_modules()\n"
        "assert 'django.apps' not in sys.modules and 'django.conf' not in sys.modules\n"
        "r = beat.app.amqp.router\n"
        "print(json.dumps({e['task']: r.route({}, e['task'])['queue'].name\n"
        "      for e in beat.app.conf.beat_schedule.values()}))"
    )
    env = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    sent = json.loads(result.stdout)
    assert set(sent) == {e["task"] for e in settings.CELERY_BEAT_SCHEDULE.values()}
    tasks = ours()
    for name, queue in sent.items():
        assert name in tasks, f"{name} : tâche inconnue des travailleurs"
        assert queue == settings.CELERY_TASK_ROUTES[name]["queue"], name


@pytest.fixture
def clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_exports_and_search_are_throttled_per_account(api, school, head, clean_cache, monkeypatch):
    # DRF lit les débits une fois pour toutes : on les resserre pour le test.
    monkeypatch.setattr(
        SimpleRateThrottle, "THROTTLE_RATES", {"search": "3/min", "output": "2/min"}
    )
    client = api(head)
    codes = [client.get("/api/students/", search="a").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    # Une demande sans recherche n'est pas comptée.
    assert client.get("/api/students/").status_code == 200
    pdf = [client.get("/api/students/class-list/", output="pdf").status_code for _ in range(3)]
    assert pdf[:2] != [429, 429] and pdf[2] == 429


def test_password_hashing_waits_its_turn_and_keeps_the_argon2_format():
    import threading
    import time

    from django.contrib.auth.hashers import Argon2PasswordHasher

    from apps.core.hashers import SerialArgon2PasswordHasher

    hasher = SerialArgon2PasswordHasher()
    hasher.time_cost, hasher.memory_cost, hasher.parallelism = 1, 1024, 1
    encoded = hasher.encode("secret", "saltsaltsaltsalt")
    # Même format qu'Argon2 de Django : les mots de passe déjà enregistrés restent valables.
    assert encoded.startswith("argon2$") and Argon2PasswordHasher().verify("secret", encoded)

    running, peak, lock = 0, 0, threading.Lock()
    original = Argon2PasswordHasher.verify

    def slow(self, password, encoded):
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.05)
        with lock:
            running -= 1
        return original(self, password, encoded)

    Argon2PasswordHasher.verify = slow
    try:
        threads = [
            threading.Thread(target=hasher.verify, args=("secret", encoded)) for _ in range(4)
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]
    finally:
        Argon2PasswordHasher.verify = original
    assert peak == 1


def test_heavy_libraries_are_loaded_only_when_used():
    """Chaque processus (site, travailleurs) charge Django et le code de toutes les tâches au
    démarrage : une grosse bibliothèque importée en tête d'un module y pèse partout, toujours
    (PERF.8, `05` § 8.5). Elles se chargent dans la fonction qui s'en sert."""
    import os
    import subprocess
    import sys

    from django.conf import settings

    heavy = [
        "pywebpush",
        "aiohttp",
        "openpyxl",
        "segno",
        "pypdf",
        "weasyprint",
        "sentry_sdk",
        "ortools",
        "pandas",
        "anthropic",
    ]
    code = (
        "import sys, django; django.setup()\n"
        "from config.celery import app; app.loader.import_default_modules()\n"
        "import config.urls\n"
        f"print(' '.join(m for m in {heavy!r} if m in sys.modules))"
    )
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.test"}
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == []
