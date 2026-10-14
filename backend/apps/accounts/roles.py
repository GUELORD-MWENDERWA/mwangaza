"""Codes de permissions et modèle de départ des rôles (`docs/04-modele-de-donnees.md` § 8).

Un rôle est un nom et des permissions, propres à l'école : aucun rôle n'est imposé par le code.
Le modèle de départ (`STARTER_ROLES`) est copié dans une école à sa création ; elle renomme,
modifie et supprime ensuite ces rôles, et crée les siens (B2). L'interface traduit les codes de
permission ; les libellés d'ici servent à l'administration Django et à la doc de l'API.

Nouveau code de permission : l'ajouter ici, aux rôles du modèle de départ qui doivent l'avoir,
et, par une migration de données, aux rôles des écoles existantes qui ont déjà un droit voisin
(jamais d'après le nom d'un rôle : l'école l'a peut-être changé).
"""

from dataclasses import dataclass

from django.conf import settings
from django.utils import translation
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

PERMISSIONS: dict[str, Promise] = {
    "school.configure": _("Configure the school (name, logo, colour, currencies, receipts)"),
    "classes.manage": _("Manage years, terms, levels, tracks, classes and student numbers"),
    "courses.configure": _("Configure courses, maxima and teachers of each class"),
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
    "finance.import_prior_payments": _("Record what students paid before the school started here"),
    "announcements.publish": _("Publish announcements"),
    "audit.view": _("View the audit log"),
}
PERMISSION_CHOICES = list(PERMISSIONS.items())
# Droits sensibles (S.3.1) : les rôles et l'argent. L'école est prévenue quand un compte en reçoit
# un (`notifications/events.py`).
SENSITIVE_PERMISSIONS = frozenset(
    code for code in PERMISSIONS if code == "roles.manage" or code.startswith("finance.")
)

# Paramètres de l'école : nom, logo, couleur, devises, fuseau (M5).
SCHOOL_CONFIGURE = "school.configure"
# Organisation scolaire : années, découpage, niveaux, options, classes, matricule (C1-C3).
CLASSES_MANAGE = "classes.manage"
# Cours de chaque classe : maxima, heures, enseignants (8.1).
COURSES_CONFIGURE = "courses.configure"
# Gérer les rôles et les comptes du personnel : une école garde toujours un compte actif qui l'a.
ROLES_MANAGE = "roles.manage"
# Publier et archiver les annonces aux familles (H4).
ANNOUNCEMENTS_PUBLISH = "announcements.publish"
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
FINANCE_REQUEST_CANCELLATION = "finance.request_cancellation"
# Reprise en cours d'année (E6) : importer ce que chaque élève avait déjà payé, hors caisse.
FINANCE_IMPORT_PRIOR_PAYMENTS = "finance.import_prior_payments"
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
class StarterRole:
    label: Promise
    permissions: tuple[str, ...]


# Modèle de départ (`docs/04` § 8) : rôles copiés une fois dans une école neuve, qui les renomme,
# les modifie et les supprime ensuite comme tout autre rôle. La clé ne sert qu'ici, aux données de
# démonstration et aux tests : un rôle n'a ni code en base ni dans l'API.
STARTER_ROLES: dict[str, StarterRole] = {
    "head": StarterRole(
        _("Head of school"),
        (
            "school.configure",
            "classes.manage",
            "courses.configure",
            "roles.manage",
            "students.view",
            "students.edit",
            "students.import",
            "finance.configure_fees",
            "finance.set_exchange_rate",
            "finance.grant_discount",
            "finance.approve_cancellation",
            "finance.view_reports",
            "finance.import_prior_payments",
            "announcements.publish",
            "audit.view",
        ),
    ),
    "study_director": StarterRole(
        _("Director of studies"),
        (
            "classes.manage",
            "courses.configure",
            "students.view",
            "students.edit",
            "announcements.publish",
        ),
    ),
    "discipline_master": StarterRole(
        _("Discipline master"), ("students.view", "announcements.publish")
    ),
    "accountant": StarterRole(
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
            "finance.import_prior_payments",
        ),
    ),
    "cashier": StarterRole(
        _("Cashier"),
        (
            "students.view",
            "finance.collect_payment",
            "finance.request_cancellation",
            "finance.close_register",
        ),
    ),
    "secretary": StarterRole(
        _("Secretary"),
        ("students.view", "students.edit", "students.import", "announcements.publish"),
    ),
    "promoter": StarterRole(_("Promoter"), ("students.view", "finance.view_reports", "audit.view")),
    # Enseignant : aucune fonction en V1.0 (B1). Parent : rien dans la Gestion, le portail lui
    # montre ses enfants.
    "teacher": StarterRole(_("Teacher"), ()),
    "parent": StarterRole(_("Parent"), ()),
}


def starter_role_name(key: str) -> str:
    """Nom donné au rôle de départ `key` dans une école neuve : celui de la langue par défaut de
    la plateforme, quelle que soit la langue de qui crée l'école."""
    with translation.override(settings.LANGUAGE_CODE):
        return str(STARTER_ROLES[key].label)


def sorted_permissions(codes) -> list[str]:
    """Codes sans doublon, dans l'ordre de `PERMISSIONS` ; `ValueError` pour un code inconnu."""
    wanted = set(codes)
    unknown = wanted - PERMISSIONS.keys()
    if unknown:
        raise ValueError(f"Codes de permission inconnus : {sorted(unknown)}")
    return [code for code in PERMISSIONS if code in wanted]
