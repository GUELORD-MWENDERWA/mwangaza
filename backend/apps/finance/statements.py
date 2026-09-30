"""Situation financière d'un élève (G2, maquette `situation-financiere`) : ce qu'il doit pour
l'année, payé, en retard et à venir, par devise jamais additionnée, avec ses paiements ; même
calcul que l'onglet Finances (2.7 : réductions déduites, paiements annulés exclus). Imprimée depuis
la fiche de l'élève, ou groupée depuis les Impayés (une page par élève).

Son QR code ouvre `/v/s/<jeton>` sur l'adresse de l'école : le jeton, signé par le serveur avec
un sel propre à l'école, porte l'inscription, la date et les montants imprimés ; la page publique
les montre avec l'élève en initiales (`verification.verify_statement`)."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.core import signing
from django.urls import reverse

from apps.core.tenancy import require_current_school
from apps.finance import services, unpaid
from apps.finance.models import Payment, StudentCharge
from apps.students.models import Enrollment, Guardian

# Au-delà, l'adresse de l'aperçu devient trop longue : une classe entière tient en dessous.
MAX_STUDENTS = 100


@dataclass
class Statement:
    enrollment: Enrollment
    day: date
    charges: list[StudentCharge]
    balance: services.Balance
    payments: list[Payment]
    guardian: Guardian | None


def statements(enrollment_ids) -> list[Statement]:
    """Situations des inscriptions, par classe puis par nom ; cinq requêtes quel que soit leur
    nombre (inscriptions, frais dus, réductions, paiements, tuteurs principaux)."""
    enrollments = list(
        Enrollment.objects.filter(pk__in=enrollment_ids).select_related(
            "student", "academic_year", "class_group__level", "class_group__track"
        )
    )
    enrollments.sort(key=lambda e: (unpaid.class_key(e), e.class_group.section, unpaid.surname(e)))
    ids = [enrollment.pk for enrollment in enrollments]
    charges = services.charges_by_enrollment(ids, light=True)
    payments = defaultdict(list)
    for payment in (
        Payment.objects.filter(enrollment_id__in=ids)
        .select_related("cancellation")
        .order_by("paid_at", "id")
    ):
        payments[payment.enrollment_id].append(payment)
    guardians = {
        guardian.family_id: guardian
        for guardian in Guardian.objects.filter(
            family_id__in={e.student.family_id for e in enrollments}, is_primary=True
        )
    }
    day = services.today()
    return [
        Statement(
            enrollment=enrollment,
            day=day,
            charges=[charge for charge in charges[enrollment.pk] if charge.state],
            balance=services.balance(charges[enrollment.pk]),
            payments=payments[enrollment.pk],
            guardian=guardians.get(enrollment.student.family_id),
        )
        for enrollment in enrollments
    ]


def _salt() -> str:
    return f"finance.statement:{require_current_school().pk}"


def verification_path(statement: Statement) -> str:
    """`/v/s/<jeton>` : inscription, date, et par devise le retard et le reste de l'année."""
    amounts = [
        [item.currency, item.overdue_minor, item.remaining_minor]
        for item in statement.balance.currencies
    ]
    data = {"e": str(statement.enrollment.pk), "d": statement.day.isoformat(), "a": amounts}
    token = signing.dumps(data, salt=_salt(), compress=True)
    return reverse("statement-verification", args=[token])


def read_token(token: str) -> dict | None:
    """Contenu d'un jeton signé pour l'école de l'adresse ; `None` s'il est modifié, illisible ou
    signé pour une autre école."""
    try:
        return signing.loads(token, salt=_salt())
    except signing.BadSignature:
        return None
