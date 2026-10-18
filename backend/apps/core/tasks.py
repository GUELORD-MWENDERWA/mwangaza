"""Tâches de fond du socle : impression des documents lourds (PERF.1) sur la file `heavy`, lue
par un travailleur à part (un seul travail à la fois, mémoire et durée plafonnées) ; e-mail et
purge des demandes de démonstration (WEB.1d)."""

from celery import shared_task

from apps.core import demo_requests, printing


# `acks_late` : le message n'est rendu qu'une fois le PDF fait ; relancé, il ne refait rien
# (`printing.run` ne reprend qu'un travail encore « en attente »).
@shared_task(ignore_result=True, acks_late=True, soft_time_limit=420, time_limit=480)
def render_print_job(job_id: str) -> None:
    printing.run(job_id)


@shared_task(ignore_result=True, soft_time_limit=300, time_limit=360)
def purge_print_jobs() -> None:
    printing.purge()


# Serveur d'envoi injoignable ou refus passager (`SMTPException` est une `OSError`) : 3 essais.
@shared_task(
    ignore_result=True,
    autoretry_for=(OSError,),
    retry_backoff=60,
    max_retries=3,
    soft_time_limit=60,
    time_limit=90,
)
def email_demo_request(request_id: str) -> None:
    demo_requests.send_email(request_id)


@shared_task(ignore_result=True, soft_time_limit=120, time_limit=150)
def purge_demo_requests() -> None:
    demo_requests.purge()
