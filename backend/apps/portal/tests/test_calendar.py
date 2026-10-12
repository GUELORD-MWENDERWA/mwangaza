"""Calendrier du portail (5.7) : événements pour tous des écoles des enfants, convocations de ses
enfants seulement (vues, annulées), annonce au personnel jamais montrée à une famille, titulaire
de la classe (téléphone seulement si l'école l'a choisi)."""

from datetime import timedelta

from django.utils import timezone

from apps.core.tenancy import use_school
from apps.notifications import communication
from apps.notifications import services as announcements
from apps.notifications.models import Notification, Summons
from apps.portal.tests.test_access import activate, portal, post
from apps.students.models import Family
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

CALENDAR = "/api/portal/calendar/"
SUMMONS = "/api/portal/summons/"


def plan(school, actor, title, days, **fields):
    day = timezone.localdate() + timedelta(days=days)
    with use_school(school):
        return communication.save_event(actor=actor, title=title, starts_on=day, **fields)


def summon(school, actor, student):
    with use_school(school):
        return communication.issue_summons(
            actor=actor,
            student=student,
            reason="Résultats de la première période.",
            meeting_at=timezone.now() + timedelta(days=2),
            meet_with="Préfet des études",
        )


def test_a_parent_sees_the_events_for_everyone_and_the_summons_of_its_children_only(
    school, other_school, head, other_head, alpha, beta
):
    child = enrolled(school, head, alpha["group"])
    neighbour = enrolled(school, head, alpha["group"], last_name="Amani")
    stranger = enrolled(other_school, other_head, beta["group"])
    client = portal()
    with use_school(school):
        activate(client, child.family.code)
        parent = Family.objects.get(pk=child.family_id).primary_user
        announcements.publish(actor=head, title="Conseil", body="Vendredi.", audience="staff")

    plan(school, head, "Réunion des parents", 5)
    plan(school, head, "Conseil des enseignants", 3, audience="staff")
    plan(school, head, "Journée sportive", -2)
    plan(other_school, other_head, "Portes ouvertes", 4)
    mine = summon(school, head, child)
    others = [summon(school, head, neighbour), summon(other_school, other_head, stranger)]

    events = client.get(CALENDAR).json()["results"]
    assert [(e["title"], e["school_name"]) for e in events] == [
        ("Réunion des parents", school.name)
    ]
    # L'annonce au personnel n'existe pas pour une famille.
    assert client.get("/api/portal/announcements/").json()["count"] == 0

    [summons] = client.get(SUMMONS).json()["results"]
    assert (summons["id"], summons["student_name"], summons["seen"]) == (
        str(mine.pk),
        child.full_name,
        False,
    )
    with use_school(school):
        notified = Notification.objects.filter(kind=Notification.Kind.SUMMONS)
        assert [(n.user, n.app, n.url) for n in notified] == [(parent, "portail", "/calendar")]

    # « Vue » : seulement la sienne, même en donnant celles des autres.
    ids = [str(mine.pk), *(str(other.pk) for other in others)]
    assert post(client, "summons/seen/", ids=ids).status_code == 204
    seen = Summons.all_schools.filter(seen_at__isnull=False)
    assert list(seen) == [mine]

    # Annulée, ou accès suspendu par l'école : plus rien.
    with use_school(school):
        communication.cancel_summons(mine, actor=head)
    assert client.get(SUMMONS).json()["count"] == 0
    Family.all_schools.filter(pk=child.family_id).update(portal_suspended_at=timezone.now())
    assert client.get(CALENDAR).json()["count"] == 0


def test_homeroom_teacher_is_named_and_its_phone_shown_only_if_the_school_chose(
    school, head, alpha
):
    child = enrolled(school, head, alpha["group"])
    client = portal()
    with use_school(school):
        activate(client, child.family.code)
    page = f"/api/portal/children/{child.pk}/"
    assert client.get(page).json()["homeroom_teacher"] is None

    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    with use_school(school):
        group = alpha["group"]
        group.homeroom_teacher = teacher
        group.save()
    assert client.get(page).json()["homeroom_teacher"] == {
        "name": teacher.get_full_name(),
        "phone": None,
    }

    school.settings = {**school.settings, "portal": {"teacher_phone": True}}
    school.save(update_fields=["settings"])
    assert client.get(page).json()["homeroom_teacher"]["phone"] == teacher.phone
