"""Tâches de fond et limites de débit (PERF.5a) : chaque tâche est dans la bonne file et a ses
limites de temps ; la recherche et les sorties lourdes sont limitées par compte."""

import pytest
from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle

from config.celery import app

QUEUES = {"celery", "heavy"}


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
    }
    # Le travailleur lourd ne reprend jamais un message deux fois en route, sauf le PDF, qui
    # ne refait rien s'il est déjà pris (`printing.run`).
    assert [n for n, t in ours().items() if t.acks_late] == ["apps.core.tasks.render_print_job"]


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
