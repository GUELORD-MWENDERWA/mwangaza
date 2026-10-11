"""Coordonnées changées par un parent dans le portail (H5, M18).

Le parent envoie son adresse, son e-mail et un contact d'urgence. Chaque école où il a une
famille (reliée à son compte, accès non suspendu, école ouverte) reçoit une demande avec ce qui
diffère de sa propre copie ; un nouvel envoi remplace la demande pas encore traitée. Le
secrétariat l'applique à la copie de son école ou ne l'applique pas : rien n'y change sans lui.
Rien de ce qu'une école sait de la famille n'est montré à une autre."""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.students.models import ContactChange, Family, Guardian

ADDRESS, EMAIL, EMERGENCY = "address", "email", "emergency_contact"
ADDRESS_PARTS = ("commune", "quartier", "avenue", "number")

ALREADY_HANDLED = ApiError(
    "already_handled", _("This request has already been handled by someone else."), 409
)


def linked(user: User):
    """Familles du compte que le portail montre, dans l'ordre où il les a reliées."""
    return (
        Family.all_schools.filter(primary_user=user, portal_suspended_at__isnull=True)
        .exclude(school__status__in=School.CLOSED_STATUSES)
        .select_related("school")
        .order_by("activated_at", "id")
    )


def _emergency(family: Family) -> Guardian | None:
    return family.guardians.filter(is_emergency_contact=True, is_primary=False).first()


def current(family: Family) -> dict:
    """Coordonnées de la famille dans son école (école courante) : adresse du premier enfant,
    e-mail du contact principal, premier contact d'urgence autre que lui."""
    student = family.students.order_by("last_name", "first_name").first()
    address = student.address if student else {}
    primary = family.guardians.filter(is_primary=True).first()
    emergency = _emergency(family)
    return {
        ADDRESS: {part: address.get(part, "") for part in ADDRESS_PARTS},
        EMAIL: primary.email if primary else "",
        EMERGENCY: {
            "full_name": emergency.full_name if emergency else "",
            "phone": emergency.phone if emergency else "",
        },
    }


def _diff(before: dict, values: dict) -> dict:
    # Contact d'urgence laissé vide : on ne retire personne de la fiche.
    if not values[EMERGENCY]["phone"]:
        values = {**values, EMERGENCY: before[EMERGENCY]}
    return {
        name: {"before": before[name], "after": after}
        for name, after in values.items()
        if after != before[name]
    }


def submit(user: User, values: dict) -> list[School]:
    """Une demande par école du compte dont la copie diffère ; renvoie ces écoles."""
    schools = []
    for family in linked(user):
        with use_school(family.school), transaction.atomic():
            family = Family.objects.select_for_update().get(pk=family.pk)
            family.contact_changes.filter(status=ContactChange.Status.PENDING).delete()
            changes = _diff(current(family), values)
            if changes:
                ContactChange.objects.create(family=family, changes=changes, created_by=user)
                schools.append(family.school)
    return schools


def profile(user: User) -> tuple[dict, list[School]]:
    """Ce que le portail affiche : les coordonnées de la première école reliée, avec ce que le
    parent a envoyé et qu'une école n'a pas encore traité ; les écoles qui ne l'ont pas traité."""
    families = list(linked(user))
    if not families:
        empty = {"full_name": "", "phone": ""}
        return {ADDRESS: dict.fromkeys(ADDRESS_PARTS, ""), EMAIL: "", EMERGENCY: empty}, []
    with use_school(families[0].school):
        values = current(families[0])
    pending = (
        ContactChange.all_schools.filter(family__in=families, status=ContactChange.Status.PENDING)
        .select_related("school")
        .order_by("created_at")
    )
    for change in pending:
        values.update({name: change.changes[name]["after"] for name in change.changes})
    return values, [change.school for change in pending]


def _close(change: ContactChange, status: str, actor: User, action: str) -> ContactChange:
    with transaction.atomic():
        change = (
            ContactChange.objects.select_for_update().select_related("family").get(pk=change.pk)
        )
        if change.status != ContactChange.Status.PENDING:
            raise BusinessError(ALREADY_HANDLED)
        if status == ContactChange.Status.APPLIED:
            _write(change.family, change.changes, actor=actor)
        change.status = status
        change.handled_by = actor
        change.handled_at = timezone.now()
        change.save(update_fields=["status", "handled_by", "handled_at", "updated_at"])
        audit.record(
            action,
            change.family,
            actor=actor,
            before={name: value["before"] for name, value in change.changes.items()},
            after={name: value["after"] for name, value in change.changes.items()},
        )
    return change


def _write(family: Family, changes: dict, *, actor: User) -> None:
    if ADDRESS in changes:
        # Un par un : chaque élève enregistré redescend sur les appareils (synchronisation).
        for student in family.students.all():
            student.address = changes[ADDRESS]["after"]
            student.save(update_fields=["address", "updated_at"])
    if EMAIL in changes:
        family.guardians.filter(is_primary=True).update(
            email=changes[EMAIL]["after"], updated_at=timezone.now()
        )
    if EMERGENCY in changes:
        after = changes[EMERGENCY]["after"]
        guardian = _emergency(family) or Guardian(
            family=family,
            relationship=Guardian.Relationship.OTHER,
            is_emergency_contact=True,
            created_by=actor,
        )
        guardian.full_name, guardian.phone = after["full_name"], after["phone"]
        guardian.save()


def apply(change: ContactChange, *, actor: User) -> ContactChange:
    """Le secrétariat recopie les coordonnées envoyées dans la fiche de la famille."""
    return _close(
        change, ContactChange.Status.APPLIED, actor, Action.STUDENTS_CONTACT_CHANGE_APPLIED
    )


def dismiss(change: ContactChange, *, actor: User) -> ContactChange:
    """Le secrétariat garde la fiche telle quelle (ex. le parent dit ne pas avoir envoyé ça)."""
    return _close(
        change, ContactChange.Status.DISMISSED, actor, Action.STUDENTS_CONTACT_CHANGE_DISMISSED
    )
