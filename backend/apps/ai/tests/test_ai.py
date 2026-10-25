"""Socle IA (IA.1.1) : les cinq verrous (un refus ne coûte rien et n'appelle jamais l'API),
coût et cumuls en entiers, même demande = un appel, session support, alertes une seule fois,
isolation entre écoles, journal de la plateforme, purge."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Role
from apps.ai import client, prices, services
from apps.ai.models import (
    AiAllowance,
    AiBalance,
    AiCall,
    AiPlatformMonth,
    AiResult,
    AiUsageMonth,
)
from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.core.errors import BusinessError
from apps.core.ids import uuid7
from apps.core.tenancy import use_all_schools, use_school
from apps.notifications.models import Notification
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db
USE = "timetable_constraints"  # module `timetable`, droit `timetable.manage`, Opus 5.5
OPUS = prices.DEFAULT_PRICES["claude-opus-5-5"]


@pytest.fixture
def api_calls(monkeypatch):
    """L'API simulée : compte les appels réels et rend toujours les mêmes jetons."""
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return client.Reply(
            text="{}",
            stop_reason="end_turn",
            model=kwargs["model"],
            input_tokens=1_000,
            output_tokens=500,
            cache_read_tokens=2_000,
            cache_write_tokens=100,
        )

    monkeypatch.setattr(client, "complete", fake)
    return calls


@pytest.fixture
def queued(monkeypatch):
    sent = []
    monkeypatch.setattr(services, "_enqueue", lambda call, payload: sent.append((call, payload)))
    return sent


def staff(school, permissions):
    with use_school(school):
        role = Role.objects.create(name=f"IA {uuid7()}", permissions=permissions)
    return MembershipFactory(school=school, roles=[role]).user


def grant(school, admin, *, credits=100, uses=(USE,), paused=False):
    services.set_allowance(
        school, actor=admin, uses_=list(uses), monthly_credits=credits, paused=paused
    )


def ask(school, user, permissions=("ai.use", "timetable.manage"), **kwargs):
    with use_school(school):
        return services.submit(
            school=school,
            user=user,
            permissions=permissions,
            use_code=kwargs.pop("use", USE),
            request_id=kwargs.pop("request_id", uuid7()),
            system="Consignes",
            messages=[{"role": "user", "content": "M. Kambale ne vient pas le vendredi."}],
            **kwargs,
        )


def refused(school, user, **kwargs) -> str:
    with pytest.raises(BusinessError) as error:
        ask(school, user, **kwargs)
    return error.value.error.code


def test_each_lock_refuses_without_calling_the_api(school, platform_admin, api_calls, queued):
    user = staff(school, ["ai.use", "timetable.manage"])
    # Rien n'est affecté à l'école : refus du second verrou.
    assert refused(school, user) == "ai_not_available"
    grant(school, platform_admin)
    # Droit `ai.use` seul, ou droit de l'écran hôte seul : refus du troisième verrou.
    assert refused(school, user, permissions=("ai.use",)) == "ai_forbidden"
    assert refused(school, user, permissions=("timetable.manage",)) == "ai_forbidden"
    # Module hôte retiré : l'usage ne marche plus.
    school.modules = [m for m in school.modules if m != "timetable"]
    school.save()
    assert refused(school, user) == "ai_not_available"
    school.modules = [*school.modules, "timetable"]
    school.save()
    # Pause de l'école, crédits épuisés, interrupteur, plafond de la plateforme.
    grant(school, platform_admin, paused=True)
    assert refused(school, user) == "ai_paused"
    grant(school, platform_admin, credits=1)  # 1 crédit = 1 000 µ$ ; l'appel peut en coûter plus
    assert refused(school, user) == "ai_no_credits"
    grant(school, platform_admin)
    services.update_settings(actor=platform_admin, enabled=False)
    assert refused(school, user) == "ai_off"
    services.update_settings(actor=platform_admin, enabled=True, monthly_cap_micro=0)
    assert refused(school, user) == "ai_cap_reached"
    services.update_settings(actor=platform_admin, monthly_cap_micro=50_000_000)
    assert api_calls == [] and queued == []
    # Les refus sont notés, sans texte ; ils ne comptent pas dans la limite par personne.
    with use_school(school):
        assert AiCall.objects.filter(state="refused").count() == 8
    # Une entrée trop grande est refusée avant tout appel.
    with use_school(school), pytest.raises(BusinessError) as error:
        services.submit(
            school=school,
            user=user,
            permissions=("ai.use", "timetable.manage"),
            use_code=USE,
            request_id=uuid7(),
            system="x" * 20_000,
            messages=[],
        )
    assert error.value.error.code == "ai_too_large"
    # Avec tout en règle : accepté, mis en file.
    assert ask(school, user).state == "queued" and len(queued) == 1


def test_rate_limit_per_person(school, platform_admin, queued):
    user = staff(school, ["ai.use", "timetable.manage"])
    grant(school, platform_admin, credits=10_000)
    services.update_settings(actor=platform_admin, hourly_limit=2)
    ask(school, user)
    ask(school, user)
    assert refused(school, user) == "ai_rate_limited"
    # Une autre personne n'est pas touchée.
    assert ask(school, staff(school, ["ai.use", "timetable.manage"])).state == "queued"


def test_cost_and_totals_are_exact_integers(school, platform_admin, api_calls, queued):
    user = staff(school, ["ai.use", "timetable.manage"])
    grant(school, platform_admin, credits=1_000)
    call = ask(school, user)
    (_, payload) = queued[0]
    services.execute(str(call.pk), str(school.pk), payload)
    expected = prices.cost(OPUS, input_=1_000, output=500, cache_read=2_000, cache_write=100)
    # 1 000 x 4 + 500 x 20 + 2 000 x 0,2 + 100 x 5 = 4 000 + 10 000 + 400 + 500 µ$
    assert expected == 14_900
    assert len(api_calls) == 1 and api_calls[0]["model"] == "claude-opus-5-5"
    with use_school(school):
        done = AiCall.objects.get(pk=call.pk)
        assert (done.state, done.cost_micro, done.input_tokens) == ("done", expected, 1_000)
        balance = AiBalance.objects.get()
        assert (balance.granted_micro, balance.spent_micro) == (1_000_000, expected)
        usage = AiUsageMonth.objects.get(use=USE)
        assert (usage.calls, usage.cost_micro, usage.cache_tokens) == (1, expected, 2_100)
        assert services.result_of(done) == {"text": "{}", "stop_reason": "end_turn"}
    assert AiPlatformMonth.objects.get().spent_micro == expected
    # Rejouée après un arrêt du travailleur : rien ne se refait ni ne se compte deux fois.
    services.execute(str(call.pk), str(school.pk), payload)
    assert len(api_calls) == 1
    with use_school(school):
        assert AiBalance.objects.get().spent_micro == expected
        # Gardé : l'état, la part gardée, et la réponse en attente est effacée.
        kept = services.settle(AiCall.objects.get(pk=call.pk), kept=True)
        services.settle(kept, kept=False)  # une seule décision
        assert kept.state == "kept" and AiResult.objects.count() == 0
        assert AiUsageMonth.objects.get().kept == 1


def test_same_request_twice_is_one_call(school, platform_admin, queued):
    user = staff(school, ["ai.use", "timetable.manage"])
    grant(school, platform_admin)
    request_id = uuid7()
    first = ask(school, user, request_id=request_id)
    again = ask(school, user, request_id=request_id)
    assert first.pk == again.pk and len(queued) == 1
    # Le même identifiant, une autre personne : refusé, rien de lisible.
    assert refused(school, staff(school, ["ai.use"]), request_id=request_id) == (
        "ai_request_conflict"
    )


def test_support_session_is_counted_on_the_platform_not_the_school(
    school, platform_admin, api_calls, queued
):
    grant(school, platform_admin, credits=0)  # aucun crédit : l'école ne pourrait rien demander
    call = ask(school, platform_admin, permissions=(), support=True)
    services.execute(str(call.pk), str(school.pk), queued[0][1])
    with use_school(school):
        assert AiCall.objects.get(pk=call.pk).on_platform
        assert not AiBalance.objects.exists() and not AiUsageMonth.objects.exists()
    assert AiPlatformMonth.objects.get().spent_micro > 0


def test_api_failure_costs_nothing(school, platform_admin, queued, monkeypatch):
    def fail(**kwargs):
        raise client.NotConfigured

    monkeypatch.setattr(client, "complete", fail)
    user = staff(school, ["ai.use", "timetable.manage"])
    grant(school, platform_admin)
    call = ask(school, user)
    services.execute(str(call.pk), str(school.pk), queued[0][1])
    with use_school(school):
        failed = AiCall.objects.get(pk=call.pk)
        assert (failed.state, failed.cost_micro, failed.refusal) == ("error", 0, "not_configured")
        assert not AiBalance.objects.exists()


def test_alerts_are_sent_once(school, platform_admin, queued, monkeypatch):
    # Un appel qui coûte 85 000 µ$ : 85 % des 100 crédits de l'école et plus de 80 % (et 100 %)
    # d'un plafond de 80 000 µ$ pour la plateforme.
    def fake(**kwargs):
        return client.Reply(
            "{}", "end_turn", kwargs["model"], input_tokens=6_250, output_tokens=3_000
        )

    monkeypatch.setattr(client, "complete", fake)
    head = staff(school, ["roles.manage", "ai.use", "timetable.manage"])
    grant(school, platform_admin, credits=100)
    services.update_settings(actor=platform_admin, monthly_cap_micro=80_000)
    call = ask(school, head)
    services.execute(str(call.pk), str(school.pk), queued[0][1])
    assert refused(school, head) == "ai_cap_reached"  # le plafond est atteint : plus d'appel
    with use_school(school):
        assert AiBalance.objects.get().spent_micro == 85_000
        assert Notification.objects.filter(kind="ai_credits", user=head).count() == 1
    month = AiPlatformMonth.objects.get()
    assert month.alerted_80 and month.alerted_100
    logged = PlatformAuditLog.objects.filter(
        action__in=[PlatformAction.AI_CAP_80, PlatformAction.AI_CAP_100]
    )
    assert sorted(logged.values_list("action", flat=True)) == ["ai.cap_100", "ai.cap_80"]


def test_school_never_sees_or_spends_another_schools_ai(
    school, other_school, platform_admin, api_calls, queued
):
    mine = staff(school, ["ai.use", "timetable.manage"])
    theirs = staff(other_school, ["ai.use", "timetable.manage"])
    grant(school, platform_admin, credits=500)
    grant(other_school, platform_admin, credits=200)
    call = ask(school, mine)
    services.execute(str(call.pk), str(school.pk), queued[0][1])
    with use_school(other_school):
        assert not AiCall.objects.exists() and not AiUsageMonth.objects.exists()
        assert AiAllowance.objects.get().monthly_credits == 200
        assert AiBalance.objects.count() == 0
        # L'appel d'une autre école ne se règle pas depuis celle-ci.
        assert not AiCall.objects.filter(pk=call.pk).exists()
    # Les crédits de l'école B n'ont pas bougé, ceux de A ont baissé.
    with use_school(school):
        assert AiBalance.objects.get().spent_micro > 0
    # L'école B, sans usage affecté pour elle seule : son propre refus, pas celui de A.
    grant(other_school, platform_admin, credits=0)
    assert refused(other_school, theirs) == "ai_no_credits"


def test_allowance_and_top_up_are_in_the_platform_log(school, platform_admin, queued):
    grant(school, platform_admin, credits=100)
    user = staff(school, ["ai.use", "timetable.manage"])
    ask(school, user)  # ne crée pas la ligne de crédits (aucune exécution)
    services.top_up(school, actor=platform_admin, credits=50)
    grant(school, platform_admin, credits=300)
    with use_school(school):
        balance = AiBalance.objects.get()
        # 100 + 50 de recharge, puis +200 crédits mensuels : 350 crédits accordés.
        assert balance.granted_micro == 350 * prices.CREDIT
    actions = list(PlatformAuditLog.objects.order_by("created_at").values_list("action", flat=True))
    assert actions == ["ai.allowance_changed", "ai.top_up", "ai.allowance_changed"]
    with pytest.raises(BusinessError):
        services.set_allowance(
            school, actor=platform_admin, uses_=["nope"], monthly_credits=1, paused=False
        )


def test_purge_keeps_monthly_totals(school, platform_admin, api_calls, queued):
    user = staff(school, ["ai.use", "timetable.manage"])
    grant(school, platform_admin)
    call = ask(school, user)
    services.execute(str(call.pk), str(school.pk), queued[0][1])
    with use_all_schools():
        AiCall.all_schools.filter(pk=call.pk).update(created_at=timezone.now() - timedelta(days=91))
        AiResult.all_schools.update(created_at=timezone.now() - timedelta(hours=25))
    assert services.purge() >= 1
    with use_school(school):
        assert not AiCall.objects.exists() and not AiResult.objects.exists()
        assert AiUsageMonth.objects.count() == 1
