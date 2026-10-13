"""Notifications du parent sur le portail (5.5.2) : son centre de notifications, toutes écoles
mêlées, et la notification d'essai.

Une notification appartient à un compte dans une école : le parent lit celles des écoles où une de
ses familles a encore accès (accès suspendu par l'école ou école fermée : rien, comme les
annonces). L'abonnement du navigateur et les préférences sont ceux de `notifications.push`, sans
école : le portail n'a qu'une adresse."""

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.core.errors import ApiError, BusinessError
from apps.notifications import push
from apps.notifications.models import Notification
from apps.schools.models import School
from apps.students.models import Family

APP = Notification.App.PORTAIL

NO_SCHOOL = ApiError("no_school", _("No school is linked to this account."), 409)


def schools(user: User) -> QuerySet[School]:
    """Écoles où une famille du compte a accès au portail."""
    families = Family.all_schools.filter(primary_user=user, portal_suspended_at__isnull=True)
    return School.objects.filter(pk__in=families.values("school")).exclude(School.portal_closed())


def inbox(user: User) -> QuerySet[Notification]:
    return Notification.all_schools.filter(
        user=user, app=APP, school__in=schools(user)
    ).select_related("school")


def mark_read(user: User, ids: list | None) -> None:
    """Toutes (`ids` vide ou absent) ou celles données ; celles d'un autre compte ou d'une école
    fermée au compte sont ignorées."""
    unread = inbox(user).filter(read_at__isnull=True)
    if ids:
        unread = unread.filter(pk__in=ids)
    unread.update(read_at=timezone.now())


def send_test(user: User) -> Notification:
    """Notification d'essai, envoyée sur les écrans abonnés du compte ; rangée dans une de ses
    écoles (une notification a toujours une école)."""
    school = schools(user).order_by("name", "pk").first()
    if school is None:
        raise BusinessError(NO_SCHOOL)
    [notification] = push.notify(
        [user],
        school=school,
        app=APP,
        kind=Notification.Kind.TEST,
        title=_("Notifications are working"),
        body=_("News from your children's schools will appear here, even with the app closed."),
        url="/notifications",
    )
    return notification
