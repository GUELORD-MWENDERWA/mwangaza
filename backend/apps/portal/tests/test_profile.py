"""Coordonnées du parent (H5, M18) : un envoi du portail devient une demande dans chaque école de
ses enfants (seulement ce qui diffère de sa fiche) ; le secrétariat de cette école seulement
(`students.edit`) l'applique à sa propre fiche, ou pas ; journal dans les deux cas."""

from apps.core.tenancy import use_school
from apps.portal.tests.test_access import actions, activate, portal, post
from apps.portal.tests.test_families import link
from apps.students import services as students
from apps.students.models import ContactChange, Guardian
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

PROFILE = "/api/portal/profile/"
CHANGES = "/api/contact-changes/"
ADDRESS = {"commune": "Goma", "quartier": "Himbi", "avenue": "Lukanga", "number": "7"}
EMERGENCY = {"full_name": "Amani Pierre", "phone": "0815539071"}


def send(client, address=ADDRESS, email="neema@exemple.cd", emergency=EMERGENCY):
    body = {"address": address, "email": email, "emergency_contact": emergency}
    return post(client, "profile/", **body)


def pending(school) -> list[ContactChange]:
    with use_school(school):
        return list(ContactChange.objects.filter(status="pending"))


def two_schools(school, other_school, head, other_head, alpha, beta):
    """Un parent relié à une famille dans chaque école ; l'ITIG a déjà son adresse."""
    child = enrolled(school, head, alpha["group"], address=ADDRESS)
    other = enrolled(other_school, other_head, beta["group"])
    client = portal()
    with use_school(school):
        activate(client, child.family.code)
    with use_school(other_school):
        link(client, other.family.code)
    return client, child, other


def test_sending_creates_one_request_per_school_with_what_differs_replacing_the_pending_one(
    school, other_school, head, other_head, alpha, beta
):
    client, _child, other = two_schools(school, other_school, head, other_head, alpha, beta)

    response = send(client)

    assert response.status_code == 200
    assert response.json()["pending_schools"] == [school.name, other_school.name]
    [at_school] = pending(school)
    assert set(at_school.changes) == {"email", "emergency_contact"}  # adresse déjà la même
    assert at_school.changes["emergency_contact"] == {
        "before": {"full_name": "", "phone": ""},
        "after": {"full_name": "Amani Pierre", "phone": "+243815539071"},
    }
    [at_other] = pending(other_school)
    assert at_other.changes["address"]["before"]["quartier"] == ""
    # Rien n'a changé dans les fiches avant le secrétariat.
    with use_school(other_school):
        assert Guardian.objects.get(family=other.family).email == ""

    # Nouvel envoi : il remplace la demande en attente ; contact d'urgence vide : rien à changer.
    send(client, email="", emergency={"full_name": "", "phone": ""})
    assert pending(school) == []
    [replaced] = pending(other_school)
    assert set(replaced.changes) == {"address"}
    profile = client.get(PROFILE).json()
    assert (profile["address"], profile["pending_schools"]) == (ADDRESS, [other_school.name])

    # Accès suspendu par une école : elle ne reçoit plus rien.
    with use_school(other_school):
        students.set_portal_access(other.family, actor=other_head, suspended=True)
    send(client, email="nouveau@exemple.cd")
    assert len(pending(school)) == 1
    assert [c.changes for c in pending(other_school)] == [replaced.changes]


def test_applying_writes_the_familys_record_of_this_school_only_with_audit(
    api, school, other_school, head, other_head, alpha, beta, django_assert_max_num_queries
):
    client, child, other = two_schools(school, other_school, head, other_head, alpha, beta)
    with use_school(school):
        sister, _ = students.create_student(
            actor=head, family=child.family, last_name="Kasereka", first_name="Esther", sex="F"
        )
    moved = {**ADDRESS, "quartier": "Katindo", "avenue": "Du Lac", "number": "12"}
    send(client, address=moved)
    [request] = pending(school)
    path = f"{CHANGES}{request.pk}/apply/"

    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    assert api(teacher).get(CHANGES).status_code == 403
    assert api(teacher).post(path).status_code == 403
    # L'autre école ne voit ni n'applique la demande.
    beta_api = api(other_head, host="beta.localhost")
    assert [c["id"] for c in beta_api.get(CHANGES).json()["results"]] == [
        str(pending(other_school)[0].pk)
    ]
    assert beta_api.post(path).status_code == 404

    head_api = api(head)
    with django_assert_max_num_queries(9):  # autant pour 1 ou 50 demandes
        listed = head_api.get(CHANGES).json()["results"]
    assert [(c["family"]["code"], len(c["family"]["children"])) for c in listed] == [
        (child.family.code, 2)
    ]
    response = head_api.post(path)

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["handled_by"]) == ("applied", str(head))
    with use_school(school):
        for student in (child, sister):
            student.refresh_from_db()
            assert student.address == moved
        guardians = {g.full_name: g for g in Guardian.objects.filter(family=child.family)}
        assert guardians["Kahindo Neema"].email == "neema@exemple.cd"
        urgent = guardians["Amani Pierre"]
        assert (urgent.phone, urgent.is_emergency_contact, urgent.is_primary) == (
            "+243815539071",
            True,
            False,
        )
    [entry] = actions(school, "students.contact_change_applied")
    assert entry.after["email"] == "neema@exemple.cd"
    # Déjà traitée : personne ne l'applique ni ne la refuse une seconde fois.
    assert api(head).post(f"{CHANGES}{request.pk}/dismiss/").json()["code"] == "already_handled"
    # L'autre école n'a rien reçu de l'ITIG : sa demande attend toujours.
    with use_school(other_school):
        assert Guardian.objects.get(family=other.family).email == ""
    assert actions(other_school, "students.contact_change_applied") == []


def test_not_applying_keeps_the_record_and_is_logged(
    api, school, other_school, head, other_head, alpha, beta
):
    client, _child, other = two_schools(school, other_school, head, other_head, alpha, beta)
    send(client)
    [request] = pending(other_school)

    response = api(other_head, host="beta.localhost").post(f"{CHANGES}{request.pk}/dismiss/")

    assert response.json()["status"] == "dismissed"
    with use_school(other_school):
        other.refresh_from_db()
        assert other.address.get("quartier", "") == ""
    assert len(actions(other_school, "students.contact_change_dismissed")) == 1
    assert pending(other_school) == []
    assert client.get(PROFILE).json()["pending_schools"] == [school.name]
