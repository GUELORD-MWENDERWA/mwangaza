"""Codes de permissions et rôles système (`docs/04-modele-de-donnees.md` § 8).

Les rôles système sont copiés dans chaque école à sa création ; l'école peut ensuite changer leurs
permissions, les renommer et créer ses propres rôles (B2). L'interface affiche ses propres libellés
traduits à partir des codes ; ceux d'ici servent à l'administration Django et à la doc de l'API.

Nouveau code de permission : l'ajouter ici, aux rôles système qui doivent l'avoir, et aux rôles
système des écoles existantes par une migration de données.
"""

from dataclasses import dataclass

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

PERMISSIONS: dict[str, Promise] = {
    "school.configure": _("Configure the school (name, logo, colour, currencies, receipts)"),
    "classes.manage": _("Manage years, terms, levels, tracks, classes and student numbers"),
    "roles.manage": _("Manage staff accounts and roles"),
    "students.view": _("View students"),
    "students.edit": _("Edit students"),
    "students.import": _("Import students from Excel"),
    "finance.configure_fees": _("Configure fees"),
    "finance.set_exchange_rate": _("Set the exchange rate"),
    "finance.grant_discount": _("Grant discounts"),
    "finance.collect_payment": _("Collect payments"),
    "finance.request_cancellation": _("Request a payment cancellation"),
    "finance.approve_cancellation": _("Approve a payment cancellation"),
    "finance.close_register": _("Close a cash register"),
    "finance.view_reports": _("View financial reports"),
    "announcements.publish": _("Publish announcements"),
    "audit.view": _("View the audit log"),
}
PERMISSION_CHOICES = list(PERMISSIONS.items())

# Paramètres de l'école : nom, logo, couleur, devises, fuseau (M5).
SCHOOL_CONFIGURE = "school.configure"
# Organisation scolaire : années, découpage, niveaux, options, classes, matricule (C1-C3).
CLASSES_MANAGE = "classes.manage"
# Gérer les rôles et les comptes du personnel : une école garde toujours un compte actif qui l'a.
ROLES_MANAGE = "roles.manage"
# Lire le journal d'audit de l'école (M6).
AUDIT_VIEW = "audit.view"
# Élèves, familles et inscriptions (D2-D4) : lire, puis créer et modifier.
STUDENTS_VIEW = "students.view"
STUDENTS_EDIT = "students.edit"
STUDENTS_IMPORT = "students.import"
# Frais, barèmes et taux de l'année (E1-E5).
FINANCE_CONFIGURE_FEES = "finance.configure_fees"
FINANCE_SET_EXCHANGE_RATE = "finance.set_exchange_rate"
FINANCE_GRANT_DISCOUNT = "finance.grant_discount"
FINANCE_COLLECT_PAYMENT = "finance.collect_payment"
FINANCE_VIEW_REPORTS = "finance.view_reports"
FINANCE_APPROVE_CANCELLATION = "finance.approve_cancellation"
# Crédits d'élèves (M14) : tous lus avec l'un de ces droits ; utilisés par le comptable, ou à la
# caisse par le caissier (3.6.2), qui voit ceux de l'élève avec ses frais dus (`CHARGES_READ`).
CREDITS_READ = (FINANCE_VIEW_REPORTS, FINANCE_APPROVE_CANCELLATION)
CREDITS_USE = (FINANCE_APPROVE_CANCELLATION, FINANCE_COLLECT_PAYMENT)
# Écran « Frais et barèmes » (entrée du menu) : lu avec l'un de ces droits.
FEES_READ = (FINANCE_CONFIGURE_FEES, FINANCE_SET_EXCHANGE_RATE, FINANCE_GRANT_DISCOUNT)
# Frais dus d'un élève (fiche, caisse, réductions) : lus avec l'un de ces droits.
CHARGES_READ = (
    FINANCE_COLLECT_PAYMENT,
    FINANCE_GRANT_DISCOUNT,
    FINANCE_CONFIGURE_FEES,
    FINANCE_VIEW_REPORTS,
)

# Double authentification obligatoire (B4) pour un compte qui a l'un de ces droits dans une école :
# l'argent, les réglages, les comptes, le journal d'audit. Par défaut : directeur, comptable,
# caissier et promoteur ; un rôle créé par l'école avec l'un de ces droits l'exige aussi.
TOTP_PERMISSIONS = frozenset(
    {SCHOOL_CONFIGURE, ROLES_MANAGE, AUDIT_VIEW}
    | {code for code in PERMISSIONS if code.startswith("finance.")}
)


@dataclass(frozen=True)
class SystemRole:
    label: Promise
    permissions: tuple[str, ...]


SYSTEM_ROLES: dict[str, SystemRole] = {
    "head": SystemRole(
        _("Head of school"),
        (
            "school.configure",
            "classes.manage",
            "roles.manage",
            "students.view",
            "students.edit",
            "students.import",
            "finance.configure_fees",
            "finance.set_exchange_rate",
            "finance.grant_discount",
            "finance.approve_cancellation",
            "finance.view_reports",
            "announcements.publish",
            "audit.view",
        ),
    ),
    "study_director": SystemRole(
        _("Director of studies"),
        ("classes.manage", "students.view", "students.edit", "announcements.publish"),
    ),
    "discipline_master": SystemRole(
        _("Discipline master"), ("students.view", "announcements.publish")
    ),
    "accountant": SystemRole(
        _("Accountant"),
        (
            "students.view",
            "finance.configure_fees",
            "finance.set_exchange_rate",
            "finance.grant_discount",
            "finance.collect_payment",
            "finance.request_cancellation",
            "finance.approve_cancellation",
            "finance.close_register",
            "finance.view_reports",
        ),
    ),
    "cashier": SystemRole(
        _("Cashier"),
        (
            "students.view",
            "finance.collect_payment",
            "finance.request_cancellation",
            "finance.close_register",
        ),
    ),
    "secretary": SystemRole(
        _("Secretary"),
        ("students.view", "students.edit", "students.import", "announcements.publish"),
    ),
    "promoter": SystemRole(_("Promoter"), ("students.view", "finance.view_reports", "audit.view")),
    # Enseignant : aucune fonction en V1.0 (B1). Parent : rien dans la Gestion, le portail lui
    # montre ses enfants.
    "teacher": SystemRole(_("Teacher"), ()),
    "parent": SystemRole(_("Parent"), ()),
}
SYSTEM_ROLE_CODES = tuple(SYSTEM_ROLES)


def sorted_permissions(codes) -> list[str]:
    """Codes sans doublon, dans l'ordre de `PERMISSIONS` ; `ValueError` pour un code inconnu."""
    wanted = set(codes)
    unknown = wanted - PERMISSIONS.keys()
    if unknown:
        raise ValueError(f"Codes de permission inconnus : {sorted(unknown)}")
    return [code for code in PERMISSIONS if code in wanted]
