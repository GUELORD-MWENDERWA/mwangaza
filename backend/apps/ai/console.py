"""Console de l'IA (IA.1.2) : page « IA » (dépense du mois, par école, par usage, alertes,
réglages), carte « IA » d'une école, et carte « Crédits IA » de la Gestion. Lit des cumuls déjà
tenus (`AiPlatformMonth`, `AiBalance`, `AiUsageMonth`) : quelques requêtes groupées, jamais une
somme sur les appels. Montants en micro-dollars (entiers) ; crédits = micro-dollars ÷ 1 000."""

from datetime import datetime, time

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy

from apps.accounts.models import User
from apps.accounts.modules import MODULES
from apps.ai import prices, uses
from apps.ai.models import AiAllowance, AiBalance, AiCall, AiPlatformMonth, AiSettings, AiUsageMonth
from apps.ai.services import (
    AI_CAP,
    AI_NO_CREDITS,
    AI_OFF,
    AI_PAUSED,
    ALERT_AT,
    month_start,
    platform_settings,
    price_table,
    resolve_use,
    update_settings,
)
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import use_all_schools, use_school
from apps.schools.models import School

State = AiCall.State
LAST_CALLS = 10
# Bornes des réglages d'un usage (jetons) : assez large pour un PDF de 3 pages, jamais sans fin.
INPUT_RANGE = (1_000, 200_000)
OUTPUT_RANGE = (256, 32_000)
AI_INVALID_USE = ApiError(
    "ai_invalid_use_settings", gettext_lazy("This model or these limits are not allowed."), 400
)
AI_MODULE_MISSING = ApiError(
    "ai_module_missing", gettext_lazy("This school does not have the module of this AI use."), 400
)


def _credits(micro: int) -> int:
    return micro // prices.CREDIT


def _kept_percent(kept: int, abandoned: int) -> int | None:
    """Part des résultats gardés parmi ceux que la personne a jugés ; rien de jugé : `None`."""
    judged = kept + abandoned
    return kept * 100 // judged if judged else None


def _use_rows(config: AiSettings, totals: dict[str, dict]) -> list[dict]:
    rows = []
    for code, base in uses.USES.items():
        use = resolve_use(config, code)
        total = totals.get(code, {})
        rows.append(
            {
                "code": code,
                "label": str(base.label),
                "module": base.module,
                "module_label": str(MODULES[base.module][0]),
                "model": use.model,
                "max_input_tokens": use.max_input_tokens,
                "max_output_tokens": use.max_output_tokens,
                "daily_limit": use.daily_limit,
                "changed": code in config.use_overrides,
                "calls": total.get("calls") or 0,
                "kept_percent": _kept_percent(total.get("kept") or 0, total.get("abandoned") or 0),
                "abandoned": total.get("abandoned") or 0,
                "cost_micro": total.get("cost") or 0,
            }
        )
    return rows


def _totals(queryset, key: str) -> dict:
    return {
        row[key]: row
        for row in queryset.values(key).annotate(
            calls=Sum("calls"), kept=Sum("kept"), abandoned=Sum("abandoned"), cost=Sum("cost_micro")
        )
    }


def overview(environments, *, live: bool) -> dict:
    """La page « IA » pour les espaces du mode de la console. En mode réel, la dépense est celle
    de la plateforme (tous les appels, sessions support comprises) face au plafond ; en
    démonstration, la somme fictive des espaces de démonstration, sans plafond ni réglages."""
    config = platform_settings()
    month = month_start()
    since = timezone.make_aware(datetime.combine(month, time.min))
    with use_all_schools():
        schools = School.objects.filter(environment__in=environments)
        usage = AiUsageMonth.all_schools.filter(month=month, school__in=schools)
        per_use = _totals(usage, "use")
        per_school = _totals(usage, "school")
        states = dict(
            AiCall.all_schools.filter(created_at__gte=since, school__in=schools)
            .values_list("state")
            .annotate(n=Count("id"))
        )
        balances = {
            row.school_id: row
            for row in AiBalance.all_schools.filter(month=month, school__in=schools)
        }
        allowances = list(
            AiAllowance.all_schools.filter(school__in=schools)
            .select_related("school")
            .order_by("school__name")
        )
    school_rows = []
    alerts = []
    for allowance in allowances:
        balance = balances.get(allowance.school_id)
        granted = balance.granted_micro if balance else allowance.monthly_credits * prices.CREDIT
        spent = balance.spent_micro if balance else 0
        total = per_school.get(allowance.school_id, {})
        row = {
            "id": allowance.school_id,
            "code": allowance.school.code,
            "name": allowance.school.name,
            "uses": len(allowance.uses),
            "paused": allowance.paused,
            "granted_credits": _credits(granted),
            "spent_credits": _credits(spent),
            "remaining_credits": _credits(max(0, granted - spent)),
            "calls": total.get("calls") or 0,
            "kept_percent": _kept_percent(total.get("kept") or 0, total.get("abandoned") or 0),
        }
        school_rows.append(row)
        if granted and spent * 100 >= granted * ALERT_AT:
            alerts.append({"kind": "school_credits", "percent": spent * 100 // granted, **row})
    calls = sum((row.get("calls") or 0) for row in per_use.values())
    kept = sum((row.get("kept") or 0) for row in per_use.values())
    abandoned = sum((row.get("abandoned") or 0) for row in per_use.values())
    if live:
        platform = AiPlatformMonth.objects.filter(month=month).first()
        spent = platform.spent_micro if platform else 0
        cap = config.monthly_cap_micro
        if cap and spent * 100 >= cap * ALERT_AT:
            alerts.insert(0, {"kind": "platform_cap", "percent": spent * 100 // cap})
    else:
        spent = sum((row.get("cost") or 0) for row in per_use.values())
        cap = None
    alerts.sort(key=lambda alert: -alert["percent"])
    return {
        "month": month,
        "live": live,
        "spent_micro": spent,
        "cap_micro": cap,
        "calls": calls,
        "refused": states.get(State.REFUSED, 0),
        "errors": states.get(State.ERROR, 0),
        "kept_percent": _kept_percent(kept, abandoned),
        "schools_with_ai": len(school_rows),
        "schools_paused": sum(1 for row in school_rows if row["paused"]),
        "alerts": alerts,
        "schools": school_rows,
        "uses": _use_rows(config, per_use),
        "settings": _settings(config) if live else None,
    }


def _settings(config: AiSettings) -> dict:
    table = price_table(config)
    return {
        "enabled": config.enabled,
        "monthly_cap_micro": config.monthly_cap_micro,
        "hourly_limit": config.hourly_limit,
        "prices": [
            {
                "model": model,
                "input": price[prices.INPUT],
                "output": price[prices.OUTPUT],
                "cache_read": price[prices.CACHE_READ],
                "changed": model in config.prices,
            }
            for model, price in table.items()
        ],
    }


# Réglages de la plateforme (réel seulement) : chaque changement au journal (`update_settings`).


@transaction.atomic
def change_price(*, actor: User, model: str, input_: int, output: int, cache_read: int):
    config = AiSettings.objects.select_for_update().get_or_create(pk=1)[0]
    if model not in price_table(config):
        raise BusinessError(AI_INVALID_USE)
    table = {**config.prices, model: prices.entry(input_, output, cache_read)}
    return update_settings(actor=actor, prices=table)


@transaction.atomic
def change_use(
    *,
    actor: User,
    code: str,
    model: str | None,
    max_input: int | None,
    max_output: int | None,
    daily_limit: int | None = None,
):
    """Modèle et limites d'un usage (demandes par personne et par jour comprises) ; tout à
    `None` : retour au réglage du catalogue."""
    config = AiSettings.objects.select_for_update().get_or_create(pk=1)[0]
    base = resolve_use(AiSettings(), code)  # lève 404 pour un usage inconnu
    overrides = {**config.use_overrides}
    if model is None and max_input is None and max_output is None and daily_limit is None:
        overrides.pop(code, None)
    else:
        model = model or base.model
        max_input = max_input or base.max_input_tokens
        max_output = max_output or base.max_output_tokens
        if (
            model not in price_table(config)
            or not INPUT_RANGE[0] <= max_input <= INPUT_RANGE[1]
            or not OUTPUT_RANGE[0] <= max_output <= OUTPUT_RANGE[1]
        ):
            raise BusinessError(AI_INVALID_USE)
        overrides[code] = {
            "model": model,
            "max_input_tokens": max_input,
            "max_output_tokens": max_output,
            "daily_limit": daily_limit or base.daily_limit,
        }
    return update_settings(actor=actor, use_overrides=overrides)


def check_uses(school: School, codes: list[str]) -> None:
    """Un usage ne se donne qu'à une école qui a son module hôte."""
    for code in codes:
        use = uses.USES.get(code)
        if use is not None and not school.has_module(use.module):
            raise BusinessError(AI_MODULE_MISSING)


# Carte « IA » de la fiche d'une école (console) et « Crédits IA » de la Gestion.


def _month_of(school: School) -> tuple[AiAllowance | None, int, int]:
    month = month_start()
    with use_school(school):
        allowance = AiAllowance.objects.filter(school=school).first()
        balance = AiBalance.objects.filter(school=school, month=month).first()
    monthly = allowance.monthly_credits if allowance else 0
    granted = balance.granted_micro if balance else monthly * prices.CREDIT
    return allowance, granted, balance.spent_micro if balance else 0


def school_card(school: School) -> dict:
    config = platform_settings()
    month = month_start()
    allowance, granted, spent = _month_of(school)
    with use_school(school):
        per_use = _totals(AiUsageMonth.objects.filter(school=school, month=month), "use")
        calls = list(AiCall.objects.select_related("user").order_by("-created_at")[:LAST_CALLS])
    granted_uses = set(allowance.uses if allowance else [])
    rows = [
        {
            **row,
            "granted": row["code"] in granted_uses,
            "available": school.has_module(row["module"]),
        }
        for row in _use_rows(config, per_use)
    ]
    return {
        "month": month,
        "has_module": school.has_module("ai"),
        "uses": rows,
        "monthly_credits": allowance.monthly_credits if allowance else 0,
        "paused": allowance.paused if allowance else False,
        "granted_credits": _credits(granted),
        "spent_credits": _credits(spent),
        "remaining_credits": _credits(max(0, granted - spent)),
        "last_calls": [
            {
                "id": call.id,
                "created_at": call.created_at,
                "use": call.use,
                "use_label": str(uses.USES[call.use].label) if call.use in uses.USES else call.use,
                "user": call.user.get_full_name() or call.user.phone,
                "state": call.state,
                "refusal": call.refusal,
                "credits": -(-call.cost_micro // prices.CREDIT),
                "on_platform": call.on_platform,
            }
            for call in calls
        ],
    }


def credits_for_school(school: School) -> dict:
    """« Crédits IA » de la Gestion, en lecture seule, et la raison d'un refus sûr pour chaque
    usage (bouton grisé) : IA éteinte ou plafond atteint, pause, crédits sous le coût minimal
    d'un appel (sa réponse au plus). Le serveur revérifie tout au clic (`authorize`)."""
    config = platform_settings()
    allowance, granted, spent = _month_of(school)
    remaining = max(0, granted - spent)
    platform = AiPlatformMonth.objects.filter(month=month_start()).first()
    blocked = ""
    if not config.enabled:
        blocked = AI_OFF.code
    elif (platform.spent_micro if platform else 0) >= config.monthly_cap_micro:
        blocked = AI_CAP.code
    elif allowance and allowance.paused:
        blocked = AI_PAUSED.code
    table = price_table(config)
    rows = []
    for code in allowance.uses if allowance else []:
        if code not in uses.USES:
            continue
        use = resolve_use(config, code)
        floor = prices.cost(table[use.model], output=use.max_output_tokens)
        rows.append(
            {
                "code": code,
                "label": str(use.label),
                "blocked": blocked or (AI_NO_CREDITS.code if remaining < floor else ""),
            }
        )
    return {
        "month": month_start(),
        "has_module": school.has_module("ai"),
        "granted_credits": _credits(granted),
        "spent_credits": _credits(spent),
        "remaining_credits": _credits(remaining),
        "blocked": blocked,
        "uses": rows,
    }
