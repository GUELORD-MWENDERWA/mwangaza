"""IA de démonstration (IA.1.1) : chaque espace reçoit des usages et des crédits fictifs pour
essayer l'assistance (aucun appel à l'API : pas de clé en démonstration). L'ITIG a les trois
usages et 5 000 crédits par mois (≈ 5 $), `volcans` seulement les règles de l'horaire et 2 000
crédits. Rejouable : l'espace est remis comme au départ (appels et crédits effacés)."""

from apps.ai import uses
from apps.ai.models import AiAllowance, AiBalance, AiCall, AiResult, AiUsageMonth
from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace

PLANS = {"itig": (list(uses.USES), 5_000), "volcans": (["timetable_constraints"], 2_000)}


def create_demo_ai(spaces: list[DemoSpace]) -> None:
    for space in spaces:
        with use_school(space.school):
            for model in (AiResult, AiCall, AiUsageMonth, AiBalance, AiAllowance):
                model.objects.all().delete()
            granted, credits = PLANS.get(space.school.code, PLANS["volcans"])
            AiAllowance.objects.create(uses=granted, monthly_credits=credits)
