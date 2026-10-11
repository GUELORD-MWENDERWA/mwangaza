"""Tâches de fond des écoles : suppression d'un espace d'essai ou de démonstration (4.16),
remplissage et remise à zéro d'un espace de démonstration (4.17.2)."""

from celery import shared_task

from apps.schools import deletion, demonstrations


@shared_task(ignore_result=True)
def delete_space(school_id: str) -> None:
    """Remise à zéro demandée : l'espace est recréé à l'instant où sa ligne part, puis rempli
    par `fill_demonstration`."""
    deletion.run(school_id, then=demonstrations.recreation(school_id))


@shared_task(ignore_result=True)
def fill_demonstration(school_id: str) -> None:
    demonstrations.fill(school_id)
