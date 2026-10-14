"""Droits sensibles (S.3.1) : ceux qui gèrent les rôles d'une école sont prévenus quand un compte
y reçoit le droit de gérer les rôles ou un droit sur l'argent. Rien ne sort de l'école."""

import pytest
from django.utils import translation

from apps.accounts import services
from apps.accounts.roles import PERMISSIONS
from apps.core.tenancy import use_all_schools, use_school
from apps.notifications import push
from apps.notifications.models import Notification
from tests.factories import MembershipFactory, starter_role

pytestmark = pytest.mark.django_db

Kind = Notification.Kind


def alerts() -> list[Notification]:
    with use_all_schools():
        sent = Notification.all_schools.filter(kind=Kind.SENSITIVE_RIGHTS)
        return list(sent.order_by("created_at", "id"))


def right(code: str, reader) -> str:
    with translation.override(reader.language):
        return str(PERMISSIONS[code])


def test_a_sensitive_right_alerts_the_role_managers_of_that_school_only(school, head, other_head):
    teacher = MembershipFactory(school=school, roles=["teacher"])

    with use_school(school):
        # Un rôle sans droit sur les rôles ni sur l'argent : rien.
        services.add_staff_member(
            actor=head,
            phone="0990000001",
            roles=[starter_role(school, "teacher")],
            last_name="Kasereka",
        )
        assert alerts() == []
        # La caisse donnée à un enseignant : le directeur le voit, même s'il en est l'auteur
        # (son compte a pu être pris par quelqu'un d'autre).
        services.update_staff_member(teacher, actor=head, roles=[starter_role(school, "cashier")])
        [alert] = alerts()
        # Désactivé puis réactivé : il retrouve ses droits, l'alerte repart.
        services.update_staff_member(teacher, actor=head, is_active=False)
        services.update_staff_member(teacher, actor=head, is_active=True)
        # Nommé directeur : l'intéressé, qui gère maintenant les rôles, n'est pas prévenu de
        # ses propres droits.
        services.update_staff_member(teacher, actor=head, roles=[starter_role(school, "head")])

    assert (alert.user, alert.school, alert.app, alert.url) == (head, school, "gestion", "/staff")
    assert str(teacher.user) in alert.title
    assert right("finance.collect_payment", head) in alert.body
    assert str(head) in alert.body
    assert [(sent.user, sent.school) for sent in alerts()] == [(head, school)] * 3
    # Alerte de sécurité : celui qui gère les rôles ne peut pas la couper.
    assert Kind.SENSITIVE_RIGHTS not in push.offered_kinds("gestion", {"roles.manage"})


def test_a_role_given_a_sensitive_right_alerts_once_and_never_names_the_support(
    school, other_school, head, other_head, platform_admin
):
    for _ in range(2):
        MembershipFactory(school=school, roles=["teacher"])
    MembershipFactory(school=other_school, roles=["teacher"])
    role = starter_role(school, "teacher")

    with use_school(school):
        # Renommé, ou élargi d'un droit ordinaire : rien.
        services.update_role(
            role,
            actor=platform_admin,
            name="Enseignant principal",
            permissions=[*role.permissions, "announcements.publish"],
        )
        assert alerts() == []
        services.update_role(
            role, actor=platform_admin, permissions=[*role.permissions, "finance.grant_discount"]
        )

    [alert] = alerts()
    assert (alert.user, alert.school, alert.url) == (head, school, "/roles")
    assert "Enseignant principal" in alert.title
    assert right("finance.grant_discount", head) in alert.body
    assert "2" in alert.body
    assert "Support" in alert.body
    assert str(platform_admin) not in alert.body
