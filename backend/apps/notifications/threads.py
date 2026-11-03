"""Fil parent ↔ école (8.8) : le parent écrit depuis le Portail (demande de dérogation, question sur
une note ou une décision), le personnel qui communique avec les familles (`announcements.publish`)
répond depuis la Gestion. Un fil par élève ; chaque côté a sa date de lecture (`*_read_at`), le
« non lu » se calcule. Pas de pièce jointe, pas de temps réel (la messagerie complète : V1.7)."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Max, Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.core.errors import ApiError, BusinessError
from apps.notifications import events
from apps.notifications.models import Message, Thread
from apps.students.models import Student

EMPTY = ApiError("message_empty", _("Write your message first."), 400)
TOO_MANY = ApiError(
    "too_many_messages",
    _("You have written several messages in a row: please wait for the school to answer."),
    429,
)
# Un parent ne peut pas inonder l'école : au plus 5 messages par heure et par élève.
HOURLY_LIMIT = 5


def listing() -> QuerySet[Thread]:
    """Fils de l'école, le plus récent d'abord ; `unread` : le parent a écrit depuis la dernière
    lecture du personnel. Une requête."""
    parent = Q(messages__from_school=False)
    return (
        Thread.objects.select_related("student__family")
        .annotate(last_parent_at=Max("messages__created_at", filter=parent))
        .order_by("-last_message_at")
    )


def is_unread_by_school(thread: Thread) -> bool:
    last = getattr(thread, "last_parent_at", None)
    return bool(last and (thread.school_read_at is None or last > thread.school_read_at))


def parent_has_unread(thread: Thread) -> bool:
    """Une réponse de l'école arrivée après la dernière lecture du parent."""
    answers = thread.messages.filter(from_school=True)
    if thread.parent_read_at:
        answers = answers.filter(created_at__gt=thread.parent_read_at)
    return answers.exists()


def _post(
    thread: Thread, *, author: User, body: str, from_school: bool, topic: str = ""
) -> Message:
    body = body.strip()
    if not body:
        raise BusinessError(EMPTY)
    now = timezone.now()
    message = Message.objects.create(
        thread=thread, from_school=from_school, author=author, topic=topic, body=body
    )
    Thread.objects.filter(pk=thread.pk).update(last_message_at=now, updated_at=now)
    return message


def write_as_parent(student: Student, *, author: User, body: str, topic: str) -> Message:
    """Message du parent (créé le fil au premier) ; prévient le personnel."""
    with transaction.atomic():
        thread, _created = Thread.objects.select_for_update().get_or_create(
            student=student, defaults={"last_message_at": timezone.now()}
        )
        recent = thread.messages.filter(
            from_school=False, created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        if recent >= HOURLY_LIMIT:
            raise BusinessError(TOO_MANY)
        message = _post(thread, author=author, body=body, from_school=False, topic=topic)
        events.parent_message(thread, message)
    return message


def reply(thread: Thread, *, actor: User, body: str) -> Message:
    """Réponse de l'école ; prévient le parent."""
    with transaction.atomic():
        message = _post(thread, author=actor, body=body, from_school=True)
        events.school_reply(thread, message)
    return message


def mark_read(thread: Thread, *, school: bool) -> None:
    field = "school_read_at" if school else "parent_read_at"
    setattr(thread, field, timezone.now())
    thread.save(update_fields=[field])
