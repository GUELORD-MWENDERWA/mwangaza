"""Tâches de fond du socle : impression des documents lourds (PERF.1) sur la file `print`, lue
par un travailleur à part (un seul travail à la fois, mémoire et durée plafonnées)."""

from celery import shared_task

from apps.core import printing


@shared_task(ignore_result=True, soft_time_limit=420, time_limit=480)
def render_print_job(job_id: str) -> None:
    printing.run(job_id)


@shared_task(ignore_result=True)
def purge_print_jobs() -> None:
    printing.purge()
