"""Demandes de démonstration du site public (WEB.1d) : formulaire sans JavaScript, spam, doublon,
alerte au super-admin, console réservée au super-admin, effacement au bout d'un an ; adresse et
réseaux de la plateforme lus par le site."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.core import demo_requests
from apps.core.models import DemoRequest, PlatformSettings
from apps.core.tests.test_site import structured_data
from apps.notifications import console
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

PAGE = "/demonstration/"
CONSOLE = "admin.localhost"
REQUESTS = "/api/console/demo-requests/"
FORM = {
    "name": "MUHINDO KAKULE Jean-Paul",
    "role": "prefect",
    "school_name": "Institut Les Volcans",
    "town": "Goma",
    "phone": "097 123 45 67",
    "size": "300-800",
    "email": "",
    "message": "Voir la caisse.",
    "consent": "on",
    "site_web": "",
}


@pytest.fixture(autouse=True)
def alerts(monkeypatch):
    """Compteur d'adresses vidé ; alertes sur l'écran relevées au lieu d'être envoyées."""
    cache.clear()
    sent = []
    monkeypatch.setattr(console, "alert", lambda *args: sent.append(args))
    return sent


def post(client, ip="10.0.0.1", **changes):
    return client.post(PAGE, {**FORM, **changes}, REMOTE_ADDR=ip)


def test_a_request_is_kept_for_the_console_and_alerts_the_admin_once(
    client, settings, alerts, mailoutbox, django_capture_on_commit_callbacks
):
    settings.EMAIL_HOST, settings.EMAIL_HOST_USER = "smtp.example.com", "contact@example.com"
    settings.ALERT_EMAILS = ["patron@example.com"]

    with django_capture_on_commit_callbacks(execute=True):
        response = post(client)
    assert response.status_code == 200
    assert 'name="consent"' not in response.content.decode()  # la carte « merci »
    request = DemoRequest.objects.get()
    assert (request.phone, request.language, request.status) == ("+243971234567", "fr", "new")
    assert alerts == [
        (console.DEMO_REQUEST, request.pk, "Institut Les Volcans, Goma | MUHINDO KAKULE Jean-Paul")
    ]
    (email,) = mailoutbox
    assert email.to == ["patron@example.com"]
    assert "Institut Les Volcans" in email.subject
    assert "+243 97 123 45 67" in email.body

    # Le même numéro dans les 24 heures (double clic, retour arrière) : ni demande ni alerte.
    with django_capture_on_commit_callbacks(execute=True):
        assert post(client, phone="+243971234567", message="Encore").status_code == 200
    assert DemoRequest.objects.count() == 1
    assert len(alerts) == 1 and len(mailoutbox) == 1


def test_invalid_requests_and_robots_leave_nothing(client, alerts):
    # Téléphone incomplet ou consentement absent : le formulaire revient avec l'erreur.
    for changes in ({"phone": "097 12"}, {"consent": ""}, {"school_name": ""}):
        response = post(client, **changes)
        assert response.status_code == 200
        assert 'aria-invalid="true"' in response.content.decode()
    # Champ caché rempli (robot) : « merci », rien de gardé.
    response = post(client, site_web="https://spam.example")
    assert 'name="consent"' not in response.content.decode()
    assert not DemoRequest.objects.exists() and not alerts


def test_six_requests_in_an_hour_from_one_address_are_refused(client):
    for n in range(5):
        assert post(client, phone=f"09712345{n:02d}").status_code == 200
    refused = post(client, phone="0971234599")
    assert refused.status_code == 429
    assert DemoRequest.objects.count() == 5
    # Une autre connexion n'est pas gênée.
    assert post(client, ip="10.0.0.2", phone="0971234599").status_code == 200
    assert DemoRequest.objects.count() == 6


def test_a_chat_message_is_kept_and_alerts_the_admin(client, alerts):
    chat = {"name": "Papa Gloire", "phone": "0971234500", "message": "Prix pour 400 élèves ?"}
    assert client.post("/chat/", {**chat, "site_web": "x"}).json() == {"sent": True}  # robot
    assert not DemoRequest.objects.exists() and not alerts

    assert client.post("/en/chat/", chat, REMOTE_ADDR="10.0.0.1").json() == {"sent": True}
    request = DemoRequest.objects.get()
    assert (request.source, request.language, request.phone) == ("chat", "en", "+243971234500")
    assert request.school_name == "" and alerts[0][:2] == (console.DEMO_REQUEST, request.pk)

    # Téléphone incomplet, message vide : refusé, rien de gardé ; au-delà de 5 par heure : 429.
    assert client.post("/chat/", {**chat, "phone": "097"}).status_code == 400
    assert client.post("/chat/", {**chat, "message": ""}).status_code == 400
    assert client.get("/chat/").status_code == 405
    for _n in range(4):
        assert client.post("/chat/", chat, REMOTE_ADDR="10.0.0.1").status_code == 200
    assert client.post("/chat/", chat, REMOTE_ADDR="10.0.0.1").status_code == 429
    assert DemoRequest.objects.count() == 5


def test_only_the_platform_admin_follows_requests_at_the_console(api, platform_admin, head):
    new = DemoRequest.objects.create(
        name="KAVIRA Esther",
        role="promoter",
        school_name="Mont Goma",
        town="Goma",
        phone="+243971234560",
    )
    DemoRequest.objects.create(
        name="BAHATI Patrick",
        role="head",
        school_name="Kivu Lumière",
        town="Gisenyi",
        phone="+243971234561",
        status="contacted",
    )
    item = f"{REQUESTS}{new.pk}/"
    assert api(None, host=CONSOLE).get(REQUESTS).status_code == 403
    assert api(head, host=CONSOLE).get(REQUESTS).status_code == 403
    assert api(platform_admin, host=CONSOLE, mfa=False).get(REQUESTS).status_code == 403
    assert api(head, host=CONSOLE).delete(item).status_code == 403
    for host in ("alpha.localhost", "localhost"):
        assert api(platform_admin, host=host).get(REQUESTS).status_code == 404

    admin = api(platform_admin, host=CONSOLE)
    listed = admin.get(f"{REQUESTS}?status=new").json()
    assert [r["school_name"] for r in listed["results"]] == ["Mont Goma"]
    assert admin.get(REQUESTS).json()["count"] == 2
    # Seuls le suivi et la note changent ; ce que l'école a écrit reste tel quel.
    changed = admin.patch(item, {"status": "trial", "notes": "Espace ouvert", "name": "X"}).json()
    assert (changed["status"], changed["notes"], changed["name"]) == (
        "trial",
        "Espace ouvert",
        "KAVIRA Esther",
    )
    assert admin.patch(item, {"status": "lost"}).status_code == 400
    # La personne demande l'effacement.
    assert admin.delete(item).status_code == 204
    assert not DemoRequest.objects.filter(pk=new.pk).exists()


def test_requests_are_erased_a_year_after_they_were_sent():
    fields = {"name": "A", "role": "other", "school_name": "B", "town": "Goma"}
    old = DemoRequest.objects.create(**fields, phone="+243971234570")
    recent = DemoRequest.objects.create(**fields, phone="+243971234571")
    DemoRequest.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=366))
    DemoRequest.objects.filter(pk=recent.pk).update(created_at=timezone.now() - timedelta(days=364))
    assert demo_requests.purge() == 1
    assert list(DemoRequest.objects.all()) == [recent]


def test_address_and_networks_of_the_identity_reach_the_site(api, platform_admin, client):
    admin = api(platform_admin, host=CONSOLE)
    wrong = admin.patch("/api/console/platform/", {"linkedin_url": "https://facebook.com/x"})
    assert wrong.status_code == 400
    assert (
        admin.patch(
            "/api/console/platform/",
            {"address": "Avenue du Lac 12", "facebook_url": "https://www.facebook.com/lumiere"},
        ).status_code
        == 200
    )

    html = client.get(PAGE).content.decode()
    assert "Avenue du Lac 12, Goma, Nord-Kivu" in html
    assert '<a href="https://www.facebook.com/lumiere" rel="me noopener">Facebook</a>' in html
    assert "LinkedIn" not in html  # lien vide : caché
    organization = structured_data(html)["Organization"]
    assert organization["sameAs"] == ["https://www.facebook.com/lumiere"]
    assert organization["address"]["streetAddress"] == "Avenue du Lac 12"

    platform = PlatformSettings.load()
    platform.city = platform.region = platform.address = ""
    platform.save()
    assert "Nord-Kivu, RDC" not in client.get("/").content.decode()


# --- Suivi commercial (CON.3) ---


def prospect(**fields) -> DemoRequest:
    fields = {"name": "A", "role": "head", "school_name": "Kivu", "town": "Goma", **fields}
    return DemoRequest.objects.create(phone="+243971234570", **fields)


def sales_member(role="commercial"):
    return UserFactory(is_platform_admin=True, platform_roles=[role])


def test_sales_follow_prospects_but_other_roles_cannot(api):
    item = f"{REQUESTS}{prospect().pk}/"
    sales = api(sales_member(), host=CONSOLE)
    assert sales.patch(item, {"status": "contacted"}).status_code == 200
    for role in ("support", "communication", "finance", "technical"):
        other = api(sales_member(role), host=CONSOLE)
        assert other.get(REQUESTS).status_code == 403
        assert other.patch(item, {"status": "signed"}).status_code == 403


def test_a_lost_prospect_needs_a_reason_and_the_reason_goes_with_the_step(api):
    item = f"{REQUESTS}{prospect().pk}/"
    sales = api(sales_member(), host=CONSOLE)
    assert sales.patch(item, {"status": "lost"}).status_code == 400
    assert sales.patch(item, {"status": "lost", "lost_reason": " "}).status_code == 400
    lost = sales.patch(item, {"status": "lost", "lost_reason": "Trop cher"}).json()
    assert (lost["status"], lost["lost_reason"]) == ("lost", "Trop cher")
    # Elle revient dans le suivi : le motif ne reste pas.
    back = sales.patch(item, {"status": "contacted"}).json()
    assert back["lost_reason"] == ""


def test_only_a_sales_member_can_be_responsible_and_late_follow_ups_are_flagged(api):
    seller, support = sales_member(), sales_member("support")
    request = prospect(follow_up_on=timezone.localdate() - timedelta(days=1))
    item = f"{REQUESTS}{request.pk}/"
    admin = api(sales_member("owner"), host=CONSOLE)
    assert admin.patch(item, {"assignee": str(support.pk)}).status_code == 400
    data = admin.patch(item, {"assignee": str(seller.pk)}).json()
    assert (data["assignee"], data["overdue"]) == (str(seller.pk), True)
    assert {row["id"] for row in admin.get(f"{REQUESTS}assignees/").json()} >= {str(seller.pk)}
    assert str(support.pk) not in {r["id"] for r in admin.get(f"{REQUESTS}assignees/").json()}
    signed = admin.patch(item, {"status": "signed"}).json()
    assert signed["overdue"] is False  # signée : plus à relancer


def test_the_reminder_goes_to_the_assignee_on_the_day_only(monkeypatch):
    seller = sales_member()
    today = timezone.localdate()
    due = prospect(assignee=seller, follow_up_on=today, school_name="Aujourd'hui")
    prospect(assignee=seller, follow_up_on=today + timedelta(days=1), school_name="Demain")
    prospect(assignee=seller, follow_up_on=today, status="lost", school_name="Perdue")
    prospect(follow_up_on=today, school_name="Sans responsable")
    sent = []
    monkeypatch.setattr(console, "alert", lambda *args, **kw: sent.append((args, kw)))

    assert demo_requests.remind_follow_ups() == 1
    assert sent == [((console.FOLLOW_UP, due.pk, "Aujourd'hui"), {"concerned": seller.pk})]


def test_a_follow_up_alert_reaches_only_its_assignee():
    from apps.notifications.models import PushSubscription

    seller, other = sales_member(), sales_member()
    for user in (seller, other, sales_member("owner")):
        PushSubscription.objects.create(
            user=user,
            app=PushSubscription.CONSOLE,
            endpoint=f"https://push.example/{user.pk}",
            p256dh="k",
            auth="a",
        )
    reached = console.subscriptions(console.FOLLOW_UP, seller.pk)
    assert [s.user_id for s in reached] == [seller.pk]


def test_creating_a_trial_from_a_prospect_links_it_and_moves_it_to_trial(api):
    request = prospect()
    body = {
        "code": "kivu-essai",
        "name": "Institut Kivu",
        "official_name": "Institut Kivu",
        "environment": "test",
        "enabled_currencies": ["USD"],
        "default_currency": "USD",
        "status": "trial",
        "head": {"phone": "0100004001", "last_name": "Kasereka", "first_name": "Dieudonné"},
        "prospect": str(request.pk),
    }
    # Le support peut ouvrir un essai mais ne gère pas les prospects : pas de lien.
    schools = "/api/console/schools/"
    assert api(sales_member("support"), host=CONSOLE).post(schools, body).status_code == 403
    assert api(sales_member(), host=CONSOLE).post(schools, body).status_code == 201
    request.refresh_from_db()
    assert (request.status, request.school_code) == ("trial", "kivu-essai")
    listed = api(sales_member(), host=CONSOLE).get(REQUESTS).json()["results"][0]
    assert listed["school_code"] == "kivu-essai"
