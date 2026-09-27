"""Actions du journal d'audit : codes stables `<domaine>.<événement>`.

L'interface affiche son propre texte traduit à partir du code (M6) ; les libellés d'ici servent à
l'administration Django et à la doc de l'API. Le domaine (avant le point) sert au filtre
« Domaine » de M6.

Nouvelle action sensible (finances, élèves, notes, paie…) : l'ajouter ici, dans la tâche qui la
crée, et l'écrire avec `apps.audit.services.record()` dans le service.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Action(models.TextChoices):
    # Connexion, dans le journal de l'école de l'adresse.
    AUTH_LOGIN = "auth.login", _("Logged in")

    # Le compte d'une personne, dans le journal de chaque école où elle est active.
    ACCOUNT_PASSWORD_CHANGED = "account.password_changed", _("Password changed")
    ACCOUNT_TOTP_ENABLED = "account.totp_enabled", _("Two-factor authentication turned on")
    ACCOUNT_TOTP_CHANGED = "account.totp_changed", _("Two-factor authentication on a new phone")
    ACCOUNT_TOTP_DISABLED = "account.totp_disabled", _("Two-factor authentication turned off")
    ACCOUNT_TOTP_RESET = "account.totp_reset", _("Two-factor authentication reset by support")
    ACCOUNT_RECOVERY_CODES_RENEWED = "account.recovery_codes_renewed", _("New recovery codes")
    # Par le support Mwangaza, dans l'administration Django.
    ACCOUNT_CHANGED = "account.changed", _("Names or phone changed by support")
    ACCOUNT_DEACTIVATED = "account.deactivated", _("Account deactivated by support")
    ACCOUNT_REACTIVATED = "account.reactivated", _("Account reactivated by support")
    ACCOUNT_PASSWORD_RESET = "account.password_reset", _("Temporary password given by support")

    # Rôles de l'école.
    ROLES_CREATED = "roles.created", _("Role created")
    ROLES_UPDATED = "roles.updated", _("Role changed")
    ROLES_DELETED = "roles.deleted", _("Role deleted")

    # Comptes du personnel de l'école.
    STAFF_ADDED = "staff.added", _("Staff member added")
    STAFF_ROLES_CHANGED = "staff.roles_changed", _("Staff member's roles changed")
    STAFF_DEACTIVATED = "staff.deactivated", _("Staff member deactivated")
    STAFF_REACTIVATED = "staff.reactivated", _("Staff member reactivated")
    STAFF_ACCOUNT_CHANGED = "staff.account_changed", _("Staff member's names or phone changed")
    STAFF_PASSWORD_RESET = "staff.password_reset", _("Temporary password given")
    STAFF_TOTP_RESET = "staff.totp_reset", _("Two-factor authentication reset")

    # L'école : créée et suspendue par le super-admin ; identité changée par lui ou par l'école
    # (paramètres, M5).
    SCHOOL_CREATED = "school.created", _("School created")
    SCHOOL_UPDATED = "school.updated", _("School settings changed")
    SCHOOL_LOGO_CHANGED = "school.logo_changed", _("School logo changed")
    SCHOOL_SUSPENDED = "school.suspended", _("School suspended")
    SCHOOL_REACTIVATED = "school.reactivated", _("School reactivated")

    # Organisation scolaire (C1-C3) : années, découpage, niveaux, options, classes, matricule.
    ORGANISATION_YEAR_CREATED = "organisation.year_created", _("School year created")
    ORGANISATION_YEAR_UPDATED = "organisation.year_updated", _("School year changed")
    ORGANISATION_YEAR_DELETED = "organisation.year_deleted", _("School year deleted")
    ORGANISATION_TERMS_CHANGED = "organisation.terms_changed", _("Terms and periods changed")
    ORGANISATION_LEVEL_CREATED = "organisation.level_created", _("Level created")
    ORGANISATION_LEVEL_UPDATED = "organisation.level_updated", _("Level changed")
    ORGANISATION_LEVEL_DELETED = "organisation.level_deleted", _("Level deleted")
    ORGANISATION_LEVELS_REORDERED = "organisation.levels_reordered", _("Levels reordered")
    ORGANISATION_TRACK_CREATED = "organisation.track_created", _("Track created")
    ORGANISATION_TRACK_UPDATED = "organisation.track_updated", _("Track changed")
    ORGANISATION_TRACK_DELETED = "organisation.track_deleted", _("Track deleted")
    ORGANISATION_CLASS_CREATED = "organisation.class_created", _("Class created")
    ORGANISATION_CLASS_UPDATED = "organisation.class_updated", _("Class changed")
    ORGANISATION_CLASS_DELETED = "organisation.class_deleted", _("Class deleted")
    ORGANISATION_MATRICULE_FORMAT_CHANGED = (
        "organisation.matricule_format_changed",
        _("Student number format changed"),
    )

    # Session support « en tant qu'école » (A3) ; chaque action faite pendant la session porte
    # aussi `impersonated_by`.
    SUPPORT_STARTED = "support.started", _("Support session opened")
    SUPPORT_ENDED = "support.ended", _("Support session closed")


def domain_of(action: str) -> str:
    return action.split(".", 1)[0]


DOMAINS = sorted({domain_of(action) for action in Action.values})
