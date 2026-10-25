"""Files, routes et horaires des tâches de fond, sans Django (PERF.8).

Lu par les réglages de Django (`settings/base.py`) et par le planificateur léger
(`beat.py`), qui n'a besoin que de ces noms pour poser les tâches dans Redis : il ne
charge ni Django ni le code des écoles, et n'a ni accès à la base ni clé secrète.
"""

from celery.schedules import crontab

TIME_ZONE = "Africa/Lubumbashi"

# Deux files, deux travailleurs (PERF.5a) : `celery` (rapide : notifications, purges, passage du
# planificateur) et `heavy` (lourde : PDF, import d'une liste, création et remise à zéro d'un espace
# de démonstration). Un travail lourd ne retarde jamais une tâche courte. Chaque tâche est routée
# ici, nommément : un test refuse une tâche sans route ni limites de temps.
FAST_QUEUE, HEAVY_QUEUE, AI_QUEUE = "celery", "heavy", "ai"
TASK_ROUTES = {
    "apps.core.tasks.render_print_job": {"queue": HEAVY_QUEUE},
    "apps.students.tasks.run_student_import": {"queue": HEAVY_QUEUE},
    "apps.schools.tasks.delete_space": {"queue": HEAVY_QUEUE},
    "apps.schools.tasks.fill_demonstration": {"queue": HEAVY_QUEUE},
    "apps.timetable.tasks.run_timetable": {"queue": HEAVY_QUEUE},
    "apps.ai.tasks.run_call": {"queue": AI_QUEUE},
    "apps.ai.tasks.purge": {"queue": FAST_QUEUE},
    "apps.notifications.tasks.deliver": {"queue": FAST_QUEUE},
    "apps.notifications.tasks.alert_console": {"queue": FAST_QUEUE},
    "apps.notifications.tasks.tick": {"queue": FAST_QUEUE},
    "apps.notifications.tasks.purge": {"queue": FAST_QUEUE},
    "apps.core.tasks.purge_print_jobs": {"queue": FAST_QUEUE},
    "apps.core.tasks.email_demo_request": {"queue": FAST_QUEUE},
    "apps.core.tasks.purge_demo_requests": {"queue": FAST_QUEUE},
    "apps.sync.tasks.purge": {"queue": FAST_QUEUE},
}

# Les heures propres à chaque école (relances, clôture) sont décidées dans le passage, pas ici
# (`notifications/scheduled.py`). Une nouvelle entrée justifie sa fréquence : jamais plus d'un
# passage toutes les 15 minutes, et un travail de nuit regroupé avec les purges (`05` § 8.5).
BEAT_SCHEDULE = {
    "notifications-tick": {
        "task": "apps.notifications.tasks.tick",
        "schedule": crontab(minute="*/15"),
        "options": {"expires": 10 * 60},
    },
    "notifications-purge": {
        "task": "apps.notifications.tasks.purge",
        "schedule": crontab(hour=3, minute=30),
    },
    "print-purge": {
        "task": "apps.core.tasks.purge_print_jobs",
        "schedule": crontab(hour=3, minute=50),
    },
    "sync-purge": {
        "task": "apps.sync.tasks.purge",
        "schedule": crontab(hour=3, minute=45),
    },
    "ai-purge": {
        "task": "apps.ai.tasks.purge",
        "schedule": crontab(hour=4, minute=0),
    },
    "demo-requests-purge": {
        "task": "apps.core.tasks.purge_demo_requests",
        "schedule": crontab(hour=3, minute=55),
    },
}
