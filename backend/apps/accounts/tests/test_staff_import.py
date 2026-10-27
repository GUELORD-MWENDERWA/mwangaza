"""/api/staff/import/ et /api/staff/access-letters/ : import du personnel depuis Excel et lettres
d'accès (R.1), permission `roles.manage`."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts import staff_import
from apps.accounts.models import Membership, User
from apps.accounts.roles import starter_role_name
from apps.audit.models import AuditLog
from apps.core.documents import workbook
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

URL = "/api/staff/import/"
LETTERS = "/api/staff/access-letters/"
TITLES = ["NOM", "POST-NOM", "PRÉNOM", "TÉLÉPHONE", "RÔLES"]
TEACHER, CASHIER = starter_role_name("teacher"), starter_role_name("cashier")


def send(client, rows, *, expected=None):
    body = {"file": SimpleUploadedFile("personnel.xlsx", workbook(TITLES, rows))}
    if expected is not None:
        body["expected"] = expected
    return client.client.post(URL, body, HTTP_HOST=client.host)


def logged(school, action) -> int:
    with use_school(school):
        return AuditLog.objects.filter(action=action).count()


@pytest.fixture
def member(school):
    """Déjà dans l'école alpha."""
    return MembershipFactory(school=school, roles=["teacher"]).user


@pytest.fixture
def elsewhere(other_school):
    """Compte de l'école beta seulement."""
    return MembershipFactory(
        school=other_school, roles=["head"], user__last_name="Byamungu", user__first_name="Anne"
    ).user


def rows(member, elsewhere):
    return [
        ["Kambale", "Muhindo", "Josué", "0971234567", TEACHER],
        # Rôles sans tenir compte des accents ni de la casse, plusieurs séparés par « ; ».
        ["Kavira", "", "Esther", "+243 99 230 77 41", f"{TEACHER.upper()} ; {CASHIER.lower()}"],
        ["Autre", "", "Nom", elsewhere.phone, CASHIER],
        ["Paluku", "", "", "097 55 21", TEACHER],
        ["Bahati", "", "", "0000001234", TEACHER],
        ["Kahindo", "", "", "0815550000", "Bibliothécaire"],
        ["Mumbere", "", "", "0815550001", ""],
        ["Muhindo", "", "", "0971234567", TEACHER],
        ["", "", "Grâce", "0815550002", TEACHER],
        ["Déjà", "", "", member.phone, "Inconnu"],
    ]


def test_preview_writes_nothing_and_flags_each_line(api, head, school, member, elsewhere):
    accounts = User.objects.count()

    response = send(api(head), rows(member, elsewhere))

    assert response.status_code == 200
    body = response.json()
    states = {line["line"]: (line["status"], line["issues"]) for line in body["lines"]}
    assert states[2] == ("ready", [])
    assert states[3] == ("ready", [])
    # Un numéro qui sert dans une autre école : rien ne le dit avant l'enregistrement (B3).
    assert states[4] == ("ready", [])
    assert "Beta" not in response.content.decode()
    assert states[5] == ("error", [{"code": "invalid_phone"}])
    assert states[6] == ("error", [{"code": "demo_number"}])
    assert states[7] == ("error", [{"code": "unknown_role", "role": "Bibliothécaire"}])
    assert states[8] == ("error", [{"code": "missing_role"}])
    assert states[9] == ("error", [{"code": "duplicate_phone", "line": 2}])
    assert states[10] == ("error", [{"code": "missing_name"}])
    # Déjà dans l'école : ignorée, quels que soient ses autres problèmes.
    assert states[11] == ("skipped", [{"code": "already_member"}])
    assert (body["ready_count"], body["skipped_count"], body["error_count"]) == (3, 1, 6)
    assert User.objects.count() == accounts
    assert logged(school, "staff.added") == 0


def test_record_adds_the_ready_lines_in_one_block(api, head, school, member, elsewhere):
    client = api(head)
    sent = rows(member, elsewhere)
    response = send(client, sent, expected=3)

    assert response.status_code == 201
    added = {person["phone"]: person for person in response.json()["added"]}
    assert set(added) == {"+243971234567", "+243992307741", elsewhere.phone}
    josue = User.objects.get(phone="+243971234567")
    assert (josue.last_name, josue.middle_name, josue.first_name) == ("Kambale", "Muhindo", "Josué")
    # Pas de mot de passe avant la lettre d'accès, puis changement obligatoire.
    assert not josue.has_usable_password()
    assert josue.must_change_password
    assert added["+243971234567"] | {"id": None} == {
        "id": None,
        "name": str(josue),
        "phone": "+243971234567",
        "roles": [TEACHER],
        "existing_account": False,
        "letter": True,
    }
    esther = Membership.objects.get(school=school, user__phone="+243992307741")
    with use_school(school):
        assert {role.name for role in esther.roles.all()} == {TEACHER, CASHIER}
    # Numéro connu : ajouté à l'école, ses noms et son mot de passe ne changent pas.
    elsewhere.refresh_from_db()
    assert elsewhere.last_name == "Byamungu"
    assert elsewhere.has_usable_password()
    assert added[elsewhere.phone]["existing_account"] is True
    assert added[elsewhere.phone]["letter"] is False
    assert logged(school, "staff.added") == 3

    # Le même fichier renvoyé ne crée rien deux fois.
    again = send(client, sent).json()
    assert (again["ready_count"], again["skipped_count"]) == (0, 4)
    assert send(client, sent, expected=1).json()["code"] == "nothing_to_record"
    assert Membership.objects.filter(school=school).count() == 5


def test_record_refuses_a_preview_that_changed(api, head, school, member, elsewhere):
    response = send(api(head), rows(member, elsewhere), expected=4)

    assert response.status_code == 409
    assert response.json()["code"] == "preview_outdated"
    assert not User.objects.filter(phone="+243971234567").exists()


def test_letters_give_a_working_password_only_to_who_needs_one(api, head, school, other_head):
    client = api(head)
    send(client, [["Kambale", "", "", "0971234567", TEACHER]], expected=1)
    new = Membership.objects.get(school=school, user__phone="+243971234567")
    used = MembershipFactory(school=school, roles=["teacher"])
    User.objects.filter(pk=used.user_id).update(last_login=timezone.now())
    used_password = User.objects.get(pk=used.user_id).password

    with use_school(school):
        context = staff_import.letters([new.pk, used.pk], actor=head)

    (letter,) = context["letters"]
    user = User.objects.get(pk=new.user_id)
    assert user.check_password(letter["password"])
    assert user.must_change_password
    # Déjà connecté : pas de lettre, son mot de passe ne change pas.
    assert User.objects.get(pk=used.user_id).password == used_password
    assert logged(school, "staff.password_reset") == 1

    pdf = client.get(LETTERS, ids=str(new.pk))
    assert pdf.status_code == 200
    assert pdf["Content-Type"] == "application/pdf"
    user.refresh_from_db()
    assert not user.check_password(letter["password"])  # réimprimée : l'ancienne ne marche plus

    # L'école beta n'imprime pas la lettre d'une personne de l'école alpha.
    refused = api(other_head, host="beta.localhost").get(LETTERS, ids=str(new.pk))
    assert refused.status_code == 409
    assert refused.json()["code"] == "no_letter"


def test_import_and_letters_need_roles_manage(api, cashier, school):
    client = api(cashier)
    target = MembershipFactory(school=school, roles=["teacher"])

    assert send(client, [["Kambale", "", "", "0971234567", TEACHER]]).status_code == 403
    assert client.get(f"{URL}template/").status_code == 403
    assert client.get(LETTERS, ids=str(target.pk)).status_code == 403
