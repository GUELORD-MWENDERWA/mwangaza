"""Console de l'IA et « Crédits IA » de la Gestion (IA.1.2) : droits de l'équipe, modes réel et
démonstration jamais mêlés, crédits exacts en entiers, journal de la plateforme, et une école
qui ne lit jamais les crédits d'une autre."""

import pytest

from apps.accounts.modules import ALL_MODULES
from apps.ai import prices, services
from apps.ai.models import AiBalance, AiPlatformMonth, AiSettings
from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.core.tenancy import use_school
from apps.schools.models import School
from tests.factories import MembershipFactory, SchoolFactory, UserFactory

from .test_ai import USE, grant, staff

pytestmark = pytest.mark.django_db
CONSOLE = "admin.localhost"
DEMO = {"HTTP_X_CONSOLE_MODE": "demo"}


@pytest.fixture
def console(api, platform_admin):
    def make(user=None, *, demo=False):
        return api(user or platform_admin, host=CONSOLE, headers=DEMO if demo else None)

    return make


def member(*roles):
    return UserFactory(is_platform_admin=True, platform_roles=list(roles))


def spend(school, micro):
    with use_school(school):
        balance = AiBalance.objects.get(school=school, month=services.month_start())
        balance.spent_micro = micro
        balance.save()


def test_only_the_ai_right_opens_the_page(console, api):
    assert console(member("communication")).get("/api/console/ai/").status_code == 403
    assert console(member("commercial")).get("/api/console/ai/").status_code == 403
    for role in ("technical", "finance", "owner"):
        assert console(member(role)).get("/api/console/ai/").status_code == 200
    # Hors de la console, ces points n'existent pas.
    assert api(member("owner")).get("/api/console/ai/").status_code == 404


def test_real_and_demo_spaces_never_mix(console, school, platform_admin):
    demo = SchoolFactory(code="demo-ia", environment=School.Environment.DEMO)
    grant(school, platform_admin, credits=300)
    grant(demo, platform_admin, credits=900)
    live_page = console().get("/api/console/ai/").json()
    demo_page = console(demo=True).get("/api/console/ai/").json()
    assert [row["code"] for row in live_page["schools"]] == ["alpha"]
    assert [row["code"] for row in demo_page["schools"]] == ["demo-ia"]
    # Réglages et plafond : le réel seulement ; rien ne se change depuis la démonstration.
    assert live_page["settings"]["monthly_cap_micro"] == AiSettings().monthly_cap_micro
    assert demo_page["settings"] is None and demo_page["cap_micro"] is None
    assert console(demo=True).patch("/api/console/ai/", {"enabled": False}).status_code == 404
    price = {"input": 1, "output": 1, "cache_read": 1}
    path = "/api/console/ai/prices/claude-opus-5-5/"
    assert console(demo=True).put(path, price).status_code == 404
    # La fiche d'une école de l'autre mode n'existe pas.
    assert console().get(f"/api/console/ai/schools/{demo.pk}/").status_code == 404
    assert console(demo=True).get(f"/api/console/ai/schools/{school.pk}/").status_code == 404
    top_up = console().post(f"/api/console/ai/schools/{demo.pk}/top-up/", {"credits": 5})
    assert top_up.status_code == 404


def test_credits_are_exact_and_each_change_is_logged(console, school, platform_admin):
    path = f"/api/console/ai/schools/{school.pk}/"
    body = {"uses": [USE], "monthly_credits": 2_000, "paused": False}
    assert console().put(path, body).status_code == 200
    services.top_up(school, actor=platform_admin, credits=1)  # crée le mois
    spend(school, 1_680_500)  # 1 680,5 crédits : on n'arrondit jamais en faveur de l'école
    card = console().post(f"{path}top-up/", {"credits": 500}).json()
    assert (card["granted_credits"], card["spent_credits"]) == (2_501, 1_680)
    assert card["remaining_credits"] == 820  # (2 501 000 - 1 680 500) // 1 000
    assert [row["code"] for row in card["uses"] if row["granted"]] == [USE]
    # Baisser les crédits par mois retire la différence du mois en cours.
    card = console().put(path, {**body, "monthly_credits": 1_000}).json()
    assert card["granted_credits"] == 1_501
    actions = set(PlatformAuditLog.objects.values_list("action", flat=True))
    assert {PlatformAction.AI_ALLOWANCE_CHANGED, PlatformAction.AI_TOP_UP} <= actions
    page = console().get("/api/console/ai/").json()
    row = page["schools"][0]
    assert (row["granted_credits"], row["remaining_credits"]) == (1_501, 0)
    assert page["alerts"][0]["kind"] == "school_credits"


def test_a_use_needs_its_host_module(console, school):
    school.modules = [code for code in ALL_MODULES if code != "academics"]
    school.save()
    body = {"uses": ["course_grid_from_pdf"], "monthly_credits": 10, "paused": False}
    response = console().put(f"/api/console/ai/schools/{school.pk}/", body)
    assert response.status_code == 400
    assert response.json()["code"] == "ai_module_missing"


def test_platform_settings_use_and_price_are_checked_and_logged(console):
    page = console().patch("/api/console/ai/", {"monthly_cap_micro": 80_000_000}).json()
    assert page["settings"]["monthly_cap_micro"] == 80_000_000
    entry = PlatformAuditLog.objects.get(action=PlatformAction.AI_SETTINGS_CHANGED)
    assert entry.before == {"monthly_cap_micro": 50_000_000}
    use_path = f"/api/console/ai/uses/{USE}/"
    assert console().put(use_path, {"model": "gpt-4"}).status_code == 400
    assert console().put(use_path, {"max_output_tokens": 10**6}).status_code == 400
    page = console().put(use_path, {"model": "claude-haiku-5-5"}).json()
    row = next(row for row in page["uses"] if row["code"] == USE)
    assert (row["model"], row["changed"], row["max_output_tokens"]) == (
        "claude-haiku-5-5",
        True,
        3_000,
    )
    assert services.resolve_use(services.platform_settings(), USE).model == "claude-haiku-5-5"
    page = console().put(use_path, {}).json()  # retour au catalogue
    assert not next(row for row in page["uses"] if row["code"] == USE)["changed"]
    price = {"input": 3_000_000, "output": 15_000_000, "cache_read": 300_000}
    console().put("/api/console/ai/prices/claude-sonnet-5-5/", price)
    table = services.price_table(services.platform_settings())["claude-sonnet-5-5"]
    assert table[prices.CACHE_WRITE] == 3_750_000  # 1,25 fois l'entrée, en entiers
    assert console().put("/api/console/ai/prices/inconnu/", price).status_code == 400


def test_school_reads_only_its_own_credits(api, school, other_school, platform_admin):
    grant(school, platform_admin, credits=300)
    grant(other_school, platform_admin, credits=9_000, paused=True)
    reader = staff(school, ["ai.use", "timetable.manage"])
    data = api(reader).get("/api/ai/credits/").json()
    assert (data["granted_credits"], data["blocked"]) == (300, "")
    assert [use["code"] for use in data["uses"]] == [USE]
    # Sans `school.configure` ni `ai.use` : refusé.
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    assert api(teacher).get("/api/ai/credits/").status_code == 403
    # Bouton grisé avec la raison : pause, crédits sous le coût d'une réponse, plafond.
    head = MembershipFactory(school=other_school, roles=["head"]).user
    data = api(head, host="beta.localhost").get("/api/ai/credits/").json()
    assert (data["granted_credits"], data["blocked"]) == (9_000, "ai_paused")
    grant(school, platform_admin, credits=0)
    assert api(reader).get("/api/ai/credits/").json()["uses"][0]["blocked"] == "ai_no_credits"
    AiPlatformMonth.objects.create(month=services.month_start(), spent_micro=10**12)
    assert api(reader).get("/api/ai/credits/").json()["blocked"] == "ai_cap_reached"
