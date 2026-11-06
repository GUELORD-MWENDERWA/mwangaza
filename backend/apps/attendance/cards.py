"""Cartes d'élève et du personnel (6.1) et impression d'une sélection (A.5).

Le QR d'une carte porte `MWZ1:` suivi d'un jeton aléatoire de 128 bits (32 signes hexadécimaux),
jamais le matricule. Le serveur ne garde que l'empreinte SHA-256 du jeton et ses 4 derniers
signes : le jeton n'existe en clair que dans le PDF fait à l'émission (rangé un jour au plus comme
tout document imprimé, `core/printing.py`). Réimprimer = émettre une nouvelle carte, l'ancienne
est révoquée (« remplacée »). L'appareil de pointage reçoit les empreintes (`roster`), hache ce
qu'il lit et décide seul, même sans réseau.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, Max, OuterRef, Q, QuerySet
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Membership, User
from apps.attendance.models import IdCard
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import qr_code, school_header
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.schools import colors, organisation
from apps.schools.models import AcademicYear, School
from apps.students.documents import photo_uri
from apps.students.models import Enrollment, Student

TOKEN_PREFIX = "MWZ1:"
MAX_PER_PRINT = 100
PER_SHEET = 10  # planche A4 : 2 colonnes, 5 rangées de cartes de 85,6 sur 54 mm
SHEET, CARD = "sheet", "card"
ROSTER_PAGE = 1000

NO_YEAR = ApiError("no_current_year", gettext_lazy("Set the current school year first."), 409)
ALREADY_REVOKED = ApiError(
    "card_already_revoked", gettext_lazy("This card is already revoked."), 409
)
ISSUE_CONFLICT = ApiError(
    "card_issue_conflict",
    gettext_lazy("Someone issued a card for the same person at the same time: try again."),
    409,
)


@dataclass
class Issued:
    card: IdCard
    token: str


def new_token() -> str:
    return secrets.token_hex(16).upper()


def fingerprint(token: str) -> str:
    """Empreinte gardée par le serveur et l'appareil : SHA-256 du jeton (sans `MWZ1:`)."""
    return hashlib.sha256(token.encode()).hexdigest()


def active() -> QuerySet[IdCard]:
    return IdCard.objects.filter(revoked_at__isnull=True)


def current_enrollments() -> QuerySet[Enrollment]:
    """Élèves inscrits dans l'année en cours (les seuls qui reçoivent une carte et pointent)."""
    year = organisation.current_year()
    if year is None:
        return Enrollment.objects.none()
    return Enrollment.objects.filter(academic_year=year, status=Enrollment.Status.ACTIVE)


def staff() -> QuerySet[Membership]:
    """Personnel actif de l'école courante (les parents n'ont pas de compte du personnel)."""
    return Membership.objects.filter(school=require_current_school(), is_active=True)


def has_active_card(field: str, outer: str = "pk") -> Exists:
    """Annotation : la personne (`student` ou `member`) a une carte active."""
    return Exists(active().filter(**{field: OuterRef(outer)}))


def holder_name(card: IdCard) -> str:
    if card.student_id:
        return card.student.full_name
    return card.member.user.get_full_name()


def _label(card: IdCard) -> str:
    return f"{holder_name(card)} · {card}"


def valid_until(school: School, year: AcademicYear) -> date:
    configured = school.card["valid_until"]
    return date.fromisoformat(configured) if configured else year.ends_on


def issue(
    *, actor: User, enrollments: list[Enrollment] = (), members: list[Membership] = ()
) -> list[Issued]:
    """Une nouvelle carte pour chaque élève inscrit et chaque membre du personnel, dans l'ordre
    donné ; la carte active de chacun est révoquée (« remplacée »). Écritures en masse, une
    entrée au journal par carte (jamais le jeton)."""
    school = require_current_school()
    year = organisation.current_year()
    if year is None:
        raise BusinessError(NO_YEAR)
    if not enrollments and not members:
        raise ValidationError({"students": _("Choose at least one person.")})
    if len(enrollments) + len(members) > MAX_PER_PRINT:
        raise ValidationError(
            {"students": _("At most %(max)s cards at a time.") % {"max": MAX_PER_PRINT}}
        )
    until = valid_until(school, year)
    now = timezone.now()
    students = [enrollment.student for enrollment in enrollments]
    try:
        with transaction.atomic():
            old = list(
                active()
                .filter(Q(student__in=students) | Q(member__in=members))
                .select_related("student", "member__user")
                .select_for_update(of=("self",))
            )
            for card in old:
                card.revoked_at, card.revoked_by, card.updated_at = now, actor, now
                card.revoke_reason = IdCard.RevokeReason.REPLACED
            IdCard.objects.bulk_update(
                old, ["revoked_at", "revoked_by", "revoke_reason", "updated_at"]
            )
            issued = []
            for holder in [*students, *members]:
                token = new_token()
                card = IdCard(
                    token_hash=fingerprint(token),
                    last4=token[-4:],
                    valid_until=until,
                    created_by=actor,
                    **({"student": holder} if isinstance(holder, Student) else {"member": holder}),
                )
                issued.append(Issued(card, token))
            IdCard.objects.bulk_create([item.card for item in issued])
    except IntegrityError:
        raise BusinessError(ISSUE_CONFLICT) from None
    if old:
        audit.record_many(
            Action.CARD_REVOKED,
            [(card, {"reason": card.revoke_reason}) for card in old],
            actor=actor,
            label=_label,
        )
    audit.record_many(
        Action.CARD_ISSUED,
        [
            (item.card, {"last4": item.card.last4, "valid_until": until.isoformat()})
            for item in issued
        ],
        actor=actor,
        label=_label,
    )
    return issued


def revoke(card: IdCard, *, actor: User, reason: str) -> IdCard:
    """Carte perdue ou départ : refusée à tous les pointages dès maintenant. Une carte n'est
    jamais réactivée : on en émet une nouvelle."""
    with transaction.atomic():
        card = IdCard.objects.select_for_update(of=("self",)).get(pk=card.pk)
        if card.revoked_at is not None:
            raise BusinessError(ALREADY_REVOKED)
        card.revoked_at, card.revoked_by, card.revoke_reason = timezone.now(), actor, reason
        card.save(update_fields=["revoked_at", "revoked_by", "revoke_reason", "updated_at"])
        card = IdCard.objects.select_related("student", "member__user").get(pk=card.pk)
        audit.record(
            Action.CARD_REVOKED, card, actor=actor, after={"reason": reason}, label=_label(card)
        )
    return card


def summary() -> dict:
    """Compteurs de l'écran « Cartes » : cartes actives d'élèves inscrits, élèves sans carte,
    cartes perdues depuis le début de l'année."""
    year = organisation.current_year()
    counts = (
        current_enrollments()
        .annotate(carded=has_active_card("student", "student"))
        .aggregate(total=Count("pk"), with_card=Count("pk", filter=Q(carded=True)))
    )
    lost = IdCard.objects.filter(revoke_reason=IdCard.RevokeReason.LOST)
    if year is not None:
        lost = lost.filter(revoked_at__date__gte=year.starts_on)
    return {
        "students": counts["total"],
        "active": counts["with_card"],
        "missing": counts["total"] - counts["with_card"],
        "lost_this_year": lost.count(),
    }


# Choix des personnes

CLASS_ORDER = (
    "class_group__level__order",
    "class_group__level__name",
    "class_group__track__name",
    "class_group__section",
    "student__last_name",
    "student__first_name",
)


def students_list() -> QuerySet[Enrollment]:
    """Élèves inscrits, rangés par classe puis par nom, avec ce que montre leur carte."""
    return (
        current_enrollments()
        .select_related("student", "class_group__level", "class_group__track")
        .order_by(*CLASS_ORDER)
    )


def staff_list() -> QuerySet[Membership]:
    return (
        staff()
        .select_related("user")
        .prefetch_related("roles")
        .order_by("user__last_name", "user__middle_name", "user__first_name")
    )


@dataclass
class Selection:
    enrollments: list[Enrollment]
    members: list[Membership]
    remaining: int = 0


def select(
    *, students=(), members=(), class_group=None, missing_only=False, missing=None
) -> Selection:
    """Qui reçoit une carte : une sélection (A.5), une classe (`missing_only` : sans carte
    seulement) ou les `MAX_PER_PRINT` premiers sans carte (`missing` : `students` ou `staff`).
    Un élève non inscrit cette année ou un compte d'une autre école : refusé."""
    if missing == "students":
        pending = students_list().filter(~has_active_card("student", "student"))
        found = list(pending[: MAX_PER_PRINT + 1])
        rest = pending.count() - MAX_PER_PRINT if len(found) > MAX_PER_PRINT else 0
        return Selection(found[:MAX_PER_PRINT], [], rest)
    if missing == "staff":
        pending = staff_list().filter(~has_active_card("member"))
        found = list(pending[: MAX_PER_PRINT + 1])
        rest = pending.count() - MAX_PER_PRINT if len(found) > MAX_PER_PRINT else 0
        return Selection([], found[:MAX_PER_PRINT], rest)
    if class_group is not None:
        chosen = students_list().filter(class_group=class_group)
        if missing_only:
            chosen = chosen.filter(~has_active_card("student", "student"))
        return Selection(list(chosen[:MAX_PER_PRINT]), [])
    enrollments = list(students_list().filter(student_id__in=students)) if students else []
    people = list(staff_list().filter(pk__in=members)) if members else []
    if len(enrollments) != len(set(students)):
        raise ValidationError({"students": _("Only students enrolled this year get a card.")})
    if len(people) != len(set(members)):
        raise ValidationError({"members": _("Unknown staff member.")})
    return Selection(enrollments, people)


# Impression


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper()


def _face(item: Issued, enrollment: Enrollment | None, year: AcademicYear) -> dict:
    card = item.card
    if card.student_id:
        student = card.student
        name = student.full_name
        line = enrollment.class_group.name if enrollment else ""
        number = student.matricule
        kind = _("Student card")
        photo = photo_uri(student) if student.photo_consent else ""
    else:
        user = card.member.user
        name = user.get_full_name()
        roles = sorted(role.name for role in card.member.roles.all())
        line = roles[0] if roles else ""
        number, kind, photo = "", _("Staff card"), ""
    return {
        "name": name,
        "initials": _initials(name),
        "line": line,
        "number": number,
        "kind": f"{kind} · {year.name}",
        "photo": photo,
        "qr": qr_code(TOKEN_PREFIX + item.token),
        "last4": card.last4,
        "valid_until": card.valid_until,
    }


def _pages(faces: list[dict], layout: str) -> list[tuple[str, list]]:
    """Pages du PDF : `card` = recto puis verso de chaque carte (imprimante à cartes) ; `sheet` =
    planches A4 de 10, rectos puis versos dont les colonnes sont inversées (impression recto
    verso, retournée sur le grand côté : chaque verso tombe derrière son recto)."""
    if layout == CARD:
        return [page for face in faces for page in (("front", [face]), ("back", [face]))]
    pages = []
    for start in range(0, len(faces), PER_SHEET):
        chunk = faces[start : start + PER_SHEET]
        padded = chunk + [None] * (-len(chunk) % 2)
        backs = [face for i in range(0, len(padded), 2) for face in (padded[i + 1], padded[i])]
        pages += [("front", chunk), ("back", backs)]
    return pages


def document(issued: list[Issued], enrollments: dict, layout: str) -> tuple[str, list[str]]:
    """Début du HTML (styles) et corps de chaque page, pour `printing.prepare_at`."""
    school = require_current_school()
    year = organisation.current_year()
    settings = school.card
    color = settings["color"] or school.primary_color
    header = school_header(school)
    city = f", {school.city}" if school.city else ""
    back_text = settings["back_text"] or _(
        "This card is personal. If you find it, please return it to %(school)s%(city)s."
    ) % {"school": header["school_name"], "city": city}
    shared = {
        **header,
        "layout": layout,
        "color": color,
        "text_color": colors.text_color(color) or colors.WHITE,
        "back_text": back_text,
    }
    faces = [_face(item, enrollments.get(item.card.student_id), year) for item in issued]
    head = render_to_string("attendance/cards.html", shared)
    bodies = [
        render_to_string("attendance/_card_page.html", {**shared, "side": side, "faces": chunk})
        for side, chunk in _pages(faces, layout)
    ]
    return head, bodies


# Liste de l'appareil de pointage


def roster_version() -> str:
    """Change dès qu'une carte, une inscription de l'année, un élève ou un membre du personnel
    change : l'appareil ne recharge la liste que dans ce cas (trois requêtes d'agrégats)."""
    cards = IdCard.objects.aggregate(last=Max("updated_at"), count=Count("pk"))
    pupils = current_enrollments().aggregate(
        last=Max("updated_at"), student=Max("student__updated_at"), count=Count("pk")
    )
    people = staff().aggregate(last=Max("updated_at"), user=Max("user__updated_at"))
    raw = "|".join(str(value) for part in (cards, pupils, people) for value in part.values())
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def roster_students(after=None) -> list[Enrollment]:
    """Élèves inscrits par pages de `ROSTER_PAGE` (dans l'ordre des identifiants), avec leur
    carte active : `card_hash`, `card_last4` (vides sans carte)."""
    items = current_enrollments().select_related(
        "student", "class_group__level", "class_group__track"
    )
    if after is not None:
        items = items.filter(student_id__gt=after)
    items = list(items.order_by("student_id")[: ROSTER_PAGE + 1])
    cards = {
        card.student_id: card
        for card in active().filter(student_id__in=[item.student_id for item in items])
    }
    for item in items:
        card = cards.get(item.student_id)
        item.card_hash = card.token_hash if card else ""
        item.card_last4 = card.last4 if card else ""
    return items


def roster_staff() -> list[Membership]:
    members = list(staff().select_related("user").order_by("pk"))
    cards = {card.member_id: card for card in active().filter(member__in=members)}
    for member in members:
        card = cards.get(member.pk)
        member.card_hash = card.token_hash if card else ""
        member.card_last4 = card.last4 if card else ""
    return members
