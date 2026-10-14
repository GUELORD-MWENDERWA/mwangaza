"""Tâches de fond de la synchronisation : purge de chaque nuit (A.2, `CELERY_BEAT_SCHEDULE`)."""

from celery import shared_task

from apps.sync import operations


@shared_task(ignore_result=True)
def purge() -> None:
    operations.purge()
