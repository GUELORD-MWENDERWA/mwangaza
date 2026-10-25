"""Services de l'IA (IA.1.1, `05` § 6.5) : les cinq verrous avant chaque appel (`authorize`),
la demande (`submit`), l'exécution par le travailleur (`execute`), le sort de la réponse
(`settle`), les réglages de la plateforme (journal de la plateforme) et la purge.

Rien n'est appelé sans le clic d'une personne. Un refus ne coûte rien (aucun appel à l'API) et
dit pourquoi. Le texte de la demande passe par la file de tâches et n'est écrit nulle part ;
`AiCall` ne garde que les jetons et le coût, en micro-dollars (entiers)."""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from apps.accounts.models import User
from apps.ai import client, prices, uses
from apps.ai.models import (
    AiAllowance,
    AiBalance,
    AiCall,
    AiPlatformMonth,
    AiResult,
    AiSettings,
    AiUsageMonth,
)
from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import use_all_schools, use_school
from apps.schools.models import School

logger = logging.getLogger(__name__)
State = AiCall.State
KEEP_DAYS = 90
RESULT_HOURS = 24
ALERT_AT = 80  # pour cent

# Un refus par verrou ; le code est stable, l'interface affiche son texte.
AI_OFF = ApiError("ai_off", gettext_lazy("The AI assistance is switched off."), 403)
AI_CAP = ApiError(
    "ai_cap_reached", gettext_lazy("The AI assistance is unavailable until next month."), 403
)
AI_UNKNOWN = ApiError("ai_unknown_use", gettext_lazy("This AI use does not exist."), 404)
AI_NOT_AVAILABLE = ApiError(
    "ai_not_available", gettext_lazy("This AI use is not part of your school's plan."), 403
)
AI_PAUSED = ApiError("ai_paused", gettext_lazy("The AI assistance is paused for your school."), 403)
AI_FORBIDDEN = ApiError(
    "ai_forbidden", gettext_lazy("You are not allowed to use the AI assistance here."), 403
)
AI_NO_CREDITS = ApiError(
    "ai_no_credits", gettext_lazy("Your school has no AI credits left this month."), 403
)
AI_RATE_LIMITED = ApiError(
    "ai_rate_limited", gettext_lazy("Too many AI requests this hour. Try again later."), 429
)
AI_TOO_LARGE = ApiError(
    "ai_too_large", gettext_lazy("The request is too large for this AI use."), 413
)
AI_CONFLICT = ApiError(
    "ai_request_conflict", gettext_lazy("This request identifier is already used."), 409
)


@dataclass(frozen=True)
class Authorization:
    use: uses.AiUse
    model: str
    max_output_tokens: int
    max_cost_micro: int
    on_platform: bool


def month_start(today: date | None = None) -> date:
    return (today or timezone.localdate()).replace(day=1)


def platform_settings() -> AiSettings:
    return AiSettings.objects.get_or_create(pk=1)[0]


def price_table(config: AiSettings) -> dict:
    return {**prices.DEFAULT_PRICES, **config.prices}


def resolve_use(config: AiSettings, code: str) -> uses.AiUse:
    """L'usage du catalogue avec les changements de la console (modèle, limites)."""
    base = uses.USES.get(code)
    if base is None:
        raise BusinessError(AI_UNKNOWN)
    changed = config.use_overrides.get(code, {})
    fields = {
        key: changed[key]
        for key in ("model", "max_input_tokens", "max_output_tokens")
        if key in changed
    }
    return uses.AiUse(**{**base.__dict__, **fields})


def estimate_tokens(chars: int) -> int:
    """Estimation prudente (par le haut) des jetons d'une entrée de `chars` caractères."""
    return chars // 2 + 1


def authorize(
    *, school: School, user: User, permissions, use_code: str, input_chars: int, support=False
) -> Authorization:
    """Les cinq verrous, dans l'ordre. Lève `BusinessError` au premier refus, sans rien écrire
    ni appeler l'API. Dans l'école courante."""
    config = platform_settings()
    use = resolve_use(config, use_code)
    month = month_start()
    # 1. Interrupteur et plafond de la plateforme.
    if not config.enabled:
        raise BusinessError(AI_OFF)
    platform = AiPlatformMonth.objects.filter(month=month).first()
    if (platform.spent_micro if platform else 0) >= config.monthly_cap_micro:
        raise BusinessError(AI_CAP)
    # 2. Module `ai`, module hôte, usage affecté à l'école, école pas en pause.
    allowance = AiAllowance.objects.filter(school=school).first()
    if (
        not school.has_module("ai")
        or not school.has_module(use.module)
        or allowance is None
        or use.code not in allowance.uses
    ):
        raise BusinessError(AI_NOT_AVAILABLE)
    if allowance.paused:
        raise BusinessError(AI_PAUSED)
    # 3. `ai.use` et la permission de l'écran hôte (la session support a tous les droits utiles).
    if not support and not {"ai.use", use.permission} <= set(permissions):
        raise BusinessError(AI_FORBIDDEN)
    # 4. Crédits restants ≥ coût maximal de l'appel (sauf session support : plateforme).
    input_tokens = estimate_tokens(input_chars)
    if input_tokens > use.max_input_tokens:
        raise BusinessError(AI_TOO_LARGE)
    table = price_table(config)[use.model]
    max_cost = prices.cost(table, input_=input_tokens, output=use.max_output_tokens)
    if not support:
        balance = AiBalance.objects.filter(school=school, month=month).first()
        granted = balance.remaining_micro if balance else allowance.monthly_credits * prices.CREDIT
        if granted < max_cost:
            raise BusinessError(AI_NO_CREDITS)
    # 5. Limite par personne : appels de la dernière heure (les refus ne comptent pas).
    since = timezone.now() - timedelta(hours=1)
    recent = (
        AiCall.objects.filter(user=user, created_at__gte=since).exclude(state=State.REFUSED).count()
    )
    if recent >= config.hourly_limit:
        raise BusinessError(AI_RATE_LIMITED)
    return Authorization(use, use.model, use.max_output_tokens, max_cost, support)


def submit(
    *,
    school: School,
    user: User,
    permissions,
    use_code: str,
    request_id,
    system: str,
    messages: list[dict],
    schema: dict | None = None,
    support: bool = False,
) -> AiCall:
    """Demande d'une personne, dans l'école courante : autorise, écrit l'appel, met la tâche en
    file. Même `request_id` deux fois : l'appel déjà fait, aucun nouvel appel. Le refus est noté
    (une ligne, sans texte) puis levé."""
    existing = AiCall.objects.filter(request_id=request_id).first()
    if existing is not None:
        if existing.user_id != user.pk:
            raise BusinessError(AI_CONFLICT)
        return existing
    chars = len(system) + sum(len(str(message.get("content", ""))) for message in messages)
    try:
        grant = authorize(
            school=school,
            user=user,
            permissions=permissions,
            use_code=use_code,
            input_chars=chars,
            support=support,
        )
    except BusinessError as refusal:
        _record_refusal(school, user, use_code, request_id, refusal.error.code)
        raise
    try:
        with transaction.atomic():
            call = AiCall.objects.create(
                user=user,
                use=use_code,
                model=grant.model,
                request_id=request_id,
                on_platform=support,
            )
    except IntegrityError:  # deux clics en même temps : l'autre a gagné
        return AiCall.objects.get(request_id=request_id)
    payload = {
        "system": system,
        "messages": messages,
        "schema": schema,
        "max_tokens": grant.max_output_tokens,
        "language": translation.get_language() or settings.LANGUAGE_CODE,
    }
    _enqueue(call, payload)
    return call


def _record_refusal(school: School, user: User, use_code: str, request_id, code: str) -> None:
    """La ligne du refus ; jamais une raison de plus de refuser si elle ne s'écrit pas."""
    try:
        AiCall.objects.get_or_create(
            request_id=request_id,
            defaults={
                "user": user,
                "use": use_code,
                "state": State.REFUSED,
                "refusal": code,
                "finished_at": timezone.now(),
            },
        )
    except Exception:
        logger.exception("Refus de l'IA non noté")


def _enqueue(call: AiCall, payload: dict) -> None:
    from apps.ai.tasks import run_call

    school_id = str(call.school_id)
    transaction.on_commit(lambda: run_call.delay(str(call.pk), school_id, payload))


def execute(call_id: str, school_id: str, payload: dict) -> None:
    """Tâche de la file `ai` : un seul appel à l'API, puis jetons, coût et cumuls écrits. Déjà
    pris ou refait après un arrêt : rien ne se refait (`acks_late`, seul un appel « en attente »
    démarre). Une erreur est notée sur l'appel ; sans réponse de l'API, rien n'est facturé."""
    with use_all_schools():
        school = School.objects.get(pk=school_id)
    with use_school(school), translation.override(payload.get("language")):
        started = AiCall.objects.filter(pk=call_id, state=State.QUEUED).update(state=State.RUNNING)
        if not started:
            return
        call = AiCall.objects.get(pk=call_id)
        reply, failure = None, ""
        try:
            reply = client.complete(
                model=call.model,
                system=payload["system"],
                messages=payload["messages"],
                max_tokens=payload["max_tokens"],
                schema=payload.get("schema"),
            )
        except client.NotConfigured:
            failure = "not_configured"
        except Exception as error:  # l'API a refusé, coupé ou ne répond pas
            logger.exception("Appel IA %s en échec", call_id)
            failure = type(error).__name__[:40]
        _finish(call, reply, failure)


@transaction.atomic
def _finish(call: AiCall, reply: client.Reply | None, failure: str) -> None:
    now = timezone.now()
    if reply is None:
        AiCall.objects.filter(pk=call.pk).update(
            state=State.ERROR, refusal=failure, finished_at=now
        )
        return
    config = platform_settings()
    table = price_table(config).get(call.model) or prices.DEFAULT_PRICES[uses.DEFAULT_MODEL]
    cost = prices.cost(
        table,
        input_=reply.input_tokens,
        output=reply.output_tokens,
        cache_read=reply.cache_read_tokens,
        cache_write=reply.cache_write_tokens,
    )
    AiCall.objects.filter(pk=call.pk).update(
        state=State.DONE,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
        cache_read_tokens=reply.cache_read_tokens,
        cache_write_tokens=reply.cache_write_tokens,
        cost_micro=cost,
        finished_at=now,
    )
    AiResult.objects.update_or_create(
        call=call, defaults={"payload": {"text": reply.text, "stop_reason": reply.stop_reason}}
    )
    month = month_start()
    if not call.on_platform:
        usage, _created = AiUsageMonth.objects.get_or_create(
            school=call.school, month=month, use=call.use
        )
        AiUsageMonth.objects.filter(pk=usage.pk).update(
            calls=F("calls") + 1,
            input_tokens=F("input_tokens") + reply.input_tokens,
            output_tokens=F("output_tokens") + reply.output_tokens,
            cache_tokens=F("cache_tokens") + reply.cache_read_tokens + reply.cache_write_tokens,
            cost_micro=F("cost_micro") + cost,
        )
        _charge_school(call.school, month, cost)
    _charge_platform(month, cost, config)


def _balance(school: School, month: date) -> AiBalance:
    balance = AiBalance.objects.select_for_update().filter(school=school, month=month).first()
    if balance is None:
        allowance = AiAllowance.objects.filter(school=school).first()
        granted = (allowance.monthly_credits if allowance else 0) * prices.CREDIT
        balance = AiBalance.objects.create(school=school, month=month, granted_micro=granted)
    return balance


def _charge_school(school: School, month: date, cost: int) -> None:
    balance = _balance(school, month)
    balance.spent_micro += cost
    alert = (
        not balance.alerted_80
        and balance.granted_micro > 0
        and balance.spent_micro * 100 >= balance.granted_micro * ALERT_AT
    )
    if alert:
        balance.alerted_80 = True
    balance.save(update_fields=["spent_micro", "alerted_80", "updated_at"])
    if alert:
        from apps.notifications import events

        events.ai_credits_low(balance)


def _charge_platform(month: date, cost: int, config: AiSettings) -> None:
    row = AiPlatformMonth.objects.select_for_update().get_or_create(month=month)[0]
    row.spent_micro += cost
    cap = config.monthly_cap_micro
    crossed = []
    if not row.alerted_80 and row.spent_micro * 100 >= cap * ALERT_AT:
        row.alerted_80 = True
        crossed.append(PlatformAction.AI_CAP_80)
    if not row.alerted_100 and row.spent_micro >= cap:
        row.alerted_100 = True
        crossed.append(PlatformAction.AI_CAP_100)
    row.save()
    for action in crossed:
        entry = audit.record_platform(
            action, row, actor=None, after={"spent_micro": row.spent_micro, "cap_micro": cap}
        )
        from apps.notifications import console

        detail = _("%(spent)s of %(cap)s dollars used this month.") % {
            "spent": f"{row.spent_micro / 1_000_000:.2f}",
            "cap": f"{cap / 1_000_000:.2f}",
        }
        console.alert(action, entry.pk, detail)


def result_of(call: AiCall) -> dict | None:
    """Réponse en attente de la personne (écran de l'usage) ; None si elle n'est pas prête."""
    found = AiResult.objects.filter(call=call).first()
    return found.payload if found else None


@transaction.atomic
def settle(call: AiCall, *, kept: bool) -> AiCall:
    """La personne garde le résultat (il devient une donnée normale, jamais refait) ou
    l'abandonne : l'état de l'appel et la part « gardée » du mois. Une fois seulement."""
    changed = AiCall.objects.filter(pk=call.pk, state=State.DONE).update(
        state=State.KEPT if kept else State.ABANDONED
    )
    if changed:
        usage = AiUsageMonth.objects.filter(
            school=call.school, month=month_start(call.created_at.date()), use=call.use
        )
        usage.update(**{"kept" if kept else "abandoned": F("kept" if kept else "abandoned") + 1})
        AiResult.objects.filter(call=call).delete()
    call.refresh_from_db()
    return call


# Réglages de la plateforme : seul le super-admin (console, IA.1.2), journal de la plateforme.


@transaction.atomic
def update_settings(*, actor: User, **changes) -> AiSettings:
    config = AiSettings.objects.select_for_update().get_or_create(pk=1)[0]
    before = {key: getattr(config, key) for key in changes}
    for key, value in changes.items():
        setattr(config, key, value)
    config.save()
    audit.record_platform(
        PlatformAction.AI_SETTINGS_CHANGED, config, actor=actor, before=before, after=changes
    )
    return config


@transaction.atomic
def set_allowance(
    school: School, *, actor: User, uses_: list[str], monthly_credits: int, paused: bool
) -> AiAllowance:
    """Usages, crédits mensuels et pause d'une école. Les crédits du mois en cours suivent le
    changement (la différence s'ajoute ou se retire)."""
    unknown = set(uses_) - set(uses.USES)
    if unknown:
        raise BusinessError(AI_UNKNOWN)
    with use_school(school):
        allowance = AiAllowance.objects.select_for_update().filter(school=school).first()
        old = allowance.monthly_credits if allowance else 0
        before = (
            {"uses": allowance.uses, "monthly_credits": old, "paused": allowance.paused}
            if allowance
            else None
        )
        allowance = allowance or AiAllowance(school=school)
        allowance.uses, allowance.monthly_credits, allowance.paused = uses_, monthly_credits, paused
        allowance.save()
        balance = AiBalance.objects.filter(school=school, month=month_start()).first()
        if balance:
            balance.granted_micro = max(
                0, balance.granted_micro + (monthly_credits - old) * prices.CREDIT
            )
            balance.save(update_fields=["granted_micro", "updated_at"])
    audit.record_platform(
        PlatformAction.AI_ALLOWANCE_CHANGED,
        school,
        actor=actor,
        before=before,
        after={"uses": uses_, "monthly_credits": monthly_credits, "paused": paused},
    )
    return allowance


@transaction.atomic
def top_up(school: School, *, actor: User, credits: int) -> AiBalance:
    """Recharge : des crédits en plus pour le mois en cours."""
    if credits <= 0:
        raise BusinessError(ApiError("invalid", gettext_lazy("Some fields are invalid."), 400))
    with use_school(school):
        balance = _balance(school, month_start())
        balance.granted_micro += credits * prices.CREDIT
        balance.alerted_80 = balance.spent_micro * 100 >= balance.granted_micro * ALERT_AT
        balance.save(update_fields=["granted_micro", "alerted_80", "updated_at"])
    audit.record_platform(PlatformAction.AI_TOP_UP, school, actor=actor, after={"credits": credits})
    return balance


def purge(now=None) -> int:
    """Chaque nuit : appels de plus de 90 jours, réponses de plus de 24 h (jamais gardées en
    silence). Les cumuls mensuels restent (facturation)."""
    now = now or timezone.now()
    with use_all_schools():
        AiResult.all_schools.filter(created_at__lt=now - timedelta(hours=RESULT_HOURS)).delete()
        deleted, _per = AiCall.all_schools.filter(
            created_at__lt=now - timedelta(days=KEEP_DAYS)
        ).delete()
    return deleted
