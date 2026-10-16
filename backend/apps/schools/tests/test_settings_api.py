"""Paramètres de l'école (M5, Q8) : `/api/school/settings/` (`school.configure`), réglages du reçu,
logos (couleur et noir et blanc) et leurs adresses publiques `/api/school/logo/`,
`/api/school/logo-monochrome/`."""

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL.PngImagePlugin import PngInfo

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools.models import School
from tests.factories import MembershipFactory
from tests.images import PNG, image_bytes

pytestmark = pytest.mark.django_db

SETTINGS = "/api/school/settings/"
LOGO = "/api/school/settings/logo/"
PUBLIC_LOGO = "/api/school/logo/"
MONOCHROME_LOGO = "/api/school/settings/logo-monochrome/"
PUBLIC_MONOCHROME_LOGO = "/api/school/logo-monochrome/"
SVG = b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>'


def journal(school) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.order_by("created_at", "id"))


def upload(client, content: bytes, name: str = "logo.png", url: str = LOGO):
    return client.client.post(
        url, {"logo": SimpleUploadedFile(name, content)}, HTTP_HOST=client.host
    )


# Lire et changer


def test_head_reads_the_settings(api, school, head):
    response = api(head).get(SETTINGS)

    assert response.status_code == 200
    assert response.json() == {
        "code": "alpha",
        "name": "École Alpha (fictive)",
        "official_name": "",
        "primary_color": "#0B5FCC",
        "text_color": "#FFFFFF",
        "logo": None,
        "logo_monochrome": None,
        "stamp": None,
        "head_name": "",
        "head_title": "",
        "head_signature": None,
        "epst_code": "",
        "province": "",
        "city": "",
        "commune": "",
        "regime": "",
        "timezone": "Africa/Lubumbashi",
        "enabled_currencies": ["USD", "CDF"],
        "default_currency": "USD",
        "receipt": {
            "printer": "thermal_80",
            "sheet_size": "half",
            "header": "",
            "footer": "",
        },
        "alerts": {
            "difference_minor": {"USD": 1000, "CDF": 20000},
            "cancellations_per_day": 3,
            "closing_time": "18:00",
        },
        # Relances aux parents : rien ne part tant que l'école ne les a pas activées.
        "reminders": {"enabled": False, "days_before": 3, "overdue_every_days": 7},
        # Téléphone du titulaire : caché aux parents tant que l'école ne l'a pas choisi.
        "portal": {"teacher_phone": False},
        "grading": {"entry": "detailed"},
        "pass_rules": {
            "pass_percent": 50,
            "course_pass_percent": 50,
            "resit_mode": "band",
            "resit_floor_percent": 45,
            "resit_failures_to_fail": 2,
        },
    }


def test_head_changes_the_colour(api, school, head):
    response = api(head).patch(SETTINGS, {"primary_color": "#f2c94c"})

    assert response.status_code == 200
    assert response.json()["primary_color"] == "#F2C94C"
    assert response.json()["text_color"] == "#101828"
    school.refresh_from_db()
    assert school.primary_color == "#F2C94C"
    [entry] = journal(school)
    assert entry.action == Action.SCHOOL_UPDATED
    assert entry.actor == head
    assert entry.before == {"primary_color": "#0B5FCC"}
    assert entry.after == {"primary_color": "#F2C94C"}


def test_an_unreadable_colour_is_refused_with_a_proposal(api, school, head):
    response = api(head).patch(SETTINGS, {"primary_color": "#FF0000"})

    assert response.status_code == 400
    [error] = response.json()["fields"]["primary_color"]
    assert error["code"] == "unreadable_color"
    assert "#FF0F0F" in error["detail"]
    school.refresh_from_db()
    assert school.primary_color == "#0B5FCC"
    assert journal(school) == []


def test_other_settings(api, school, head):
    response = api(head).patch(
        SETTINGS,
        {
            "name": "Alpha",
            "official_name": "Complexe scolaire Alpha",
            "timezone": "Africa/Kinshasa",
            "enabled_currencies": ["CDF", "USD", "CDF"],
            "default_currency": "CDF",
        },
    )

    assert response.status_code == 200, response.content
    school.refresh_from_db()
    assert school.name == "Alpha"
    assert school.timezone == "Africa/Kinshasa"
    assert school.enabled_currencies == ["USD", "CDF"]
    assert school.default_currency == "CDF"


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"enabled_currencies": ["USD"], "default_currency": "CDF"}, "default_currency"),
        ({"enabled_currencies": ["CDF"]}, "default_currency"),
        ({"enabled_currencies": []}, "enabled_currencies"),
        ({"enabled_currencies": ["EUR"]}, "enabled_currencies"),
        ({"timezone": "Goma"}, "timezone"),
        ({"primary_color": "bleu"}, "primary_color"),
        ({"name": ""}, "name"),
        ({"receipt": {"printer": "laser"}}, "receipt"),
        ({"receipt": {"sheet_size": "a6"}}, "receipt"),
        ({"receipt": {"header": "1\n2\n3\n4\n5\n6"}}, "receipt"),
        ({"alerts": {"difference_minor": {"EUR": 500}}}, "alerts"),
        ({"alerts": {"difference_minor": {"USD": -1}}}, "alerts"),
        ({"alerts": {"closing_time": "25:00"}}, "alerts"),
        ({"reminders": {"overdue_every_days": 0}}, "reminders"),
    ],
)
def test_invalid_settings_are_refused(api, school, head, data, field):
    response = api(head).patch(SETTINGS, data)

    assert response.status_code == 400
    assert any(name.split(".")[0] == field for name in response.json()["fields"])
    assert journal(school) == []


def test_receipt_settings_are_merged_and_journaled(api, school, head):
    first = api(head).patch(SETTINGS, {"receipt": {"printer": "sheet", "sheet_size": "third"}})
    response = api(head).patch(
        SETTINGS, {"receipt": {"header": " Av. du Lac 1 \n+243 000 000 000 "}}
    )

    assert first.status_code == 200, first.content
    assert response.status_code == 200, response.content
    receipt = {
        "printer": "sheet",
        "sheet_size": "third",
        "header": "Av. du Lac 1\n+243 000 000 000",
        "footer": "",
    }
    assert response.json()["receipt"] == receipt
    # Le caissier les lit avec l'école (publique : ils sont imprimés sur chaque reçu).
    assert api(head).get("/api/school/").json()["receipt"] == receipt
    school.refresh_from_db()
    assert school.settings["receipt"] == receipt
    updates = [log for log in journal(school) if log.action == Action.SCHOOL_UPDATED]
    assert [(log.before, log.after) for log in updates] == [
        (
            {"receipt_printer": "thermal_80", "receipt_sheet_size": "half"},
            {"receipt_printer": "sheet", "receipt_sheet_size": "third"},
        ),
        (
            {"receipt_header": ""},
            {"receipt_header": "Av. du Lac 1\n+243 000 000 000"},
        ),
    ]


def test_reminders_to_parents_are_merged_and_journaled(api, school, head):
    api(head).patch(SETTINGS, {"reminders": {"days_before": 5}})
    response = api(head).patch(SETTINGS, {"reminders": {"enabled": True}})

    assert response.status_code == 200, response.content
    reminders = {"enabled": True, "days_before": 5, "overdue_every_days": 7}
    assert response.json()["reminders"] == reminders
    school.refresh_from_db()
    assert school.settings["reminders"] == reminders
    updates = [log for log in journal(school) if log.action == Action.SCHOOL_UPDATED]
    assert [(log.before, log.after) for log in updates] == [
        ({"reminder_days_before": 3}, {"reminder_days_before": 5}),
        ({"reminder_enabled": False}, {"reminder_enabled": True}),
    ]


def test_alert_thresholds_are_merged_and_journaled(api, school, head):
    first = api(head).patch(SETTINGS, {"alerts": {"difference_minor": {"CDF": 50000}}})
    response = api(head).patch(
        SETTINGS, {"alerts": {"cancellations_per_day": 5, "closing_time": "17:30"}}
    )

    assert first.status_code == 200, first.content
    assert response.status_code == 200, response.content
    alerts = {
        "difference_minor": {"USD": 1000, "CDF": 50000},
        "cancellations_per_day": 5,
        "closing_time": "17:30",
    }
    assert response.json()["alerts"] == alerts
    school.refresh_from_db()
    assert school.settings["alerts"] == alerts
    updates = [log for log in journal(school) if log.action == Action.SCHOOL_UPDATED]
    assert [(log.before, log.after) for log in updates] == [
        ({"alert_difference_cdf": 20000}, {"alert_difference_cdf": 50000}),
        (
            {"alert_cancellations_per_day": 3, "alert_closing_time": "18:00"},
            {"alert_cancellations_per_day": 5, "alert_closing_time": "17:30"},
        ),
    ]


def test_the_code_is_not_changed_by_the_school(api, school, head):
    response = api(head).patch(SETTINGS, {"code": "piratee"})

    assert response.status_code == 200
    school.refresh_from_db()
    assert school.code == "alpha"


# Qui peut


@pytest.mark.parametrize(
    "role", ["cashier", "accountant", "secretary", "study_director", "promoter", "teacher"]
)
def test_other_roles_cannot(api, school, role):
    user = MembershipFactory(school=school, roles=[role]).user

    assert api(user).get(SETTINGS).status_code == 403
    assert api(user).patch(SETTINGS, {"name": "Piratée"}).status_code == 403
    assert upload(api(user), PNG).status_code == 403
    assert upload(api(user), PNG, url=MONOCHROME_LOGO).status_code == 403


def test_anonymous_is_refused(api, school):
    assert api().get(SETTINGS).json()["code"] == "not_authenticated"


def test_two_factor_authentication_is_required(api, head):
    assert api(head, mfa=False).get(SETTINGS).json()["code"] == "totp_required"


def test_not_at_the_platform_address(api, head):
    assert api(head, host="localhost").get(SETTINGS).json()["code"] == "school_not_found"


# Isolation des écoles


def test_a_school_changes_only_its_own_settings(api, school, other_school, head, other_head):
    # Directeur de beta à l'adresse d'alpha : refusé.
    assert api(other_head).patch(SETTINGS, {"name": "Piratée"}).status_code == 403

    response = api(other_head, host="beta.localhost").patch(SETTINGS, {"name": "Beta"})

    assert response.status_code == 200
    school.refresh_from_db()
    other_school.refresh_from_db()
    assert (school.name, other_school.name) == ("École Alpha (fictive)", "Beta")
    assert journal(school) == []
    assert len(journal(other_school)) == 1


def test_each_address_serves_its_own_logo(api, client, school, other_school, head):
    assert upload(api(head), PNG).status_code == 200

    alpha = client.get(PUBLIC_LOGO, HTTP_HOST="alpha.localhost")
    beta = client.get(PUBLIC_LOGO, HTTP_HOST="beta.localhost")

    assert alpha.status_code == 200
    assert b"".join(alpha.streaming_content).startswith(b"\x89PNG")
    assert beta.status_code == 404
    assert beta.json()["code"] == "no_logo"


# Logo


def test_head_uploads_a_logo(api, client, school, head):
    text = PngInfo()
    text.add_text("Author", "Graphiste fictif")
    response = upload(api(head), image_bytes("PNG", pnginfo=text))

    assert response.status_code == 200, response.content
    logo = response.json()["logo"]
    assert logo.startswith("/api/school/logo/?v=")
    public = client.get(logo, HTTP_HOST="alpha.localhost")
    assert public.status_code == 200
    assert public["Content-Type"] == "image/png"
    assert public["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in public["Content-Security-Policy"]
    # Ré-encodé à l'envoi : ce qui est servi n'a plus les métadonnées du fichier envoyé.
    assert b"Graphiste fictif" not in b"".join(public.streaming_content)
    assert client.get("/api/school/", HTTP_HOST="alpha.localhost").json()["logo"] == logo
    assert journal(school)[-1].action == Action.SCHOOL_LOGO_CHANGED


def test_svg_is_refused_and_one_sent_before_stays_served_without_scripts(api, client, school, head):
    # Avant S.4, une école pouvait envoyer un SVG : il reste affiché, sans rien pouvoir exécuter.
    school.logo.save("logo.svg", ContentFile(SVG), save=True)
    public = client.get(PUBLIC_LOGO, HTTP_HOST="alpha.localhost")
    assert public["Content-Type"] == "image/svg+xml"
    assert "sandbox" in public["Content-Security-Policy"]

    for url in (LOGO, MONOCHROME_LOGO):
        response = upload(api(head), SVG, "logo.svg", url=url)
        assert response.status_code == 400
        assert response.json()["fields"]["logo"][0]["code"] == "image_type"


def test_the_content_decides_not_the_name(api, client, school, head):
    assert upload(api(head), PNG, "logo.svg").status_code == 200

    school.refresh_from_db()
    assert school.logo.name.endswith(".png")


@pytest.mark.parametrize(
    "content",
    [
        image_bytes("GIF"),
        b"%PDF-1.7",
        b"<html><body>logo</body></html>",
        PNG[:40],
        PNG + bytes(1024 * 1024),
        image_bytes("PNG", (2049, 16)),
    ],
)
def test_other_files_are_refused(api, school, head, content):
    response = upload(api(head), content, "logo.png")

    assert response.status_code == 400
    assert "logo" in response.json()["fields"]
    school.refresh_from_db()
    assert not school.logo


def test_head_removes_the_logo(api, client, school, head):
    upload(api(head), PNG)

    response = api(head).delete(LOGO)

    assert response.status_code == 200
    assert response.json()["logo"] is None
    assert client.get(PUBLIC_LOGO, HTTP_HOST="alpha.localhost").status_code == 404


def test_black_and_white_logo(api, client, school, head):
    response = upload(api(head), PNG, url=MONOCHROME_LOGO)

    assert response.status_code == 200, response.content
    address = response.json()["logo_monochrome"]
    assert address.startswith(f"{PUBLIC_MONOCHROME_LOGO}?v=")
    assert response.json()["logo"] is None
    public = client.get(address, HTTP_HOST="alpha.localhost")
    assert public["Content-Type"] == "image/png"
    assert "sandbox" in public["Content-Security-Policy"]
    # Seulement à l'adresse de son école.
    assert client.get(PUBLIC_MONOCHROME_LOGO, HTTP_HOST="beta.localhost").status_code == 404
    assert journal(school)[-1].after == {"logo_monochrome": True}

    assert api(head).delete(MONOCHROME_LOGO).json()["logo_monochrome"] is None
    assert client.get(PUBLIC_MONOCHROME_LOGO, HTTP_HOST="alpha.localhost").status_code == 404
    assert journal(school)[-1].after == {"logo_monochrome": False}


def test_logo_address_without_school(client, school):
    response = client.get(PUBLIC_LOGO, HTTP_HOST="localhost")

    assert response.status_code == 404
    assert response.json()["code"] == "school_not_found"


def test_suspended_school_serves_nothing(client, school):
    school.status = School.Status.SUSPENDED
    school.save()

    assert client.get(PUBLIC_LOGO, HTTP_HOST="alpha.localhost").status_code == 403


def test_old_receipt_settings_are_read_as_one_receipt_per_sheet(school):
    from apps.schools.receipts import receipt_settings

    school.settings = {"receipt": {"printer": "sheet", "sheet_size": "half", "copies": 2}}

    assert "copies" not in receipt_settings(school.settings)
