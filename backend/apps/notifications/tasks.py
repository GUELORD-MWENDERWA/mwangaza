"""Tâches de fond des notifications : envoi sur l'écran (5.5)."""

from celery import shared_task

from apps.notifications import push


@shared_task(ignore_result=True)
def deliver(notification_ids: list[str]) -> None:
    push.deliver(notification_ids)
