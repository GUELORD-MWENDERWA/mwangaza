"""Écoles : création par le super-admin avec son premier directeur (A1), changements faits par le
super-admin (console, 5.3) ou par l'école (paramètres, M5), suspension, arrêt (4.15), suppression
d'un espace d'essai ou de démonstration (4.16).

Tout va dans le journal de l'école : création, identité (avant / après), logo, suspension, arrêt
et réactivation. L'abonnement (offre, dates, essai ↔ actif) n'y va pas : c'est l'affaire de la
plateforme. Ce que fait le super-admin (identité et abonnement) va aussi dans le journal de la
plateforme.
"""

from dataclasses import dataclass
from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts import modules
from apps.accounts import services as accounts
from apps.accounts.models import Membership, Role
from apps.audit import services as audit
from apps.audit.actions import Action, PlatformAction
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import use_school
from apps.schools import alerts, deletion, portal, receipts, reminders, tasks
from apps.schools.models import Demonstration, School

LIVE_SPACE = ApiError("live_space", _("A live space is never deleted: stop it instead."), 409)
# Remplir ou effacer un espace est lourd : un seul à la fois, par un refus (pas de file d'attente).
SPACE_BUSY = ApiError(
    "space_busy", _("Another space is being created or deleted: wait until it is done."), 409
)
SPACE_BEING_DELETED = ApiError(
    "space_being_deleted", _("This space is being deleted: it can no longer be changed."), 409
)

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
# Ce que le journal de la plateforme garde en plus (`environment` : fixé à la création).
SUBSCRIPTION_FIELDS = ("environment", "status", "plan", "trial_ends_on", "paid_until", "modules")


@dataclass(frozen=True)
class Director:
    """Premier directeur d'une nouvelle école. Numéro déjà connu : noms ignorés (B3)."""

    phone: str
    last_name: str = ""
    middle_name: str = ""
    first_name: str = ""


def _identity(school: School) -> dict:
    return {field: getattr(school, field) for field in IDENTITY_FIELDS}


def _platform_fields(school: School) -> dict:
    """Identité et abonnement, dates écrites `AAAA-MM-JJ` (JSON)."""
    subscription = {field: getattr(school, field) for field in SUBSCRIPTION_FIELDS}
    dates = ("trial_ends_on", "paid_until")
    return {
        **_identity(school),
        **{f: str(v) if f in dates and v else v for f, v in subscription.items()},
    }


def _record_platform(action: str, school: School, *, actor, before: dict | None = None) -> None:
    after = _platform_fields(school)
    if before is not None:
        before, after = audit.changes(before, after)
        if not after:
            return
    audit.record_platform(action, school, actor=actor, before=before, after=after)


def create_school(school: School, *, actor, director: Director) -> tuple[Membership, str | None]:
    """Nouvelle école (`school`, pas encore enregistrée) : rôles système copiés, premier
    directeur avec le rôle `head`. Nouveau numéro : mot de passe provisoire renvoyé une seule
    fois, à transmettre au directeur (pas de SMS en V1)."""
    with transaction.atomic():
        open_space(school, actor=actor)
        with use_school(school):
            return accounts.add_staff_member(
                actor=actor,
                phone=director.phone,
                roles=[Role.objects.get(code="head")],
                last_name=director.last_name,
                middle_name=director.middle_name,
                first_name=director.first_name,
            )


def open_space(school: School, *, actor) -> School:
    """Enregistre le nouvel espace `school` et le note dans les deux journaux."""
    with transaction.atomic():
        school.created_by = actor
        if school.environment == School.Environment.DEMO:
            # Déjà rempli : pas de liste « Mise en route » (`setup.py`).
            school.setup_completed_at = timezone.now()
            school.modules = modules.ALL_MODULES
        school.save()  # rôles système copiés (`accounts/signals.py`)
        _record_platform(PlatformAction.SCHOOL_CREATED, school, actor=actor)
        with use_school(school):
            audit.record(Action.SCHOOL_CREATED, school, actor=actor, after=_identity(school))
    return school


def space_busy(*, but: School | None = None) -> bool:
    """Un autre espace que `but` se remplit ou s'efface en ce moment."""
    filling = Demonstration.objects.filter(state=Demonstration.State.FILLING)
    deleting = School.objects.filter(status=School.Status.DELETING)
    if but is not None:
        filling, deleting = filling.exclude(school=but), deleting.exclude(pk=but.pk)
    return filling.exists() or deleting.exists()


def save_school(school: School, *, actor) -> School:
    """Enregistre les changements faits sur `school` et les note dans son journal."""
    with transaction.atomic():
        old = School.objects.select_for_update().get(pk=school.pk)
        if old.status == School.Status.DELETING:
            # Ni relancé, ni arrêté, ni renommé : ses données partent déjà (4.16).
            raise BusinessError(SPACE_BEING_DELETED)
        if school.environment != old.environment:
            # Pas de passage d'un type à l'autre (`03` § 4 bis) : on repart d'un espace neuf.
            raise ValueError("Le type d'un espace ne change jamais.")
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
    if old.status == school.status:
        return
    if school.status == School.Status.SUSPENDED:
        audit.record(Action.SCHOOL_SUSPENDED, school, actor=actor)
    elif school.status == School.Status.STOPPED:
        audit.record(Action.SCHOOL_STOPPED, school, actor=actor)
    elif old.is_closed:
        audit.record(Action.SCHOOL_REACTIVATED, school, actor=actor)


def _settings_fields(settings: dict) -> dict:
    return {
        **receipts.journal_fields(settings),
        **alerts.journal_fields(settings),
        **reminders.journal_fields(settings),
        **portal.journal_fields(settings),
    }


LOGO_FIELDS = ("logo", "logo_monochrome")


def update_school(school: School, *, actor, **fields) -> School:
    """Paramètres de l'école (M5) ou administration : champs déjà vérifiés. `logo=None` retire
    le logo ; `receipt`, `alerts`, `reminders`, `portal` : réglages du reçu, seuils d'alerte,
    relances aux parents ou portail à changer, les autres restent."""
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
    if (changed := fields.pop("reminders", None)) is not None:
        school.settings = {**school.settings, "reminders": {**school.reminders, **changed}}
    if (changed := fields.pop("portal", None)) is not None:
        school.settings = {**school.settings, "portal": {**school.portal, **changed}}
    for field, value in fields.items():
        setattr(school, field, "" if field in LOGO_FIELDS and value is None else value)
    return save_school(school, actor=actor)


def change_school(school: School, *, actor, **fields) -> School:
    """Console (5.3) : identité ou abonnement changés par le super-admin, notés dans le journal
    de la plateforme (avant / après) ; l'école ne voit que son identité changer."""
    with transaction.atomic():
        before = _platform_fields(school)
        update_school(school, actor=actor, **fields)
        _record_platform(PlatformAction.SCHOOL_UPDATED, school, actor=actor, before=before)
    return school


def suspend(school: School, *, actor) -> School:
    """Plus personne ne se connecte à l'école ; rien n'est supprimé (A1)."""
    if school.is_closed:
        return school
    before = _platform_fields(school)
    with transaction.atomic():
        update_school(school, actor=actor, status=School.Status.SUSPENDED)
        _record_platform(PlatformAction.SCHOOL_SUSPENDED, school, actor=actor, before=before)
    return school


def stop(school: School, *, actor, reason: str) -> School:
    """Espace arrêté (4.15) : l'école a quitté la plateforme, l'essai ou la démonstration est
    fini. Plus personne n'y entre, rien n'est supprimé ; le motif reste dans le journal de la
    plateforme. Une erreur se rattrape par `reactivate`."""
    if school.status == School.Status.STOPPED:
        return school
    before = _platform_fields(school)
    with transaction.atomic():
        update_school(school, actor=actor, status=School.Status.STOPPED)
        before, after = audit.changes(before, _platform_fields(school))
        audit.record_platform(
            PlatformAction.SCHOOL_STOPPED,
            school,
            actor=actor,
            before=before,
            after={**after, "reason": reason},
        )
    return school


def reactivate(school: School, *, actor) -> School:
    """Suspendue ou arrêtée, de nouveau ouverte : en essai gratuit s'il n'est pas fini, sinon
    active."""
    if not school.is_closed:
        return school
    trial = school.trial_ends_on is not None and school.trial_ends_on >= timezone.localdate()
    status = School.Status.TRIAL if trial else School.Status.ACTIVE
    before = _platform_fields(school)
    with transaction.atomic():
        update_school(school, actor=actor, status=status)
        _record_platform(PlatformAction.SCHOOL_REACTIVATED, school, actor=actor, before=before)
    return school


def delete_space(school: School, *, actor, confirm: str) -> None:
    """Supprime un espace d'essai ou de démonstration (4.16) ; jamais un espace réel, qu'on
    arrête. `confirm` : le code de l'espace, retapé.

    Dans la requête : l'espace est fermé à tous, les comptes qui n'avaient que lui sont
    désactivés et le journal de la plateforme est écrit. Les données sont effacées en tâche de
    fond (`deletion.run`), un espace à la fois. Déjà en cours : la tâche est seulement relancée
    (une panne l'avait interrompue)."""
    if school.environment == School.Environment.LIVE:
        raise BusinessError(LIVE_SPACE)
    if confirm.strip().lower() != school.code:
        message = _("Type the code of the space to confirm.")
        raise ValidationError({"confirm": ValidationError(message, code="wrong_code")})
    deleting = School.Status.DELETING
    with transaction.atomic():
        school = School.objects.select_for_update().get(pk=school.pk)
        if school.status != deleting:
            if space_busy(but=school):
                raise BusinessError(SPACE_BUSY)
            before = _platform_fields(school)
            deactivated = deletion.deactivate_accounts_left_without_school(school)
            school.status = deleting
            school.save(update_fields=["status", "updated_at"])
            audit.record_platform(
                PlatformAction.SCHOOL_DELETED,
                school,
                actor=actor,
                before=before,
                after={"accounts_deactivated": deactivated},
            )
        transaction.on_commit(partial(tasks.delete_space.delay, str(school.pk)))
