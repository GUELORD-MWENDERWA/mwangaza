"""Règles de prêt de l'école (BIB.2, BIB.3) : `School.settings["library"]`, réglées dans l'onglet
« Règles » de la bibliothèque, jamais dans le code. Valeurs par défaut tant que l'école n'a rien
changé.

Durée, nombre de prêts ouverts au plus et prolongations, pour un élève et pour le personnel ; un
outil d'atelier se rend le jour même (`tool_days` = 0). `block_if_overdue` : pas de nouveau prêt à
qui a un retard. Rappels : `remind_days_before` jours avant la date de retour, puis tous les
`remind_every_days` jours de retard. Pénalité de retard par jour (`late_fee_minor`, en entiers
dans `late_fee_currency`) : 0 = aucune (par défaut) ; plafonnée au prix de l'article."""

from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.tenancy import require_current_school
from apps.schools.models import School

DEFAULTS = {
    "student_days": 14,
    "student_max": 3,
    "student_extensions": 1,
    "staff_days": 30,
    "staff_max": 5,
    "staff_extensions": 2,
    "tool_days": 0,
    "block_if_overdue": True,
    "notify_parent": True,
    "remind_days_before": 2,
    "remind_every_days": 3,
    "late_fee_minor": 0,
    "late_fee_currency": "USD",
}


def rules(school: School | None = None) -> dict:
    school = school or require_current_school()
    saved = (school.settings or {}).get("library", {})
    return {key: saved.get(key, default) for key, default in DEFAULTS.items()}


def update_rules(*, actor: User, values: dict) -> dict:
    """Enregistre les règles données (les autres gardent leur valeur) ; journal : ce qui change."""
    with transaction.atomic():
        school = School.objects.select_for_update().get(pk=require_current_school().pk)
        before = rules(school)
        after = {**before, **{key: values[key] for key in DEFAULTS if key in values}}
        if after != before:
            school.settings = {**school.settings, "library": after}
            school.save(update_fields=["settings", "updated_at"])
            changed = [key for key in DEFAULTS if after[key] != before[key]]
            audit.record(
                Action.INVENTORY_RULES_CHANGED,
                school,
                actor=actor,
                before={key: before[key] for key in changed},
                after={key: after[key] for key in changed},
            )
    return after


def due_on(lent_at: datetime, *, staff: bool, tool: bool, settings: dict) -> date:
    """Date de retour d'un prêt fait à `lent_at` (jour de l'école)."""
    if tool:
        days = settings["tool_days"]
    else:
        days = settings["staff_days"] if staff else settings["student_days"]
    return timezone.localdate(lent_at) + timedelta(days=days)
