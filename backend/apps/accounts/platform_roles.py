"""Droits et rôles de l'équipe de la plateforme (EQ.1, `05` § 6.3 bis).

Contrairement aux rôles d'une école (`roles.py`), les rôles de l'équipe sont **fixes dans le
code** : l'équipe reste petite, et des droits libres sur la console seraient un risque. Un membre
de l'équipe est un compte de la plateforme (`User.is_platform_admin`) qui a un ou plusieurs de ces
rôles (`User.platform_roles`) ; chaque point de la console demande un de ces droits
(`permissions.HasPlatformPermission`). L'interface traduit les codes ; les libellés d'ici servent
à l'administration Django et à la doc de l'API.
"""

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

SCHOOLS_VIEW = "platform.schools.view"
SCHOOLS_MANAGE = "platform.schools.manage"
SCHOOLS_STOP = "platform.schools.stop"
ACCOUNTS_SUPPORT = "platform.accounts.support"
DEMOS_MANAGE = "platform.demos.manage"
LEADS_MANAGE = "platform.leads.manage"
SITE_EDIT = "platform.site.edit"
NEWS_PUBLISH = "platform.news.publish"
HEALTH_VIEW = "platform.health.view"
AUDIT_VIEW = "platform.audit.view"
BILLING_MANAGE = "platform.billing.manage"
IDENTITY_EDIT = "platform.identity.edit"
TEAM_MANAGE = "platform.team.manage"

PLATFORM_PERMISSIONS: dict[str, Promise] = {
    SCHOOLS_VIEW: _("View the schools and the dashboard"),
    SCHOOLS_MANAGE: _("Create, change, suspend and reopen a live school"),
    SCHOOLS_STOP: _("Stop a live school"),
    ACCOUNTS_SUPPORT: _("Help accounts (names, temporary password, two-factor) and open support"),
    DEMOS_MANAGE: _("Manage sandbox and demonstration spaces"),
    LEADS_MANAGE: _("Handle the demo requests of the website"),
    SITE_EDIT: _("Edit the contents of the website"),
    NEWS_PUBLISH: _("Publish announcements to schools"),
    HEALTH_VIEW: _("View the server health and the devices, disconnect a device"),
    AUDIT_VIEW: _("View the platform log and receive its alerts"),
    BILLING_MANAGE: _("Manage subscriptions and invoices"),
    IDENTITY_EDIT: _("Change the identity of the platform"),
    TEAM_MANAGE: _("Manage the platform team"),
}

OWNER = "owner"

# Rôle → (libellé, droits). Les actions sans retour (arrêter un espace réel, l'équipe, l'identité)
# restent au seul propriétaire.
PLATFORM_ROLES: dict[str, tuple[Promise, frozenset[str]]] = {
    OWNER: (_("Lead administrator"), frozenset(PLATFORM_PERMISSIONS)),
    "technical": (_("Technical"), frozenset({HEALTH_VIEW, AUDIT_VIEW, SCHOOLS_VIEW})),
    "support": (
        _("Support"),
        frozenset({SCHOOLS_VIEW, ACCOUNTS_SUPPORT, DEMOS_MANAGE}),
    ),
    # Ni la liste des espaces réels ni leurs données : seulement les essais et démonstrations.
    "commercial": (_("Sales"), frozenset({LEADS_MANAGE, DEMOS_MANAGE})),
    "communication": (_("Communication"), frozenset({SITE_EDIT, NEWS_PUBLISH})),
    # Abonnements et factures (ABO, V1.3) : le droit ne garde encore aucun point d'API.
    "finance": (_("Finance"), frozenset({BILLING_MANAGE, SCHOOLS_VIEW})),
}

ROLE_CHOICES = [(code, label) for code, (label, _rights) in PLATFORM_ROLES.items()]


def permissions_of(roles) -> frozenset[str]:
    """Droits donnés par ces rôles ; un code inconnu (rôle retiré du code) ne donne rien."""
    rights: set[str] = set()
    for role in roles:
        if role in PLATFORM_ROLES:
            rights |= PLATFORM_ROLES[role][1]
    return frozenset(rights)


def roles_with(permission: str) -> list[str]:
    """Rôles qui portent ce droit (destinataires d'une alerte, filtre en base)."""
    return sorted(code for code, (_label, rights) in PLATFORM_ROLES.items() if permission in rights)
