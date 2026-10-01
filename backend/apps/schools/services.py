"""Écoles : création par le super-admin avec son premier directeur (A1), changements faits par le
super-admin (administration Django) ou par l'école (paramètres, M5), suspension.

Tout va dans le journal de l'école : création, identité (avant / après), logo, suspension et
réactivation. L'abonnement (offre, dates, essai ↔ actif) n'y va pas : c'est l'affaire de la
plateforme (historique de l'administration Django).
"""

from dataclasses import dataclass
from functools import partial

from django.db import transaction
from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.models import Membership, Role
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.tenancy import use_school
from apps.schools import alerts, receipts
from apps.schools.models import School

# Ce que l'école voit changer dans son journal.
IDENTITY_FIELDS = (
    "code",
    "name",
    "official_name",
    "primary_color",
    "timezone",
    "enabled_currencies",
    "default_currency",
)


@dataclass(frozen=True)
class Director:
    """Premier directeur d'une nouvelle école. Numéro déjà connu : noms ignorés (B3)."""

    phone: str
    last_name: str = ""
    middle_name: str = ""
    first_name: str = ""


def _identity(school: School) -> dict:
    return {field: getattr(school, field) for field in IDENTITY_FIELDS}


def create_school(school: School, *, actor, director: Director) -> tuple[Membership, str | None]:
    """Nouvelle école (`school`, pas encore enregistrée) : rôles système copiés, premier
    directeur avec le rôle `head`. Nouveau numéro : mot de passe provisoire renvoyé une seule
    fois, à transmettre au directeur (pas de SMS en V1)."""
    with transaction.atomic():
        school.created_by = actor
        school.save()  # rôles système copiés (`accounts/signals.py`)
        with use_school(school):
            audit.record(Action.SCHOOL_CREATED, school, actor=actor, after=_identity(school))
            return accounts.add_staff_member(
                actor=actor,
                phone=director.phone,
                roles=[Role.objects.get(code="head")],
                last_name=director.last_name,
                middle_name=director.middle_name,
                first_name=director.first_name,
            )


def save_school(school: School, *, actor) -> School:
    """Enregistre les changements faits sur `school` et les note dans son journal."""
    with transaction.atomic():
        old = School.objects.select_for_update().get(pk=school.pk)
        school.save()
        with use_school(school):
            _record_changes(old, school, actor=actor)
        for field in LOGO_FIELDS:
            file = getattr(old, field)
            if file and file.name != getattr(school, field).name:
                transaction.on_commit(partial(file.storage.delete, file.name))
    return school


def _record_changes(old: School, school: School, *, actor) -> None:
    before, after = audit.changes(
        {**_identity(old), **_settings_fields(old.settings)},
        {**_identity(school), **_settings_fields(school.settings)},
    )
    if after:
        audit.record(Action.SCHOOL_UPDATED, school, actor=actor, before=before, after=after)
    for field in LOGO_FIELDS:
        if getattr(old, field).name != getattr(school, field).name:
            after = {field: bool(getattr(school, field))}
            audit.record(Action.SCHOOL_LOGO_CHANGED, school, actor=actor, after=after)
    suspended = School.Status.SUSPENDED
    if old.status != suspended and school.status == suspended:
        audit.record(Action.SCHOOL_SUSPENDED, school, actor=actor)
    elif old.status == suspended and school.status != suspended:
        audit.record(Action.SCHOOL_REACTIVATED, school, actor=actor)


def _settings_fields(settings: dict) -> dict:
    return {**receipts.journal_fields(settings), **alerts.journal_fields(settings)}


LOGO_FIELDS = ("logo", "logo_monochrome")


def update_school(school: School, *, actor, **fields) -> School:
    """Paramètres de l'école (M5) ou administration : champs déjà vérifiés. `logo=None` retire
    le logo ; `receipt`, `alerts` : réglages du reçu ou seuils d'alerte à changer, les autres
    restent."""
    if (receipt := fields.pop("receipt", None)) is not None:
        school.settings = {**school.settings, "receipt": {**school.receipt, **receipt}}
    if (changed := fields.pop("alerts", None)) is not None:
        current = school.alerts
        if "closing_time" in changed:
            changed["closing_time"] = changed["closing_time"].strftime("%H:%M")
        differences = {**current["difference_minor"], **changed.pop("difference_minor", {})}
        school.settings = {
            **school.settings,
            "alerts": {**current, **changed, "difference_minor": differences},
        }
    for field, value in fields.items():
        setattr(school, field, "" if field in LOGO_FIELDS and value is None else value)
    return save_school(school, actor=actor)


def suspend(school: School, *, actor) -> School:
    """Plus personne ne se connecte à l'école ; rien n'est supprimé (A1)."""
    return update_school(school, actor=actor, status=School.Status.SUSPENDED)


def reactivate(school: School, *, actor) -> School:
    """De nouveau ouverte : en essai si l'essai n'est pas fini, sinon active."""
    if school.status != School.Status.SUSPENDED:
        return school
    trial = school.trial_ends_on is not None and school.trial_ends_on >= timezone.localdate()
    status = School.Status.TRIAL if trial else School.Status.ACTIVE
    return update_school(school, actor=actor, status=status)
