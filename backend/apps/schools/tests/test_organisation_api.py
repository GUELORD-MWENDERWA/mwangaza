"""API de l'organisation scolaire (C1-C3) : droit `classes.manage`, isolation entre écoles."""

from datetime import date

import pytest

from apps.audit.models import AuditLog
from apps.core.tenancy import use_all_schools, use_school
from apps.schools import organisation
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Track
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

YEARS = "/api/academic-years/"
LEVELS = "/api/levels/"
TRACKS = "/api/tracks/"
CLASSES = "/api/class-groups/"
MATRICULE = "/api/matricule-format/"


def structure(school, actor) -> dict:
    """Une année (modèle secondaire), deux niveaux, une option, une classe."""
    with use_school(school):
        year = organisation.create_year(
            actor=actor, starts_on=date(2026, 9, 1), ends_on=date(2027, 7, 2)
        )
        level = organisation.create_level(actor=actor, name="3e", cycle="secondary_technical")
        other_level = organisation.create_level(actor=actor, name="4e", cycle="secondary_technical")
        track = organisation.create_track(actor=actor, name="Électricité", code="ELEC")
        group = organisation.create_class_group(
            actor=actor, academic_year=year, level=level, track=track, section="A", capacity=45
        )
    return {
        "year": year,
        "level": level,
        "other_level": other_level,
        "track": track,
        "group": group,
    }


@pytest.fixture
def alpha(school, head):
    return structure(school, head)


@pytest.fixture
def beta(other_school, other_head):
    return structure(other_school, other_head)


def entries(school, action: str) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.filter(action=action))


# Droits


def test_study_director_manages_the_organisation_without_two_factor(api, school, alpha):
    director = MembershipFactory(school=school, roles=["study_director"]).user

    response = api(director, mfa=False).get(CLASSES)

    assert response.status_code == 200
    assert [group["name"] for group in response.json()] == ["3e Électricité A"]


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("post", YEARS),
        ("post", LEVELS),
        ("post", f"{LEVELS}reorder/"),
        ("post", CLASSES),
        ("get", f"{CLASSES}homeroom-candidates/"),
        ("get", MATRICULE),
        ("patch", MATRICULE),
        ("post", f"{MATRICULE}preview/"),
    ],
)
def test_without_classes_manage_everything_is_refused(api, cashier, alpha, method, url):
    response = getattr(api(cashier), method)(url)

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_students_view_reads_years_levels_tracks_and_classes_of_its_school_only(
    api, school, cashier, alpha, beta
):
    """Filtres de la liste des élèves et inscription (2.2.1), barèmes (2.5.1) : lecture seule
    avec `students.view` ou un droit des frais ; sans aucun de ces droits, refusé."""
    client = api(cashier)
    for url in (YEARS, LEVELS, TRACKS, CLASSES, f"{CLASSES}{alpha['group'].id}/"):
        assert client.get(url).status_code == 200, url
    assert [group["name"] for group in client.get(CLASSES).json()] == ["3e Électricité A"]
    assert client.get(f"{CLASSES}{beta['group'].id}/").status_code == 404
    assert client.get(f"{YEARS}{beta['year'].id}/").status_code == 404

    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    for url in (YEARS, LEVELS, TRACKS, CLASSES):
        assert api(teacher).get(url).status_code == 403, url


def test_detail_endpoints_are_refused_too(api, cashier, alpha):
    client = api(cashier)
    for response in (
        client.patch(f"{YEARS}{alpha['year'].id}/", {"name": "X"}),
        client.put(f"{YEARS}{alpha['year'].id}/terms/", {"terms": []}),
        client.post(f"{YEARS}{alpha['year'].id}/make-current/"),
        client.delete(f"{LEVELS}{alpha['other_level'].id}/"),
        client.patch(f"{TRACKS}{alpha['track'].id}/", {"name": "X"}),
        client.delete(f"{CLASSES}{alpha['group'].id}/"),
    ):
        assert response.status_code == 403
    with use_all_schools():
        assert ClassGroup.all_schools.filter(pk=alpha["group"].pk).exists()


# Années et découpage


def test_create_a_year_from_a_template_with_the_classes_of_another(api, head, alpha):
    response = api(head).post(
        YEARS,
        {
            "starts_on": "2027-09-06",
            "ends_on": "2028-07-01",
            "template": "trimesters",
            "copy_classes_from": str(alpha["year"].id),
        },
    )

    assert response.status_code == 201, response.content
    data = response.json()
    assert (data["name"], data["is_current"], data["status"]) == ("2027-2028", False, "open")
    assert [term["kind"] for term in data["terms"]] == ["trimester"] * 3
    assert [child["kind"] for child in data["terms"][0]["children"]] == ["period", "period", "exam"]
    assert data["terms"][0]["children"][0] | {"id": None} == {
        "id": None,
        "kind": "period",
        "name": "",
        "starts_on": None,
        "ends_on": None,
    }
    classes = api(head).get(CLASSES, academic_year=data["id"]).json()
    assert [group["name"] for group in classes] == ["3e Électricité A"]


def test_list_years_newest_first_with_their_terms(api, head, alpha):
    api(head).post(YEARS, {"starts_on": "2027-09-06", "ends_on": "2028-07-01"})

    data = api(head).get(YEARS).json()

    assert [year["name"] for year in data] == ["2027-2028", "2026-2027"]
    assert [year["is_current"] for year in data] == [False, True]
    assert len(data[1]["terms"]) == 2


def test_year_errors(api, head, alpha):
    client = api(head)

    taken = client.post(
        YEARS, {"name": "2026-2027", "starts_on": "2027-09-06", "ends_on": "2028-07-01"}
    )
    dates = client.post(YEARS, {"starts_on": "2028-07-01", "ends_on": "2027-09-06"})
    current = client.delete(f"{YEARS}{alpha['year'].id}/")

    assert (taken.status_code, taken.json()["code"]) == (409, "year_name_taken")
    assert dates.status_code == 400
    assert dates.json()["fields"]["ends_on"][0]["code"] == "end_before_start"
    assert (current.status_code, current.json()["code"]) == (409, "year_is_current")


def test_rename_make_current_and_delete_a_year(api, head, school, alpha):
    client = api(head)
    new = client.post(YEARS, {"starts_on": "2027-09-06", "ends_on": "2028-07-01"}).json()

    renamed = client.patch(f"{YEARS}{new['id']}/", {"name": "2027-28"})
    current = client.post(f"{YEARS}{new['id']}/make-current/")
    old = client.delete(f"{YEARS}{alpha['year'].id}/")
    client.post(f"{YEARS}{alpha['year'].id}/make-current/")
    empty = client.delete(f"{YEARS}{new['id']}/")

    assert renamed.json()["name"] == "2027-28"
    assert current.json()["is_current"] is True
    assert (old.status_code, old.json()["code"]) == (409, "year_in_use")
    assert empty.status_code == 204
    with use_school(school):
        assert list(AcademicYear.objects.values_list("name", flat=True)) == ["2026-2027"]


def test_put_the_terms(api, head, school, alpha):
    year = api(head).get(f"{YEARS}{alpha['year'].id}/").json()
    first, second = year["terms"]
    first |= {"starts_on": "2026-09-07", "ends_on": "2026-12-23"}
    first["children"][0] |= {"name": "P1", "starts_on": "2026-09-07", "ends_on": "2026-11-07"}
    first["children"].append({"kind": "period", "name": "Rattrapage"})

    response = api(head).put(f"{YEARS}{year['id']}/terms/", {"terms": [first]})

    assert response.status_code == 200, response.content
    [semester] = response.json()["terms"]
    assert semester["id"] == first["id"]
    assert [child["name"] for child in semester["children"]] == ["P1", "", "", "Rattrapage"]
    assert semester["children"][0]["ends_on"] == "2026-11-07"
    assert len(entries(school, "organisation.terms_changed")) == 1
    assert second["id"] not in {term["id"] for term in semester["children"]}


def test_put_terms_errors_are_on_their_field(api, head, alpha):
    year = api(head).get(f"{YEARS}{alpha['year'].id}/").json()
    year["terms"][1]["children"][2]["ends_on"] = "2027-08-01"

    response = api(head).put(f"{YEARS}{year['id']}/terms/", {"terms": year["terms"]})

    assert response.status_code == 400
    assert response.json()["fields"] == {
        "terms.1.children.2.ends_on": [
            {"code": "outside_year", "detail": "Cette date est en dehors de l'année scolaire."}
        ]
    }


# Niveaux et options


def test_levels(api, head, school, alpha):
    client = api(head)

    created = client.post(LEVELS, {"name": "7e EB", "cycle": "basic"})
    renamed = client.patch(f"{LEVELS}{created.json()['id']}/", {"name": "7e"})
    ids = [alpha["other_level"].id, created.json()["id"], alpha["level"].id]
    reordered = client.post(f"{LEVELS}reorder/", {"ids": [str(pk) for pk in ids]})
    in_use = client.delete(f"{LEVELS}{alpha['level'].id}/")
    unused = client.delete(f"{LEVELS}{alpha['other_level'].id}/")

    assert created.status_code == 201
    assert created.json() | {"id": None} == {
        "id": None,
        "name": "7e EB",
        "cycle": "basic",
        "order": 2,
    }
    assert renamed.json()["name"] == "7e"
    assert [level["name"] for level in reordered.json()] == ["4e", "7e", "3e"]
    assert (in_use.status_code, in_use.json()["code"]) == (409, "level_in_use")
    assert unused.status_code == 204
    assert [level["name"] for level in client.get(LEVELS).json()] == ["7e", "3e"]


def test_tracks(api, head, alpha):
    client = api(head)

    created = client.post(TRACKS, {"name": "Électronique", "code": "elo"})
    wrong = client.post(TRACKS, {"name": "Mécanique", "code": "MÉCA"})
    taken = client.post(TRACKS, {"name": "Autre", "code": "ELEC"})
    renamed = client.patch(f"{TRACKS}{created.json()['id']}/", {"name": "Électronique générale"})

    assert created.status_code == 201
    assert created.json()["code"] == "ELO"
    assert wrong.json()["fields"]["code"][0]["code"] == "invalid_code"
    assert (taken.status_code, taken.json()["code"]) == (409, "track_code_taken")
    assert renamed.json() == {
        "id": created.json()["id"],
        "name": "Électronique générale",
        "code": "ELO",
    }


# Classes


def test_list_classes_of_the_current_year_by_default(api, head, alpha):
    other = api(head).post(YEARS, {"starts_on": "2027-09-06", "ends_on": "2028-07-01"}).json()

    current = api(head).get(CLASSES).json()
    empty = api(head).get(CLASSES, academic_year=other["id"]).json()

    assert current == [
        {
            "id": str(alpha["group"].id),
            "academic_year": str(alpha["year"].id),
            "level": str(alpha["level"].id),
            "track": str(alpha["track"].id),
            "section": "A",
            "name": "3e Électricité A",
            "capacity": 45,
            "student_count": 0,
            "homeroom_teacher": None,
        }
    ]
    assert empty == []


def test_create_update_and_delete_a_class(api, head, school, alpha):
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    client = api(head)

    created = client.post(
        CLASSES,
        {
            "academic_year": str(alpha["year"].id),
            "level": str(alpha["level"].id),
            "track": str(alpha["track"].id),
            "section": "b",
            "homeroom_teacher": str(teacher.id),
        },
    )
    group_id = created.json()["id"]
    duplicate = client.patch(f"{CLASSES}{group_id}/", {"section": "A"})
    updated = client.patch(f"{CLASSES}{group_id}/", {"capacity": 40, "homeroom_teacher": None})
    deleted = client.delete(f"{CLASSES}{group_id}/")

    assert created.status_code == 201, created.content
    assert created.json()["name"] == "3e Électricité B"
    assert created.json()["homeroom_teacher"] == {
        "id": str(teacher.id),
        "last_name": teacher.last_name,
        "middle_name": "",
        "first_name": teacher.first_name,
    }
    assert (duplicate.status_code, duplicate.json()["code"]) == (409, "class_exists")
    assert updated.json()["capacity"] == 40
    assert updated.json()["homeroom_teacher"] is None
    assert deleted.status_code == 204
    assert [e.entity_label for e in entries(school, "organisation.class_deleted")] == [
        "3e Électricité B"
    ]


def test_homeroom_candidates_are_the_active_staff(api, head, school, other_head, alpha):
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    MembershipFactory(school=school, roles=["teacher"], is_active=False)

    data = api(head).get(f"{CLASSES}homeroom-candidates/").json()

    assert {person["id"] for person in data} == {str(head.id), str(teacher.id)}


# Matricule


def test_matricule_format(api, head, school, alpha):
    client = api(head)

    current = client.get(MATRICULE).json()
    preview = client.post(f"{MATRICULE}preview/", {"matricule_format": "LV/{OPT}/{AA}/{000}"})
    wrong = client.post(f"{MATRICULE}preview/", {"matricule_format": "LV/{000}"})
    saved = client.patch(MATRICULE, {"matricule_format": "ITIG-{AAAA}-{0000}"})
    refused = client.patch(MATRICULE, {"matricule_format": "ITIG-{AAAA}"})

    assert current == {
        "matricule_format": "ALPHA-{AAAA}-{0000}",
        "auto_matricule": True,
        "example": "ALPHA-2026-0001",
    }
    assert preview.json() == {
        "matricule_format": "LV/{OPT}/{AA}/{000}",
        "example": "LV/ELEC/26/001",
    }
    assert wrong.json()["fields"]["matricule_format"][0]["code"] == "matricule_year_missing"
    assert saved.json() == {
        "matricule_format": "ITIG-{AAAA}-{0000}",
        "auto_matricule": True,
        "example": "ITIG-2026-0001",
    }
    assert refused.json()["fields"]["matricule_format"][0]["code"] == "matricule_number_missing"
    assert School.objects.get(pk=school.pk).matricule_format == "ITIG-{AAAA}-{0000}"
    assert len(entries(school, "organisation.matricule_format_changed")) == 1


def test_school_stops_giving_matricules_alone_and_it_is_logged(api, head, school, alpha, beta):
    """4.13 (C5) : l'interrupteur seul, sans toucher au format ni à l'autre école."""
    client = api(head)

    off = client.patch(MATRICULE, {"auto_matricule": False})
    client.patch(MATRICULE, {"auto_matricule": False})

    assert off.json()["auto_matricule"] is False
    assert off.json()["matricule_format"] == "ALPHA-{AAAA}-{0000}"
    assert client.get("/api/school/").json()["auto_matricule"] is False
    (entry,) = entries(school, "organisation.matricule_format_changed")
    assert (entry.before, entry.after) == ({"auto_matricule": True}, {"auto_matricule": False})
    assert School.objects.get(code="beta").auto_matricule is True


# Isolation entre écoles


def test_other_school_organisation_is_invisible(api, other_head, alpha, beta):
    client = api(other_head, host="beta.localhost")

    assert [year["id"] for year in client.get(YEARS).json()] == [str(beta["year"].id)]
    assert {level["id"] for level in client.get(LEVELS).json()} == {
        str(beta["level"].id),
        str(beta["other_level"].id),
    }
    assert [track["id"] for track in client.get(TRACKS).json()] == [str(beta["track"].id)]
    assert [group["id"] for group in client.get(CLASSES).json()] == [str(beta["group"].id)]
    assert client.get(MATRICULE).json()["matricule_format"] == "BETA-{AAAA}-{0000}"
    other_candidates = client.get(f"{CLASSES}homeroom-candidates/").json()
    assert [person["id"] for person in other_candidates] == [str(other_head.id)]


def test_other_school_organisation_cannot_be_read_or_changed(api, other_head, school, alpha, beta):
    client = api(other_head, host="beta.localhost")
    year, level, track, group = (alpha[key].id for key in ("year", "other_level", "track", "group"))

    responses = [
        client.get(f"{YEARS}{year}/"),
        client.patch(f"{YEARS}{year}/", {"name": "Volée"}),
        client.put(f"{YEARS}{year}/terms/", {"terms": []}),
        client.post(f"{YEARS}{year}/make-current/"),
        client.delete(f"{YEARS}{year}/"),
        client.get(f"{LEVELS}{level}/"),
        client.patch(f"{LEVELS}{level}/", {"name": "Volé"}),
        client.delete(f"{LEVELS}{level}/"),
        client.patch(f"{TRACKS}{track}/", {"name": "Volée"}),
        client.delete(f"{TRACKS}{track}/"),
        client.get(f"{CLASSES}{group}/"),
        client.patch(f"{CLASSES}{group}/", {"section": "Z"}),
        client.delete(f"{CLASSES}{group}/"),
    ]

    assert [response.status_code for response in responses] == [404] * len(responses)
    with use_school(school):
        assert AcademicYear.objects.get().name == "2026-2027"
        assert AcademicYear.objects.get().terms.count() == 8
        assert Level.objects.count() == 2
        assert Track.objects.get().name == "Électricité"
        assert ClassGroup.objects.get().section == "A"


def test_other_school_references_are_refused(api, other_head, school, alpha, beta):
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    client = api(other_head, host="beta.localhost")

    responses = [
        client.post(
            CLASSES, {"academic_year": str(alpha["year"].id), "level": str(beta["level"].id)}
        ),
        client.post(
            CLASSES, {"academic_year": str(beta["year"].id), "level": str(alpha["level"].id)}
        ),
        client.patch(f"{CLASSES}{beta['group'].id}/", {"track": str(alpha["track"].id)}),
        client.patch(f"{CLASSES}{beta['group'].id}/", {"homeroom_teacher": str(teacher.id)}),
        client.post(
            YEARS,
            {
                "starts_on": "2027-09-06",
                "ends_on": "2028-07-01",
                "copy_classes_from": str(alpha["year"].id),
            },
        ),
        client.get(CLASSES, academic_year=str(alpha["year"].id)),
        client.post(f"{LEVELS}reorder/", {"ids": [str(alpha["level"].id)]}),
    ]

    assert [response.status_code for response in responses] == [400] * len(responses)
    first_errors = [next(iter(response.json()["fields"].items())) for response in responses]
    assert [(field, errors[0]["code"]) for field, errors in first_errors] == [
        ("academic_year", "does_not_exist"),
        ("level", "does_not_exist"),
        ("track", "does_not_exist"),
        ("homeroom_teacher", "does_not_exist"),
        ("copy_classes_from", "does_not_exist"),
        ("academic_year", "does_not_exist"),
        ("ids", "incomplete_levels"),
    ]
    with use_school(school):
        assert ClassGroup.objects.count() == 1
