"""Documents lourds en tâche de fond (PERF.1, `docs/claude/recherches/perf-impression-capacite-…`).

Un bulletin coûte ≈ 1,9 s de processeur et 13 Mo : 35 bulletins faits dans la requête web
bloquaient un des travailleurs du site pendant une à trois minutes et montaient à 700 Mo, assez pour
saturer un serveur de 2 Go. Garde-fous :

- au-delà de `INLINE_MAX_PAGES` pages, la requête ne fait que déposer le document (`submit`) ; un
  travailleur Celery à part (file `print`, un seul travail à la fois, mémoire et durée plafonnées)
  le met en PDF par paquets de `CHUNK_PAGES` pages réunis avec pypdf : ≈ 350 Mo au plus (mesuré :
  351 Mo pour 35 bulletins, au lieu de 700 Mo), quelle que soit la taille de la classe ;
- le navigateur n'a rien de nouveau à faire : la même adresse (`…?output=pdf`) répond une page
  d'attente qui se recharge seule (`PrintJobMiddleware`), puis le PDF ; recharger ne relance rien ;
- peu de travaux en attente par école et au total, un travail qui traîne est abandonné, les fichiers
  sont effacés au bout d'un jour (`core.tasks.purge_print_jobs`).
"""

import gc
import hashlib
import io
import json
import logging
from contextvars import ContextVar
from datetime import timedelta

from celery.exceptions import SoftTimeLimitExceeded
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.models import PrintJob
from apps.core.tenancy import use_all_schools, use_school

logger = logging.getLogger(__name__)

INLINE_MAX_PAGES = 3  # au-delà : en tâche de fond (≈ 6 s de calcul pour 3 bulletins)
INLINE_MAX_BODY = 600_000  # caractères de HTML d'un document d'une seule pièce (lettres, listes)
CHUNK_PAGES = 8  # pages mises en page à la fois : ≈ 220 Mo + 8 fois 13 Mo
MAX_PAGES = 200
MAX_SOURCE = 25_000_000  # caractères de HTML au total
REUSE = timedelta(minutes=10)  # un document prêt est rendu tel quel pendant ce temps
STALE_RUNNING = timedelta(minutes=10)
STALE_QUEUED = timedelta(minutes=30)
KEEP = timedelta(days=1)
MAX_PENDING_PER_SCHOOL = 3
MAX_PENDING_TOTAL = 20
REFRESH_SECONDS = 3

_asked: ContextVar[tuple[str, str] | None] = ContextVar("print_job_asked", default=None)


def request_key(request) -> str | None:
    """Empreinte d'une demande de PDF d'une personne connectée dans une école ; sinon `None`
    (aperçu HTML, autre méthode, Portail…) : rien ne change pour ces demandes."""
    school = getattr(request, "school", None)
    user = getattr(request, "user", None)
    if (
        request.method != "GET"
        or request.GET.get("output") != "pdf"
        or school is None
        or user is None
        or not user.is_authenticated
    ):
        return None
    query = "&".join(f"{k}={v}" for k, v in sorted(request.GET.items()))
    raw = f"{user.pk}|{school.pk}|{request.path}|{query}"
    return hashlib.sha256(raw.encode()).hexdigest()


class PrintJobMiddleware:
    """Une demande de PDF déjà prise en charge n'atteint pas la vue : on répond depuis le travail
    (attente, PDF ou échec). Sinon la vue travaille, et `submit` crée le travail si le document est
    lourd. Placé après l'authentification et l'école de la requête."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        key = request_key(request)
        if key is None:
            return self.get_response(request)
        job = (
            PrintJob.objects.filter(
                created_by_id=request.user.pk, key=key, created_at__gte=timezone.now() - REUSE
            )
            .order_by("-created_at")
            .first()
        )
        if job is not None:
            return answer(job)
        token = _asked.set((key, str(request.user.pk)))
        try:
            return self.get_response(request)
        finally:
            _asked.reset(token)


def is_heavy(pages: int, body_size: int) -> bool:
    return _asked.get() is not None and (pages > INLINE_MAX_PAGES or body_size > INLINE_MAX_BODY)


def _page(state: str, title: str, message: str, status: int = 200, **extra) -> HttpResponse:
    context = {
        "state": state,
        "title": title,
        "message": message,
        "percent": 0,
        "pages": 0,
        "done": 0,
        **extra,
    }
    response = HttpResponse(render_to_string("core/print_wait.html", context), status=status)
    response["Cache-Control"] = "no-store"
    return response


def _pending(*, everyone: bool = False) -> int:
    queryset = PrintJob.all_schools if everyone else PrintJob.objects
    return queryset.filter(status__in=[PrintJob.Status.QUEUED, PrintJob.Status.RUNNING]).count()


def _forget(job: PrintJob) -> None:
    """Le travail et ses fichiers : une nouvelle demande repart de zéro."""
    job.source.delete(save=False)
    job.pdf.delete(save=False)
    job.delete()


def _failed_page(job: PrintJob) -> HttpResponse:
    message = job.error or _("The document could not be prepared.")
    _forget(job)
    return _page(
        "failed",
        _("The document could not be prepared"),
        message + " " + _("Reload this page to try again."),
        status=500,
    )


def answer(job: PrintJob) -> HttpResponse:
    """Ce que voit la personne qui demande le document de `job`."""
    now = timezone.now()
    Status = PrintJob.Status
    if job.status == Status.DONE:
        content = job.pdf.read() if job.pdf else b""
        job.pdf.close()
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{job.name}"'
        return response
    # Un travail abandonné (travailleur arrêté en route) ne bloque pas la demande suivante.
    stuck = job.status == Status.RUNNING and job.started_at and now - job.started_at > STALE_RUNNING
    if stuck or (job.status == Status.QUEUED and now - job.created_at > STALE_QUEUED):
        job.error = _("The document took too long to prepare.")
        job.status = Status.FAILED
    if job.status == Status.FAILED:
        return _failed_page(job)
    ahead = PrintJob.all_schools.filter(
        status__in=[Status.QUEUED, Status.RUNNING], created_at__lt=job.created_at
    ).count()
    percent = round(100 * job.pages_done / job.pages) if job.pages else 0
    return _page(
        "waiting",
        _("Your document is being prepared"),
        _("%(name)s will open as soon as it is ready.") % {"name": job.name},
        status=202,
        refresh=REFRESH_SECONDS,
        percent=percent,
        pages=job.pages,
        done=job.pages_done,
        ahead=ahead,
    )


def submit(head: str, bodies: list[str], name: str) -> HttpResponse:
    """Dépose le document (début du HTML avec ses polices, puis le corps de chaque page) et répond
    tout de suite ; refus lisible si l'école ou la plateforme a déjà trop de travaux en attente."""
    key, user_id = _asked.get()  # type: ignore[misc]  # `is_heavy` l'a vérifié
    if len(bodies) > MAX_PAGES or sum(map(len, bodies)) > MAX_SOURCE:
        return _page(
            "busy",
            _("Document too large"),
            _("Print this class in smaller parts (a few students at a time)."),
            status=413,
        )
    with use_all_schools():
        total = _pending(everyone=True)
    if _pending() >= MAX_PENDING_PER_SCHOOL or total >= MAX_PENDING_TOTAL:
        return _page(
            "busy",
            _("Too many documents in preparation"),
            _("Wait for the documents already requested to finish, then try again."),
            status=429,
        )
    job = PrintJob(key=key, name=name[:120], pages=len(bodies), created_by_id=user_id)
    job.source.save(
        "source.json",
        ContentFile(json.dumps({"head": head, "bodies": bodies}).encode()),
        save=False,
    )
    job.save()
    from apps.core.tasks import render_print_job

    # Requêtes hors transaction (`ATOMIC_REQUESTS` faux) : le travail est déjà écrit en base.
    render_print_job.delay(str(job.pk))
    # Sans tâche de fond (développement, tests : exécution immédiate), le PDF est déjà prêt.
    job.refresh_from_db()
    return answer(job)


def build_pdf(head: str, bodies: list[str], on_chunk=None) -> bytes:
    """Le PDF de toutes les pages, `CHUNK_PAGES` à la fois : la mise en page d'un paquet est
    libérée avant le suivant, les paquets sont réunis par pypdf (polices identiques regroupées)."""
    from pypdf import PdfReader, PdfWriter
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher

    writer = PdfWriter()
    for start in range(0, len(bodies), CHUNK_PAGES):
        chunk = bodies[start : start + CHUNK_PAGES]
        html = (
            head + "".join(f'<div class="next">{body}</div>' for body in chunk) + "</body></html>"
        )
        part = HTML(string=html, url_fetcher=URLFetcher(allowed_protocols=["data"])).write_pdf()
        writer.append(PdfReader(io.BytesIO(part)))
        del html, part
        gc.collect()
        if on_chunk:
            on_chunk(start + len(chunk))
    writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def run(job_id: str) -> None:
    """Tâche du travailleur d'impression : met le travail en PDF ; tout échec est noté sur le
    travail (la personne le voit), jamais perdu en silence."""
    with use_all_schools():
        found = PrintJob.all_schools.select_related("school").filter(pk=job_id).first()
    if found is None:
        return
    with use_school(found.school):
        job = PrintJob.objects.get(pk=job_id)
        if job.status != PrintJob.Status.QUEUED:
            return
        job.status, job.started_at = PrintJob.Status.RUNNING, timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])
        try:
            data = json.loads(job.source.read())
            job.source.close()

            def progress(done: int) -> None:
                PrintJob.objects.filter(pk=job.pk).update(pages_done=done)

            pdf = build_pdf(data["head"], data["bodies"], progress)
            job.pdf.save(job.name, ContentFile(pdf), save=False)
            job.status, job.pages_done = PrintJob.Status.DONE, job.pages
        except SoftTimeLimitExceeded:
            logger.error("Impression %s : délai dépassé", job_id)
            job.status = PrintJob.Status.FAILED
            job.error = _("The document took too long to prepare.")
        except Exception:
            logger.exception("Impression %s en échec", job_id)
            job.status = PrintJob.Status.FAILED
        finally:
            job.source.delete(save=False)
            job.finished_at = timezone.now()
            job.save()


def purge() -> int:
    """Effacer les travaux et leurs fichiers de plus d'un jour ; retourne leur nombre."""
    count = 0
    with use_all_schools():
        old = list(PrintJob.all_schools.filter(created_at__lt=timezone.now() - KEEP)[:500])
        for job in old:
            with use_school(job.school):
                _forget(job)
            count += 1
    return count
