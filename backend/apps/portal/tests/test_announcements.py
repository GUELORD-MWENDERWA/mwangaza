"""Annonces des écoles sur le portail (H4) : seulement celles qui visent la famille (toutes les
familles, ou une classe d'un de ses enfants), jamais archivées ni d'une année passée, ni d'une
autre école ou famille ; marquées lues par la famille, « lue par N familles » dans la Gestion ;
pièce jointe seulement pour une famille destinataire."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.core.files.base import ContentFile
from django.utils import timezone

from apps.core.tenancy import use_all_schools, use_school
from apps.notifications import services as notifications
from apps.notifications.models import Announcement
from apps.portal.tests.test_access import activate, new_family, portal, post
from apps.portal.tests.test_families import link
from apps.schools import organisation
from apps.students.models import Family
from apps.students.tests.conftest import enrolled

ANNOUNCEMENTS = "/api/portal/announcements/"
PDF = b"%PDF-1.4\n% convocation\n"


def announce(school, actor, title, day, *, groups=(), pdf=False, archived=False):
    """Annonce publiée le `day` (2026), à toutes les familles ou aux classes `groups`."""
    with use_school(school):
        announcement = notifications.publish(
            actor=actor,
            title=title,
            body="Samedi à 9 h dans la grande salle.",
            audience="class_groups" if groups else "all_families",
            class_groups=list(groups),
            attachment=ContentFile(PDF) if pdf else None,
        )
        if archived:
            notifications.archive(announcement, actor=actor)
    published_at = datetime(2026, *day, 8, tzinfo=ZoneInfo("Africa/Lubumbashi"))
    with use_all_schools():
        Announcement.all_schools.filter(pk=announcement.pk).update(published_at=published_at)
    return announcement


def titles(client, **params) -> list[str]:
    return [a["title"] for a in client.get(ANNOUNCEMENTS, params).json()["results"]]


def read(client, *announcements):
    return post(client, "announcements/read/", ids=[str(a.pk) for a in announcements])


def attachment(client, announcement):
    return client.get(f"{ANNOUNCEMENTS}{announcement.pk}/attachment/")


def test_a_family_sees_its_schools_announcements_for_all_or_its_childrens_classes_only(
    school, other_school, head, other_head, alpha, beta, django_assert_max_num_queries
):
    with use_school(school):
        # Année passée (finie le 02/07/2026) : ses annonces ne s'affichent plus.
        organisation.create_year(actor=head, starts_on=date(2025, 9, 1), ends_on=date(2026, 7, 2))
        fourth = organisation.create_class_group(
            actor=head,
            academic_year=alpha["year"],
            level=alpha["other_level"],
            track=alpha["track"],
            section="A",
            capacity=45,
        )
    child = enrolled(school, head, alpha["group"])
    enrolled(school, head, fourth, last_name="Amani")
    announce(school, head, "Fin de l'année passée", (6, 20))
    announce(school, head, "Rentrée le 1er septembre", (8, 25))
    announce(school, head, "Réunion des parents de 3e", (10, 1), groups=[alpha["group"]])
    announce(school, head, "Réunion des parents de 4e", (10, 1), groups=[fourth])
    announce(school, head, "Mesures d'hygiène", (9, 10), archived=True)
    announce(other_school, other_head, "Portes ouvertes", (9, 20))
    client = portal()
    with use_school(school):
        activate(client, child.family.code)

    [first, second] = client.get(ANNOUNCEMENTS).json()["results"]
    assert (first["title"], first["school_name"], first["classes"]) == (
        "Réunion des parents de 3e",
        school.name,
        ["3E ÉLECTRICITÉ A"],
    )
    assert (second["title"], second["classes"], second["read"]) == (
        "Rentrée le 1er septembre",
        [],
        False,
    )

    # Le même tuteur relie son enfant de l'autre école : ses annonces s'ajoutent.
    other = enrolled(other_school, other_head, beta["group"])
    with use_school(other_school):
        other_family = other.family
        assert link(client, other_family.code).status_code == 200
    with django_assert_max_num_queries(9):  # autant de requêtes pour 1 ou 50 annonces
        assert titles(client) == [
            "Réunion des parents de 3e",
            "Portes ouvertes",
            "Rentrée le 1er septembre",
        ]
    assert titles(client, family=other_family.pk) == ["Portes ouvertes"]

    # Accès suspendu par l'école ou école suspendue : plus rien de cette école.
    with use_all_schools():
        Family.all_schools.filter(pk=other_family.pk).update(portal_suspended_at=timezone.now())
    other_school.status = other_school.Status.SUSPENDED
    other_school.save(update_fields=["status"])
    assert titles(client) == ["Réunion des parents de 3e", "Rentrée le 1er septembre"]
    assert portal().get(ANNOUNCEMENTS).status_code == 403
    assert portal("alpha.localhost").get(ANNOUNCEMENTS).status_code == 404


def test_read_once_per_family_counted_in_the_school_and_attachment_for_recipients_only(
    api, school, other_school, head, other_head, alpha, beta
):
    child = enrolled(school, head, alpha["group"])
    meeting = announce(school, head, "Réunion des parents de 3e", (10, 1), groups=[alpha["group"]])
    meeting_pdf = announce(school, head, "Convocation", (10, 2), groups=[alpha["group"]], pdf=True)
    others = enrolled(school, head, alpha["group"], last_name="Paluku")
    beta_news = announce(other_school, other_head, "Portes ouvertes", (9, 20), pdf=True)
    client = portal()
    with use_school(school):
        activate(client, child.family.code)
        stranger = portal()
        activate(stranger, new_family(school, head, phone="+243990000001").code, phone="0990000001")
        neighbour = portal()
        others.family.guardians.update(phone="+243990000002")
        activate(neighbour, others.family.code, phone="0990000002")

    # Une annonce d'une autre école ou qui ne vise pas la famille est ignorée ; deux fois : une.
    assert read(client, meeting, beta_news).status_code == 204
    assert read(client, meeting).status_code == 204
    assert read(stranger, meeting).status_code == 204
    read(neighbour, meeting, meeting_pdf)

    assert [a["read"] for a in client.get(ANNOUNCEMENTS).json()["results"]] == [False, True]
    school_list = api(head).get("/api/announcements/").json()["results"]
    assert [(a["title"], a["read_by"]) for a in school_list] == [
        ("Convocation", 1),
        ("Réunion des parents de 3e", 2),
    ]
    beta_list = api(other_head, host="beta.localhost").get("/api/announcements/").json()
    assert [a["read_by"] for a in beta_list["results"]] == [0]

    response = attachment(client, meeting_pdf)
    assert response.status_code == 200 and b"".join(response.streaming_content) == PDF
    # Téléchargée, jamais ouverte dans une page à l'adresse de l'application (S.4).
    assert response["Content-Disposition"].startswith("attachment;")
    assert response["X-Content-Type-Options"] == "nosniff"
    # Famille sans enfant dans la classe, autre école, annonce sans pièce jointe : 404.
    assert attachment(stranger, meeting_pdf).status_code == 404
    assert attachment(client, beta_news).status_code == 404
    assert attachment(client, meeting).status_code == 404
