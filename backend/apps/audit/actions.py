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


def domain_of(action: str) -> str:
    return action.split(".", 1)[0]


DOMAINS = sorted({domain_of(action) for action in Action.values})
