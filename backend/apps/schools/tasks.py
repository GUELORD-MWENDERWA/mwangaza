"""Tâches de fond des écoles : suppression d'un espace d'essai ou de démonstration (4.16)."""

from celery import shared_task

from apps.schools import deletion


@shared_task(ignore_result=True)
def delete_space(school_id: str) -> None:
    deletion.run(school_id)
