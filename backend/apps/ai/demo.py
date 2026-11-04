"""IA de démonstration (IA.1.1) : chaque espace reçoit des usages et des crédits fictifs pour
essayer l'assistance (aucun appel à l'API : pas de clé en démonstration). L'ITIG a les trois
usages et 5 000 crédits par mois (≈ 5 $), `volcans` seulement les règles de l'horaire et 2 000
crédits. Le mois en cours a une consommation fictive (IA.1.2 : la console a des chiffres à
montrer) : l'ITIG en a utilisé un tiers, `volcans` 84 % (alerte « crédits presque épuisés »).
Rejouable : l'espace est remis comme au départ (appels et crédits effacés)."""

from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import Membership
from apps.ai import prices, uses
from apps.ai.models import AiAllowance, AiBalance, AiCall, AiResult, AiUsageMonth
from apps.ai.services import month_start
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace

PLANS = {"itig": (list(uses.USES), 5_000), "volcans": (["timetable_constraints"], 2_000)}
# Part des crédits du mois déjà utilisée, en pour cent.
SPENT = {"itig": 36, "volcans": 84}
# Par usage : appels, gardés, abandonnés (le coût se répartit au prorata des appels).
CALLS = {"timetable_constraints": (60, 48, 6), "timetable_review": (25, 14, 8)}
CALLS["course_grid_from_pdf"] = (4, 4, 0)


def create_demo_ai(spaces: list[DemoSpace]) -> None:
    for space in spaces:
        with use_school(space.school):
            for model in (AiResult, AiCall, AiUsageMonth, AiBalance, AiAllowance):
                model.objects.all().delete()
            granted, credits = PLANS.get(space.profile, PLANS["volcans"])
            AiAllowance.objects.create(uses=granted, monthly_credits=credits)
            _month_usage(space, granted, credits)


def _month_usage(space: DemoSpace, granted: list[str], credits: int) -> None:
    month = month_start()
    spent = credits * prices.CREDIT * SPENT.get(space.profile, SPENT["volcans"]) // 100
    AiBalance.objects.create(month=month, granted_micro=credits * prices.CREDIT, spent_micro=spent)
    calls = {code: CALLS[code] for code in granted if code in CALLS}
    total = sum(count for count, _kept, _abandoned in calls.values())
    left = spent
    for index, (code, (count, kept, abandoned)) in enumerate(calls.items()):
        # Le dernier usage prend le reste : la somme des cumuls égale la dépense, au micro-dollar.
        cost = left if index == len(calls) - 1 else spent * count // total
        left -= cost
        AiUsageMonth.objects.create(
            month=month, use=code, calls=count, kept=kept, abandoned=abandoned, cost_micro=cost
        )
    # Le directeur des études, qui règle l'horaire (le droit `ai.use` reste à donner par l'école).
    members = Membership.objects.filter(school=space.school).select_related("user")
    user = members.filter(roles__permissions__contains=["timetable.manage"]).first()
    if user is None:
        return
    now = timezone.now()
    states = [AiCall.State.KEPT, AiCall.State.ABANDONED, AiCall.State.KEPT]
    for hours, state in enumerate(states):
        AiCall.objects.create(
            user=user.user,
            use=granted[0],
            model=uses.DEFAULT_MODEL,
            request_id=uuid7(),
            state=state,
            input_tokens=2_400,
            output_tokens=900,
            cost_micro=27_600,
            finished_at=now - timedelta(hours=hours * 5),
        )
