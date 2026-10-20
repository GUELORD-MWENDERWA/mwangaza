"""Planificateur léger (PERF.8) : `celery -A beat beat`.

Il ne fait que poser, à l'heure dite, le nom de chaque tâche dans Redis ; les travailleurs, eux,
chargent Django. Sans Django (`fixups=[]`), il pèse ≈ 35 Mo au lieu de ≈ 107 Mo, et son conteneur
n'a besoin que de l'adresse de Redis : ni mot de passe de la base, ni clé secrète.
"""

import os

from celery import Celery

from task_schedule import BEAT_SCHEDULE, TASK_ROUTES, TIME_ZONE

app = Celery("mwangaza", fixups=[])
app.conf.update(
    broker_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    broker_connection_retry_on_startup=True,
    timezone=TIME_ZONE,
    task_routes=TASK_ROUTES,
    beat_schedule=BEAT_SCHEDULE,
)
