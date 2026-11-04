"""Demandes d'aide à la plateforme (SUP.1) : un membre du personnel écrit, la plateforme répond
dans la console, un fil de messages simples (texte, jamais de HTML), sans pièce jointe.

États : `open` (la plateforme doit répondre), `answered` (c'est à l'école), `closed`. Une demande
fermée depuis moins de 30 jours se rouvre en y répondant. Côté école, chacun ne voit que **ses**
demandes ; côté console, selon le mode (réel / démonstration)."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import OperationalError, connection, transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from apps.accounts import platform_roles as team
from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.core.errors import ApiError, BusinessError
from apps.core.models import PlatformSettings
from apps.core.tenancy import use_all_schools
from apps.notifications import push
from apps.notifications.models import SupportReply, SupportRequest

logger = logging.getLogger(__name__)
Status = SupportRequest.Status

DAILY_LIMIT = 10
REOPEN_DAYS = 30
CONSOLE_PAGE = "/support"

TOO_MANY = ApiError(
    "support_limit",
    gettext_lazy("You have already sent 10 help requests today. Try again tomorrow."),
    429,
)
CLOSED_FOR_GOOD = ApiError(
    "support_closed",
    gettext_lazy("This request has been closed for more than 30 days: write a new one."),
    409,
)
NOT_ASSIGNABLE = ApiError(
    "support_assignee", gettext_lazy("This person cannot handle help requests."), 400
)


def mine(user: User):
    """Demandes de ce compte dans l'école courante, activité la plus récente d'abord."""
    return SupportRequest.objects.filter(created_by=user).order_by("-last_activity_at", "-number")


def with_thread(queryset):
    return queryset.select_related("created_by", "assignee").prefetch_related("replies__author")


def _next_number() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('support_request_number')")
        return cursor.fetchone()[0]


@transaction.atomic
def open_request(
    school,
    *,
    user: User,
    subject: str,
    body: str,
    screen: str = "",
    app_version: str = "",
    device: str = "",
) -> SupportRequest:
    """Nouvelle demande et son premier message ; 10 par compte et par jour."""
    since = timezone.now() - timedelta(days=1)
    if SupportRequest.objects.filter(created_by=user, created_at__gte=since).count() >= DAILY_LIMIT:
        raise BusinessError(TOO_MANY)
    request = SupportRequest.objects.create(
        school=school,
        number=_next_number(),
        subject=subject.strip(),
        screen=screen.strip(),
        app_version=app_version.strip(),
        device=device.strip(),
        phone=user.phone,
        created_by=user,
    )
    SupportReply.objects.create(
        school=school, request=request, author=user, from_platform=False, body=body.strip()
    )
    transaction.on_commit(lambda: _enqueue_email(str(request.pk)))
    return request


@transaction.atomic
def reply_as_school(request: SupportRequest, *, user: User, body: str) -> SupportReply:
    """L'auteur répond : la demande revient « à traiter » (rouverte si fermée depuis moins de
    30 jours)."""
    if request.status == Status.CLOSED:
        if request.closed_at and request.closed_at < timezone.now() - timedelta(days=REOPEN_DAYS):
            raise BusinessError(CLOSED_FOR_GOOD)
        request.closed_at = None
    request.status = Status.OPEN
    request.last_activity_at = timezone.now()
    request.save(update_fields=["status", "closed_at", "last_activity_at", "updated_at"])
    return SupportReply.objects.create(
        school=request.school, request=request, author=user, from_platform=False, body=body.strip()
    )


@transaction.atomic
def close_as_school(request: SupportRequest) -> SupportRequest:
    """L'auteur ferme sa demande (« C'est réglé »)."""
    return _close(request)


def _close(request: SupportRequest) -> SupportRequest:
    if request.status != Status.CLOSED:
        request.status = Status.CLOSED
        request.closed_at = request.last_activity_at = timezone.now()
        request.save(update_fields=["status", "closed_at", "last_activity_at", "updated_at"])
    return request


# --- Console --------------------------------------------------------------------------------


def queue(environments):
    """Demandes de ces types d'espaces, de toutes les écoles : à traiter d'abord (la plus
    ancienne en attente en tête), puis le reste par activité récente."""
    return SupportRequest.all_schools.filter(school__environment__in=environments).select_related(
        "school", "created_by", "assignee"
    )


def assignees():
    """Comptes actifs de l'équipe qui ont le droit de traiter les demandes."""
    return User.objects.filter(
        is_active=True,
        is_platform_admin=True,
        platform_roles__overlap=team.roles_with(team.SUPPORT_HANDLE),
    ).order_by("last_name", "first_name")


@transaction.atomic
def reply_as_platform(request: SupportRequest, *, actor: User, body: str) -> SupportReply:
    """La plateforme répond : « en attente de l'école », l'auteur est prévenu sur son écran."""
    request = SupportRequest.all_schools.select_for_update().get(pk=request.pk)
    reopened = request.status == Status.CLOSED
    request.status = Status.ANSWERED
    request.closed_at = None
    request.last_activity_at = timezone.now()
    if request.assignee_id is None:
        request.assignee = actor
    request.save(
        update_fields=["status", "closed_at", "last_activity_at", "assignee", "updated_at"]
    )
    reply = SupportReply.all_schools.create(
        school=request.school, request=request, author=actor, from_platform=True, body=body.strip()
    )
    audit.record_platform(
        PlatformAction.SUPPORT_REPLIED,
        request,
        actor=actor,
        after={"number": request.number, "school": request.school.code, "reopened": reopened},
    )
    author = request.created_by
    if author is not None and author.is_active:
        with translation.override(author.language):
            push.notify(
                [author],
                school=request.school,
                app=push.App.GESTION,
                kind=push.Kind.SUPPORT_REPLY,
                title=_("Reply to your help request n° %(number)s") % {"number": request.number},
                body=body,
                url=f"/help/requests/{request.pk}",
            )
    return reply


@transaction.atomic
def close_as_platform(request: SupportRequest, *, actor: User) -> SupportRequest:
    request = SupportRequest.all_schools.select_for_update().get(pk=request.pk)
    if request.status == Status.CLOSED:
        return request
    _close(request)
    audit.record_platform(
        PlatformAction.SUPPORT_CLOSED,
        request,
        actor=actor,
        after={"number": request.number, "school": request.school.code},
    )
    return request


@transaction.atomic
def assign(request: SupportRequest, *, actor: User, assignee: User | None) -> SupportRequest:
    if assignee is not None and not assignees().filter(pk=assignee.pk).exists():
        raise BusinessError(NOT_ASSIGNABLE)
    if request.assignee_id == (assignee.pk if assignee else None):
        return request
    request.assignee = assignee
    request.save(update_fields=["assignee", "updated_at"])
    audit.record_platform(
        PlatformAction.SUPPORT_ASSIGNED,
        request,
        actor=actor,
        after={"number": request.number, "assignee": assignee.get_full_name() if assignee else ""},
    )
    return request


# --- E-mail à la plateforme -------------------------------------------------------------------


def _enqueue_email(request_id: str) -> None:
    from apps.notifications.tasks import email_support_request

    try:
        email_support_request.delay(request_id)
    except OperationalError:
        logger.exception("E-mail de la demande d'aide non envoyé : file injoignable.")


def send_email(request_id: str) -> None:
    """E-mail à l'adresse de support de la plateforme (tâche Celery) ; sans boîte d'envoi, la
    demande reste dans la console."""
    platform = PlatformSettings.load()
    to = [platform.support_email] if platform.support_email else list(settings.ALERT_EMAILS)
    if not (settings.EMAIL_HOST and to):
        return
    # Tâche de fond, sans école courante : lecture de cette seule demande.
    with use_all_schools():
        request = (
            SupportRequest.all_schools.filter(pk=request_id)
            .select_related("school", "created_by")
            .first()
        )
        first = (
            SupportReply.all_schools.filter(request_id=request_id).order_by("created_at").first()
        )
    if request is None:
        return
    with translation.override(settings.LANGUAGE_CODE):
        subject = _("Help request n° %(number)s: %(subject)s") % {
            "number": request.number,
            "subject": request.subject,
        }
        author = request.created_by.get_full_name() if request.created_by else "—"
        lines = [
            (_("School"), f"{request.school.name} ({request.school.code})"),
            (_("From"), f"{author} {request.phone}".strip()),
            (_("Screen"), request.screen or "—"),
            (_("Message"), first.body if first else ""),
        ]
        body = "\n".join(f"{label} : {value}" for label, value in lines)
        address = settings.SCHOOL_URL.format(code="admin") + CONSOLE_PAGE
        body += "\n\n" + _("Answer in the console: %(address)s") % {"address": address}
    send_mail(subject, body, f"{platform.name} <{settings.EMAIL_HOST_USER}>", to)
