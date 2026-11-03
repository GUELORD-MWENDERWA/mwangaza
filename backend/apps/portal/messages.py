"""Fil de l'enfant avec l'école sur le Portail (8.8) : le parent lit les messages et écrit (demande
de dérogation, question sur une note ou une décision). Même accès que le reste du Portail :
l'enfant d'une famille reliée au compte, sinon 404."""

from apps.accounts.models import User
from apps.notifications import threads
from apps.notifications.models import Message, Thread
from apps.portal import children


def read(user: User, student_id) -> dict:
    """Messages du fil (vide avant le premier) et s'il y a une réponse non lue."""
    student = children.find_student(user, student_id)
    with children.in_school(student.school):
        thread = Thread.objects.filter(student=student).first()
        messages = list(thread.messages.select_related("author")) if thread else []
        return {
            "id": student.pk,
            "messages": messages,
            "unread": bool(thread and threads.parent_has_unread(thread)),
        }


def write(user: User, student_id, *, body: str, topic: str) -> Message:
    student = children.find_student(user, student_id)
    with children.in_school(student.school):
        return threads.write_as_parent(student, author=user, body=body, topic=topic)


def mark_read(user: User, student_id) -> None:
    student = children.find_student(user, student_id)
    with children.in_school(student.school):
        thread = Thread.objects.filter(student=student).first()
        if thread:
            threads.mark_read(thread, school=False)
