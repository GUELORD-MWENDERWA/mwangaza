"""Calcul automatique d'un brouillon (EDT.3a, spec emploi du temps § 7) : demande, exécution dans
la file `heavy`, résultat dans un **nouveau** brouillon (le brouillon de départ ne change pas :
revenir en arrière, c'est le rouvrir).

Serveur partagé : le travailleur `heavy` n'a qu'un fil (un calcul à la fois pour la plateforme,
sans verrou de plus) ; une école n'a qu'un calcul en attente ou en cours, la plateforme au plus
`MAX_ACTIVE_TOTAL` (les impressions passent par la même file). Annuler n'interrompt pas CP-SAT :
son temps est borné, et le résultat d'un calcul annulé n'est pas écrit."""

import logging
import resource
from datetime import timedelta

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone, translation
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.academics.courses import active_staff
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import use_all_schools, use_school
from apps.schools.models import AcademicYear, ClassGroup
from apps.timetable import checks, solver
from apps.timetable.constraints import _lock_school
from apps.timetable.drafts import NOT_A_DRAFT
from apps.timetable.models import Timetable, TimetableEntry, TimetableRun

logger = logging.getLogger(__name__)
Status, Scope = TimetableRun.Status, TimetableRun.Scope
ACTIVE = (Status.QUEUED, Status.RUNNING)
# Seconde résolution, qui nomme les règles qui bloquent.
EXPLAIN_SECONDS = 30
MAX_ACTIVE_TOTAL = 3
# Un calcul resté « en attente » ou « en cours » au-delà (travailleur arrêté) n'empêche plus d'en
# demander un autre.
STALE_AFTER = timedelta(minutes=30)
SHOWN = 10

RUN_IN_PROGRESS = ApiError(
    "run_in_progress", _("A calculation is already under way for this school."), 409
)
PLATFORM_BUSY = ApiError(
    "calculations_busy", _("Too many calculations are under way: try again in a few minutes."), 429
)
CHECKS_FAILED = ApiError(
    "checks_failed", _("Fix what the checks show in red before calculating."), 409
)
UNKNOWN_TARGET = ApiError(
    "unknown_target", _("Choose a class or a teacher of this school year."), 400
)
RUN_FINISHED = ApiError("run_finished", _("This calculation is already finished."), 409)


def runs(year: AcademicYear | None) -> QuerySet[TimetableRun]:
    """Les derniers calculs de l'année, le plus récent d'abord."""
    return TimetableRun.objects.filter(timetable__academic_year=year)[:SHOWN]


def _check_target(year: AcademicYear, scope: str, target) -> None:
    if scope == Scope.CLASS:
        found = ClassGroup.objects.filter(academic_year=year, pk=target).exists()
    elif scope == Scope.TEACHER:
        found = target is not None and active_staff().filter(pk=target).exists()
    else:
        found = True
    if not found:
        raise BusinessError(UNKNOWN_TARGET)


def request(
    *, timetable: Timetable, request_id, scope: str, target, time_limit: int, actor
) -> tuple[TimetableRun, bool]:
    """Demande un calcul (ou rend celui de cette demande) ; refusé si les contrôles ont du rouge,
    si l'école calcule déjà, ou si la plateforme a trop de calculs en cours."""
    found = TimetableRun.objects.filter(request_id=request_id).first()
    if found is not None:
        return found, False
    if timetable.status != Timetable.Status.DRAFT:
        raise BusinessError(NOT_A_DRAFT)
    year = timetable.academic_year
    _check_target(year, scope, target)
    with transaction.atomic():
        _lock_school()
        found = TimetableRun.objects.filter(request_id=request_id).first()
        if found is not None:
            return found, False
        stale = timezone.now() - STALE_AFTER
        TimetableRun.objects.filter(status__in=ACTIVE, created_at__lt=stale).update(
            status=Status.ERROR, finished_at=timezone.now()
        )
        if TimetableRun.objects.filter(status__in=ACTIVE).exists():
            raise BusinessError(RUN_IN_PROGRESS)
        with use_all_schools():
            busy = TimetableRun.all_schools.filter(status__in=ACTIVE, created_at__gte=stale).count()
        if busy >= MAX_ACTIVE_TOTAL:
            raise BusinessError(PLATFORM_BUSY)
        errors = checks.run(year)["errors"]
        if errors:
            raise BusinessError(CHECKS_FAILED, errors=errors)
        run = TimetableRun.objects.create(
            request_id=request_id,
            timetable=timetable,
            scope=scope,
            target=target if scope != Scope.ALL else None,
            time_limit=time_limit,
            created_by=actor,
        )
    from apps.timetable.tasks import run_timetable

    # Sans tâche de fond (développement, tests : exécution immédiate), le calcul est déjà fait.
    run_timetable.delay(str(run.pk))
    run.refresh_from_db()
    return run, True


def cancel(run: TimetableRun) -> TimetableRun:
    with transaction.atomic():
        run = TimetableRun.objects.select_for_update().get(pk=run.pk)
        if run.status not in ACTIVE:
            raise BusinessError(RUN_FINISHED)
        run.status, run.finished_at = Status.CANCELLED, timezone.now()
        run.save(update_fields=["status", "finished_at", "updated_at"])
    return run


def execute(run_id: str) -> None:
    """Tâche de la file `heavy` : calcule, puis écrit le résultat (sauf calcul annulé ou brouillon
    supprimé entre-temps). Tout échec est noté sur le calcul, jamais perdu en silence."""
    with use_all_schools():
        found = TimetableRun.all_schools.select_related("school").filter(pk=run_id).first()
    if found is None:
        return
    with use_school(found.school), translation.override(settings.LANGUAGE_CODE):
        started = TimetableRun.objects.filter(pk=run_id, status=Status.QUEUED).update(
            status=Status.RUNNING, started_at=timezone.now()
        )
        if not started:
            return
        run = TimetableRun.objects.select_related("timetable__academic_year").get(pk=run_id)
        outcome, entries, problem = None, [], None
        try:
            ctx = checks.context(run.timetable.academic_year)
            entries = list(TimetableEntry.objects.filter(timetable=run.timetable))
            problem = solver.prepare(ctx, entries, run.scope, run.target)
            outcome = solver.solve(problem, run.time_limit, EXPLAIN_SECONDS)
        except SoftTimeLimitExceeded:
            outcome = solver.Outcome(solver.TIMEOUT)
        except Exception:
            logger.exception("Calcul de l'horaire %s en échec", run_id)
        _finish(run_id, outcome, entries, problem)


def _finish(run_id: str, outcome, entries: list[TimetableEntry], problem) -> None:
    with transaction.atomic():
        run = (
            TimetableRun.objects.select_for_update(of=("self",))
            .select_related("timetable", "created_by")
            .filter(pk=run_id)
            .first()
        )
        if run is None or run.status != Status.RUNNING:
            return
        run.finished_at = timezone.now()
        run.peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
        if outcome is None:
            run.status = Status.ERROR
        else:
            run.status = outcome.status
            run.duration_ms, run.score = outcome.duration_ms, outcome.score
            run.unmet, run.blocking = outcome.unmet, outcome.blocking
            if outcome.status == Status.DONE:
                run.result = _write(run, outcome, entries, problem.replaced if problem else set())
        run.save()
    logger.info(
        "Calcul de l'horaire %s : %s en %s ms, %s séances, pic %s Mo",
        run_id,
        run.status,
        run.duration_ms,
        problem.sessions if problem else 0,
        run.peak_mb,
    )


def _write(run: TimetableRun, outcome, entries: list[TimetableEntry], replaced: set) -> Timetable:
    """Nouveau brouillon : les séances qui restent, puis celles du calcul (journal)."""
    source, actor = run.timetable, run.created_by
    name = gettext("%(name)s (calculated)") % {"name": source.name}
    draft = Timetable.objects.create(
        academic_year_id=source.academic_year_id,
        name=name[:80],
        based_on=source,
        created_by=actor,
    )
    rows = [
        TimetableEntry(
            timetable=draft,
            course_id=entry.course_id,
            weekday=entry.weekday,
            first=entry.first,
            length=entry.length,
            room_id=entry.room_id,
            locked=entry.locked,
            created_by=actor,
        )
        for entry in entries
        if entry.pk not in replaced
    ]
    rows += [
        TimetableEntry(
            timetable=draft,
            course_id=row["course"],
            weekday=row["weekday"],
            first=row["first"],
            length=row["length"],
            room_id=row["room"],
            locked=row["locked"],
            created_by=actor,
        )
        for row in outcome.placements
    ]
    TimetableEntry.objects.bulk_create(rows)
    audit.record(
        Action.TIMETABLE_DRAFT_CREATED,
        draft,
        actor=actor,
        after={
            "name": draft.name,
            "based_on": source.name,
            "lessons": len(rows),
            "calculated": True,
        },
        label=draft.name,
    )
    return draft
