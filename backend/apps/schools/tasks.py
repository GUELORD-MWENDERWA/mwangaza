"""Tâches de fond des écoles : suppression d'un espace d'essai ou de démonstration (4.16),
remplissage et remise à zéro d'un espace de démonstration (4.17.2)."""

from celery import shared_task

from apps.schools import deletion, demonstrations


# Limites (secondes, PERF.5a) : une démonstration complète se crée en moins d'une minute.
@shared_task(ignore_result=True, soft_time_limit=540, time_limit=600)
def delete_space(school_id: str) -> None:
    """Remise à zéro demandée : l'espace est recréé à l'instant où sa ligne part, puis rempli
    par `fill_demonstration`."""
    deletion.run(school_id, then=demonstrations.recreation(school_id))


@shared_task(ignore_result=True, soft_time_limit=540, time_limit=600)
def fill_demonstration(school_id: str) -> None:
    demonstrations.fill(school_id)
