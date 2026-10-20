import gc
import os

from celery import Celery
from celery.signals import worker_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("mwangaza")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_init.connect
def freeze_loaded_objects(**kwargs) -> None:
    """Django et le code chargés, juste avant de créer les travailleurs (PERF.8) : ces objets
    sortent du ramasse-miettes, qui ne les touche plus, et restent partagés avec chaque
    travailleur au lieu d'être recopiés peu à peu dans sa mémoire."""
    gc.collect()
    gc.freeze()
