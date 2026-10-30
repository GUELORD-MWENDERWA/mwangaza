"""Mise en route d'une école neuve (4.20.1, C4) : `/api/school/setup/` et `…/finish/` | une
école ne coche rien avec les données d'une autre, permission `school.configure`, chaque étape
se coche seule, fin refusée tant que l'école ne peut pas encaisser, puis gardée pour de bon ;
un espace de démonstration naît déjà fini."""

from decimal import Decimal

import pytest

from apps.core.tenancy import use_school
from apps.finance import services as finance
from apps.finance.tests.test_api import setup
from apps.finance.tests.test_payments import school_with_fees
from apps.finance.tests.test_prior_payments import earlier
from apps.schools import services
from apps.schools.models import School
from apps.students import invitations
from apps.students.models import Family
from apps.students.tests.conftest import enrolled
from apps.sync.tests.test_devices import remember
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

URL = "/api/school/setup/"
FINISH = "/api/school/setup/finish/"
STEPS = ["year", "classes", "fees", "staff", "cash", "students", "prior", "invitations"]


def done(client) -> list[str]:
    return [step["key"] for step in client.get(URL).json()["steps"] if step["done"]]


def ready_to_collect(api, school, head) -> dict:
    """Tout ce qu'il faut pour encaisser : organisation, barèmes et taux, caisse, élève inscrit,
    une caissière dont l'appareil est connu."""
    data = school_with_fees(school, head)
    cashier = MembershipFactory(school=school, roles=["cashier"]).user
    assert remember(api(cashier, host=f"{school.code}.localhost")).status_code == 201
    return data


def test_a_new_school_has_nothing_done_whatever_another_school_did(
    api, school, other_school, head, other_head
):
    beta = ready_to_collect(api, other_school, other_head)
    earlier(other_school, other_head, beta["enrollment"], "100")
    with use_school(other_school):
        invitations.letters(Family.objects.all(), actor=other_head, preview=False)

    theirs = api(other_head, host="beta.localhost").get(URL).json()
    mine = api(head).get(URL).json()

    assert [step["key"] for step in theirs["steps"] if step["done"]] == STEPS
    assert [step["key"] for step in mine["steps"]] == STEPS
    assert not any(step["done"] for step in mine["steps"])
    assert [step["key"] for step in mine["steps"] if step["optional"]] == ["prior", "invitations"]
    assert (mine["ready"], mine["finished_at"]) == (False, None)
    assert api().get("/api/school/").json()["setup_done"] is False


def test_only_who_configures_the_school_reads_and_finishes_the_list(
    api, school, cashier, other_head
):
    for user in (cashier, other_head):
        assert api(user).get(URL).status_code == 403
        assert api(user).post(FINISH).status_code == 403
    school.refresh_from_db()
    assert school.setup_completed_at is None


def test_each_step_ticks_itself(api, school, head):
    client = api(head)

    # Deux devises : les frais ne sont prêts qu'avec le taux de l'année.
    data = setup(school, head)
    assert done(client) == ["year", "classes"]
    with use_school(school):
        finance.set_exchange_rate(actor=head, academic_year=data["year"], rate=Decimal("2850"))
        finance.create_cash_register(actor=head, name="Caisse 1", code="C1")
    assert done(client) == ["year", "classes", "fees"]

    # Une caisse ne suffit pas : il faut un compte qui encaisse, connecté une fois sur un appareil.
    cashier = MembershipFactory(school=school, roles=["cashier"]).user
    remember(client)
    assert done(client) == ["year", "classes", "fees", "staff"]
    remember(api(cashier))
    assert done(client) == ["year", "classes", "fees", "staff", "cash"]
    assert client.get(URL).json()["ready"] is False

    student = enrolled(school, head, data["group"])
    assert done(client) == STEPS[:6]
    assert client.get(URL).json()["ready"] is True

    with use_school(school):
        enrollment = student.enrollments.get()
        invitations.letters(Family.objects.all(), actor=head, preview=False)
    earlier(school, head, enrollment, "50")
    assert done(client) == STEPS


def test_finishing_waits_until_the_school_can_collect_then_is_kept_for_good(api, school, head):
    client = api(head)

    refused = client.post(FINISH)

    assert (refused.status_code, refused.json()["code"]) == (409, "setup_incomplete")
    school.refresh_from_db()
    assert school.setup_completed_at is None

    ready_to_collect(api, school, head)
    finished = client.post(FINISH)

    assert finished.status_code == 200
    school.refresh_from_db()
    when = school.setup_completed_at
    assert when is not None and finished.json()["finished_at"] is not None
    assert api().get("/api/school/").json()["setup_done"] is True
    # Rejouée : même date. La liste n'est plus calculée.
    assert client.post(FINISH).status_code == 200
    school.refresh_from_db()
    assert school.setup_completed_at == when
    assert client.get(URL).json()["steps"] == []


def test_a_demonstration_space_is_born_finished(platform_admin):
    demo = services.open_space(
        School(code="salon", name="Salon (fictif)", environment=School.Environment.DEMO),
        actor=platform_admin,
    )
    trial = services.open_space(
        School(code="essai", name="Essai (fictif)", environment=School.Environment.TEST),
        actor=platform_admin,
    )

    assert demo.setup_completed_at is not None
    assert trial.setup_completed_at is None
