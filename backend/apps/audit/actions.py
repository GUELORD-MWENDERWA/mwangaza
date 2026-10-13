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
    # Par le support de la plateforme, dans l'administration Django.
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
    SCHOOL_STOPPED = "school.stopped", _("School stopped")

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

    # Élèves et familles (D2-D4).
    STUDENTS_FAMILY_CREATED = "students.family_created", _("Family created")
    STUDENTS_FAMILY_UPDATED = "students.family_updated", _("Family changed")
    STUDENTS_FAMILY_DELETED = "students.family_deleted", _("Family deleted")
    STUDENTS_STUDENT_CREATED = "students.student_created", _("Student created")
    STUDENTS_STUDENT_UPDATED = "students.student_updated", _("Student changed")
    STUDENTS_ENROLLED = "students.enrolled", _("Student enrolled")
    STUDENTS_ENROLLMENT_UPDATED = "students.enrollment_updated", _("Enrollment changed")
    STUDENTS_STUDENT_IMPORTED = "students.student_imported", _("Student imported from a file")
    STUDENTS_IMPORT_CANCELLED = "students.import_cancelled", _("Student import cancelled")
    STUDENTS_STUDENT_REMOVED = "students.student_removed", _("Student removed (import cancelled)")
    STUDENTS_FAMILY_CODE_PRINTED = (
        "students.family_code_printed",
        _("Family code printed on the registration form"),
    )
    STUDENTS_FAMILY_CODE_RENEWED = "students.family_code_renewed", _("New family code")
    STUDENTS_FAMILY_INVITATION_PRINTED = (
        "students.family_invitation_printed",
        _("Portal invitation letter printed (family code)"),
    )
    STUDENTS_FAMILY_INVITATION_SHARED = (
        "students.family_invitation_shared",
        _("Portal invitation message opened (family code)"),
    )
    STUDENTS_PORTAL_SUSPENDED = "students.portal_suspended", _("Parent portal access suspended")
    STUDENTS_PORTAL_RESTORED = "students.portal_restored", _("Parent portal access restored")
    STUDENTS_CONTACT_CHANGE_APPLIED = (
        "students.contact_change_applied",
        _("Contact details sent by the parent applied"),
    )
    STUDENTS_CONTACT_CHANGE_DISMISSED = (
        "students.contact_change_dismissed",
        _("Contact details sent by the parent not applied"),
    )
    # Portail des familles (H1).
    PORTAL_ACTIVATED = "portal.activated", _("Parent portal activated")
    PORTAL_PASSWORD_RESET = "portal.password_reset", _("Parent chose a new password")
    # Frais, barèmes et taux de l'année (E1, E2, E5).
    FINANCE_FEE_TYPE_CREATED = "finance.fee_type_created", _("Fee type created")
    FINANCE_FEE_TYPE_UPDATED = "finance.fee_type_updated", _("Fee type changed")
    FINANCE_FEE_TYPE_DELETED = "finance.fee_type_deleted", _("Fee type deleted")
    FINANCE_FEE_RULE_CREATED = "finance.fee_rule_created", _("Fee rule created")
    FINANCE_FEE_RULE_UPDATED = "finance.fee_rule_updated", _("Fee rule changed")
    FINANCE_FEE_RULE_DELETED = "finance.fee_rule_deleted", _("Fee rule deleted")
    FINANCE_FEE_RULES_COPIED = (
        "finance.fee_rules_copied",
        _("Fee rules copied from another school year"),
    )
    FINANCE_EXCHANGE_RATE_SET = "finance.exchange_rate_set", _("Exchange rate set")
    FINANCE_CHARGES_RESCHEDULED = "finance.charges_rescheduled", _("Custom schedule set")
    FINANCE_DISCOUNT_GRANTED = "finance.discount_granted", _("Discount granted")
    FINANCE_DISCOUNT_REVOKED = "finance.discount_revoked", _("Discount revoked")
    # Caisses et paiements (F1-F2).
    FINANCE_CASH_REGISTER_CREATED = "finance.cash_register_created", _("Cash register created")
    FINANCE_CASH_REGISTER_UPDATED = "finance.cash_register_updated", _("Cash register changed")
    FINANCE_CASH_SESSION_OPENED = "finance.cash_session_opened", _("Cash session opened")
    FINANCE_CASH_SESSION_CLOSED = "finance.cash_session_closed", _("Cash session closed")
    FINANCE_PAYMENT_RECORDED = "finance.payment_recorded", _("Payment recorded")
    # Reprise en cours d'année (E6) : payé avant que l'école n'utilise l'application, hors caisse.
    FINANCE_PRIOR_PAYMENT_RECORDED = (
        "finance.prior_payment_recorded",
        _("Earlier payment recorded (not at the cash desk)"),
    )
    # Reçus (F6) : chaque duplicata est noté.
    FINANCE_PAYMENT_REPRINTED = "finance.payment_reprinted", _("Receipt reprinted")
    # Annulations (F7) : demande, décision, duplicata du reçu d'annulation.
    FINANCE_CANCELLATION_REQUESTED = (
        "finance.cancellation_requested",
        _("Payment cancellation requested"),
    )
    FINANCE_PAYMENT_CANCELLED = "finance.payment_cancelled", _("Payment cancelled")
    FINANCE_CANCELLATION_REJECTED = (
        "finance.cancellation_rejected",
        _("Payment cancellation refused"),
    )
    FINANCE_CANCELLATION_REPRINTED = (
        "finance.cancellation_reprinted",
        _("Cancellation receipt reprinted"),
    )
    # Crédits d'élèves (M14) : argent reçu en trop, puis utilisé ou annulé.
    FINANCE_CREDIT_CREATED = "finance.credit_created", _("Student credit created")
    FINANCE_CREDIT_USED = "finance.credit_used", _("Student credit used")
    FINANCE_CREDIT_VOIDED = "finance.credit_voided", _("Student credit voided")
    # Impayés (G1) : chaque export (Excel, PDF) est noté, il contient des données personnelles.
    FINANCE_UNPAID_EXPORTED = "finance.unpaid_exported", _("Unpaid fees exported")
    # Situation financière (G2) : chaque PDF est noté, comme les exports des impayés.
    FINANCE_STATEMENT_PRINTED = "finance.statement_printed", _("Financial statement printed")

    # Annonces aux familles (H4) : publiées puis jamais modifiées, seulement archivées.
    ANNOUNCEMENTS_PUBLISHED = "announcements.published", _("Announcement published")
    ANNOUNCEMENTS_ARCHIVED = "announcements.archived", _("Announcement archived")
    # Convocations des parents (5.7) : jamais modifiées, seulement annulées.
    SUMMONS_ISSUED = "announcements.summons_issued", _("Parents summoned")
    SUMMONS_CANCELLED = "announcements.summons_cancelled", _("Summons cancelled")

    # Appareils (« Se souvenir de cet appareil », M4).
    DEVICES_REGISTERED = "devices.registered", _("Device remembered")
    DEVICES_REVOKED = "devices.revoked", _("Device disconnected")

    # Le journal lui-même (M6) : chaque export est noté.
    AUDIT_EXPORTED = "audit.exported", _("Audit log exported")

    # Session support « en tant qu'école » (A3) ; chaque action faite pendant la session porte
    # aussi `impersonated_by`.
    SUPPORT_STARTED = "support.started", _("Support session opened")
    SUPPORT_ENDED = "support.ended", _("Support session closed")


def domain_of(action: str) -> str:
    return action.split(".", 1)[0]


DOMAINS = sorted({domain_of(action) for action in Action.values})


class PlatformAction(models.TextChoices):
    """Actions du journal de la plateforme (`PlatformAuditLog`, sans école) : console du
    super-admin. À part de `Action` : le journal d'une école ne les propose pas."""

    PLATFORM_UPDATED = "platform.updated", _("Platform identity changed")
    PLATFORM_LOGO_CHANGED = "platform.logo_changed", _("Platform logo changed")
    PLATFORM_ICON_CHANGED = "platform.icon_changed", _("Application icon changed")
    # Écoles (5.3) : identité et abonnement ; l'école en voit une partie dans son propre journal.
    SCHOOL_CREATED = "school.created", _("School created")
    SCHOOL_UPDATED = "school.updated", _("School or subscription changed")
    SCHOOL_SUSPENDED = "school.suspended", _("School suspended")
    SCHOOL_REACTIVATED = "school.reactivated", _("School reactivated")
    SCHOOL_STOPPED = "school.stopped", _("School stopped")
    SCHOOL_DELETED = "school.deleted", _("Sandbox or demonstration space deleted")
    # Comptes (5.4.1), par le support (console ou administration Django) ; chaque école où la
    # personne est active le voit aussi dans son journal (`Action.ACCOUNT_*`).
    ACCOUNT_CHANGED = "account.changed", _("Names or phone changed by support")
    ACCOUNT_DEACTIVATED = "account.deactivated", _("Account deactivated by support")
    ACCOUNT_REACTIVATED = "account.reactivated", _("Account reactivated by support")
    ACCOUNT_PASSWORD_RESET = "account.password_reset", _("Temporary password given by support")
    ACCOUNT_TOTP_RESET = "account.totp_reset", _("Two-factor authentication reset by support")
    # Appareils (5.4.2) : l'école de l'appareil le voit aussi dans son journal
    # (`Action.DEVICES_REVOKED`).
    DEVICE_REVOKED = "device.revoked", _("Device disconnected by support")
    # Annonces de la plateforme aux écoles (5.4.3).
    ANNOUNCEMENT_PUBLISHED = "announcement.published", _("Announcement to schools published")
    ANNOUNCEMENT_ARCHIVED = "announcement.archived", _("Announcement to schools archived")
    # Accès d'un compte super-admin (S.3.1), où qu'il se connecte : console, administration
    # Django, adresse d'une école avant une session support.
    ACCESS_LOGIN = "access.login", _("Platform account logged in")
    ACCESS_CODE_REFUSED = "access.code_refused", _("Two-factor code refused on a platform account")
    ACCESS_ADDRESS_REFUSED = (
        "access.address_refused",
        _("Platform account refused from an unauthorised address"),
    )


PLATFORM_DOMAINS = sorted({domain_of(action) for action in PlatformAction.values})
