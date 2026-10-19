"""Conseil de délibération (NB.5) : secret (membres seuls en lecture, direction des études seule
en écriture), session de période figée avec le conseil après « bulletins prêts », procès-verbal,
journal, isolation entre écoles."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.academics import deliberation
from apps.academics.models import DeliberationSnapshot, GradeSheet, ReportCardsReady
from apps.academics.tests import test_resits
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import ClassGroup
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

data = test_resits.data
physics_teacher = test_resits.physics_teacher


def url(data, tail="", term=None) -> str:
    query = f"?term={term.pk}" if term else ""
    return f"/api/class-groups/{data['a'].pk}/deliberation/{tail}{query}"


@pytest.fixture
def director(school):
    return MembershipFactory(school=school, roles=["study_director"]).user


def ready(school, data, actor) -> None:
    """Fiches de la 1re période validées, puis bulletins dits prêts par le titulaire."""
    now = timezone.now()
    with use_school(school):
        for course in (data["physics"], data["workshop"]):
            GradeSheet.objects.update_or_create(
                course=course,
                term=data["p1"],
                defaults={"status": GradeSheet.Status.VALIDATED, "validated_at": now},
            )
        ReportCardsReady.objects.create(
            class_group=data["a"],
            term=data["p1"],
            declared_by=actor,
            declared_at=now + timedelta(seconds=1),
        )


def test_only_council_members_read_and_only_the_direction_writes(
    api, school, physics_teacher, data
):
    titular = MembershipFactory(school=school, roles=["teacher"]).user
    with use_school(school):
        ClassGroup.objects.filter(pk=data["a"].pk).update(homeroom_teacher=titular)
    # Enseignant de la classe et titulaire : lecture seule.
    for member in (physics_teacher, titular):
        client = api(member)
        answer = client.get(url(data, term=data["p1"]))
        assert answer.status_code == 200
        assert answer.json()["can_edit"] is False
        assert client.put(url(data, term=data["p1"]), {"held_on": "2026-11-08"}).status_code == 403
        assert client.put(url(data, "council/"), {"present": []}).status_code == 403
        assert client.post(url(data, "proclaim/", data["p1"])).status_code == 403
    # Enseignant d'une autre classe, secrétaire : rien, ni le tableau ni le procès-verbal.
    outsider = api(MembershipFactory(school=school, roles=["teacher"]).user)
    refused = outsider.get(url(data, term=data["p1"]))
    assert refused.status_code == 403
    assert refused.json()["code"] == "not_a_member"
    assert outsider.get(url(data, "minutes/")).status_code == 403
    secretary = api(MembershipFactory(school=school, roles=["secretary"]).user)
    assert secretary.get(url(data)).status_code == 403


def test_a_period_is_proclaimed_once_ready_and_freezes_results_and_council(
    api, school, director, physics_teacher, data
):
    client = api(director)
    p1 = data["p1"]
    assert client.put(url(data, term=p1), {"held_on": "2026-11-08"}).status_code == 200
    members = {m["name"]: m for m in client.get(url(data, term=p1)).json()["council"]["members"]}
    assert members[physics_teacher.get_full_name()]["courses"] == ["Physique"]
    assert members[director.get_full_name()]["direction"] is True
    outsider = MembershipFactory(school=school, roles=["teacher"]).user
    council = {"present": [str(director.pk), str(outsider.pk)]}
    answer = client.put(url(data, "council/", p1), council)
    assert answer.json()["code"] == "bad_member"
    council = {"present": [str(director.pk)], "chair": str(physics_teacher.pk)}
    answer = client.put(url(data, "council/", p1), council)
    assert answer.json()["code"] == "not_present"
    council = {
        "present": [str(director.pk), str(physics_teacher.pk)],
        "chair": str(director.pk),
        "secretary": str(physics_teacher.pk),
        "remarks": "Classe sérieuse.",
    }
    assert client.put(url(data, "council/", p1), council).status_code == 200

    # Pas de proclamation ni de procès-verbal avant « bulletins prêts ».
    answer = client.post(url(data, "proclaim/", p1))
    assert answer.json()["code"] == "report_cards_not_ready"
    assert client.get(url(data, "minutes/", p1) + "&output=html").status_code == 400
    ready(school, data, director)
    proclaimed = client.post(url(data, "proclaim/", p1)).json()
    assert proclaimed["status"] == "proclaimed"
    assert proclaimed["kind"] == "period"
    results = {r["enrollment"]: r for r in proclaimed["results"]}
    assert results[str(data["amani"])]["place"] == 1
    assert results[str(data["amani"])]["conduct"] == "TB"

    with use_school(school):
        snapshot = DeliberationSnapshot.objects.get(deliberation__term=p1)
        assert snapshot.council["chair"] == director.get_full_name()
        assert snapshot.council["remarks"] == "Classe sérieuse."
        assert {r["enrollment"] for r in snapshot.rows} == {str(data["amani"]), str(data["josue"])}
        # La fin d'année n'est pas touchée : le bulletin et le passage ne lisent qu'elle.
        group = ClassGroup.objects.get(pk=data["a"].pk)
        assert deliberation.proclaimed_rows(group) is None
        assert AuditLog.objects.filter(action="deliberation.council").count() == 1
        assert AuditLog.objects.filter(action="deliberation.proclaimed").count() == 1
    assert client.get(url(data)).json()["status"] == "draft"

    # Procès-verbal : lu par un membre, figé ; le PDF est noté au journal.
    minutes = api(physics_teacher).get(url(data, "minutes/", p1) + "&output=html")
    assert minutes.status_code == 200
    text = minutes.content.decode()
    assert director.get_full_name() in text and "Classe sérieuse." in text
    assert client.get(url(data, "minutes/", p1)).status_code == 200
    with use_school(school):
        assert AuditLog.objects.filter(action="deliberation.minutes_printed").count() == 1


def test_another_school_cannot_read_the_council_or_its_minutes(api, other_school, data):
    other = api(
        MembershipFactory(school=other_school, roles=["study_director"]).user, host="beta.localhost"
    )
    assert other.get(url(data, term=data["p1"])).status_code == 404
    assert other.put(url(data, "council/"), {"present": []}).status_code == 404
    assert other.get(url(data, "minutes/")).status_code == 404
