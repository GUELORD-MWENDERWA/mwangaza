"""Notifications des événements de l'école (5.6.1), écrites au moment de l'action, dans sa
transaction : paiement reçu et annonce pour le parent (Portail), écart de caisse et annulation à
valider pour le personnel qui en a le droit (Gestion). Le texte est écrit dans la langue de chaque
destinataire ; l'envoi sur l'écran suit la validation (`push.notify`).

Appelées depuis les services, dans l'école courante. Les envois à heure fixe (échéance proche,
retard, caisse encore ouverte) : `scheduled.py` (5.6.2)."""

from collections import defaultdict
from collections.abc import Callable, Iterable

from django.db.models import QuerySet
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.core.money import format_amount
from apps.core.tenancy import require_current_school
from apps.finance.models import CancellationRequest, CashClosing, CashSession, Payment
from apps.notifications import push
from apps.notifications.models import Announcement, Notification
from apps.students.models import Family

App = Notification.App
Kind = Notification.Kind


def send(users: Iterable[User], *, app: str, kind: str, url: str, text: Callable) -> int:
    """`text()` rend (titre, message) ; appelée une fois par langue des destinataires. Rend le
    nombre de notifications créées."""
    by_language = defaultdict(list)
    for user in users:
        by_language[user.language].append(user)
    school = require_current_school()
    created = 0
    for language, group in by_language.items():
        with translation.override(language):
            title, body = text()
        created += len(
            push.notify(group, school=school, app=app, kind=kind, title=title, body=body, url=url)
        )
    return created


def _parents(families: QuerySet[Family]) -> QuerySet[User]:
    """Comptes du portail de ces familles ; aucun pour une famille dont l'école a suspendu
    l'accès (elle ne voit plus rien de l'école)."""
    with_access = families.filter(portal_suspended_at__isnull=True)
    return User.objects.filter(is_active=True, pk__in=with_access.values("primary_user"))


def staff(kind: str, *, but: User | None = None) -> QuerySet[User]:
    """Personnel actif de l'école qui a le droit de recevoir cette sorte, sauf l'auteur de
    l'action (il le sait déjà)."""
    users = User.objects.filter(
        is_active=True,
        memberships__school=require_current_school(),
        memberships__is_active=True,
        memberships__roles__permissions__contains=[push.STAFF_KINDS[kind]],
    )
    return (users.exclude(pk=but.pk) if but else users).distinct()


def payment_received(payment: Payment) -> None:
    """Paiement encaissé : le parent le voit sur son téléphone et ouvre la page de l'enfant, où
    sont son solde et le reçu en PDF."""
    student = payment.enrollment.student
    parents = _parents(Family.objects.filter(pk=student.family_id))
    amount = format_amount(payment.received_amount_minor, payment.received_currency)
    send(
        parents,
        app=App.PORTAIL,
        kind=Kind.PAYMENT_RECEIVED,
        url=f"/children/{student.pk}",
        text=lambda: (
            _("Payment received: %(amount)s") % {"amount": amount},
            _("%(student)s · receipt %(number)s")
            % {"student": student, "number": payment.receipt_number},
        ),
    )


def announcement_published(announcement: Announcement, families: QuerySet[Family]) -> None:
    """Annonce de l'école : aux familles visées qui ont un compte. Le texte est celui de l'école,
    tel qu'elle l'a écrit."""
    send(
        _parents(families),
        app=App.PORTAIL,
        kind=Kind.ANNOUNCEMENT,
        url="/announcements",
        text=lambda: (announcement.title, announcement.body),
    )


def cash_difference(session: CashSession, closings: list[CashClosing], *, actor: User) -> None:
    """Clôture dont l'écart dépasse, dans une devise, le seuil choisi par l'école
    (`schools/alerts.py`) : à ceux qui lisent les rapports."""
    thresholds = require_current_school().alerts["difference_minor"]
    beyond = [
        line for line in closings if abs(line.difference_minor) > thresholds.get(line.currency, 0)
    ]
    if not beyond:
        return
    amounts = " ; ".join(
        ("+" if line.difference_minor > 0 else "")
        + format_amount(line.difference_minor, line.currency)
        for line in beyond
    )
    register = str(session.cash_register)
    send(
        staff(Kind.CASH_DIFFERENCE, but=actor),
        app=App.GESTION,
        kind=Kind.CASH_DIFFERENCE,
        url="/cash-closings",
        text=lambda: (
            _("Cash difference: %(register)s") % {"register": register},
            _("%(cashier)s closed the register with a difference of %(amounts)s.")
            % {"cashier": actor, "amounts": amounts},
        ),
    )


def cancellation_requested(request: CancellationRequest) -> None:
    """Demande d'annulation : à ceux qui la valident. Le message dit quand le caissier dépasse,
    ce jour-là, le nombre de demandes que l'école a choisi de signaler."""
    payment, cashier = request.payment, request.requested_by
    # Le jour de la demande : celui de l'appareil quand elle a été faite hors ligne.
    day = timezone.localtime(request.requested_at).date()
    count = CancellationRequest.objects.filter(requested_by=cashier, requested_at__date=day).count()
    values = {
        "cashier": cashier,
        "count": count,
        "amount": format_amount(payment.received_amount_minor, payment.received_currency),
        "reason": request.reason,
    }
    over = count > require_current_school().alerts["cancellations_per_day"]

    def text() -> tuple[str, str]:
        body = (
            _("%(cashier)s: request no. %(count)s of the day · %(amount)s · %(reason)s")
            if over
            else _("%(cashier)s · %(amount)s · %(reason)s")
        )
        title = _("Cancellation to approve: %(number)s") % {"number": payment.receipt_number}
        return title, body % values

    send(
        staff(Kind.CANCELLATION_REQUEST, but=cashier),
        app=App.GESTION,
        kind=Kind.CANCELLATION_REQUEST,
        url="/cancellations",
        text=text,
    )
