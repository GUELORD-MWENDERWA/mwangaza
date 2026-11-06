"""Cartes d'élève et du personnel (6.1) et impression d'une sélection (A.5).

Le QR d'une carte porte `MWZ1:` suivi d'un jeton aléatoire de 128 bits (32 signes hexadécimaux),
jamais le matricule. Le serveur ne garde que l'empreinte SHA-256 du jeton et ses 4 derniers
signes : le jeton n'existe en clair que dans le PDF fait à l'émission (rangé un jour au plus comme
tout document imprimé, `core/printing.py`). Réimprimer = émettre une nouvelle carte, l'ancienne
est révoquée (« remplacée »). L'appareil de pointage reçoit les empreintes (`roster`), hache ce
qu'il lit et décide seul, même sans réseau.
"""

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, Max, OuterRef, Q, QuerySet, Subquery
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, pgettext
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Membership, User
from apps.attendance.models import IdCard
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import data_uri, qr_code, school_header
from apps.core.errors import ApiError, BusinessError
from apps.core.models import PlatformSettings
from apps.core.tenancy import require_current_school
from apps.schools import colors, organisation
from apps.schools.models import AcademicYear, School
from apps.students.documents import _address
from apps.students.models import Enrollment, Guardian, Student
from apps.students.photos import CONTENT_TYPES as PHOTO_TYPES
from apps.students.photos import photo_kind

TOKEN_PREFIX = "MWZ1:"
MAX_PER_PRINT = 100
# Planche A4 : élèves en paysage (2 colonnes, 5 rangées), personnel en portrait (3 sur 3).
GRID = {"land": (2, 10), "port": (3, 9)}
SHEET, CARD = "sheet", "card"
ROSTER_PAGE = 1000

NO_YEAR = ApiError("no_current_year", gettext_lazy("Set the current school year first."), 409)
ALREADY_REVOKED = ApiError(
    "card_already_revoked", gettext_lazy("This card is already revoked."), 409
)
NO_PHOTO = ApiError(
    "card_needs_photo",
    gettext_lazy(
        "No official photo: take it first (Cards, Photo session), or allow cards without "
        "a photo in the card model."
    ),
    409,
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
    faces = {
        **{item.student_id: student_fingerprint(item) for item in enrollments},
        **{member.pk: member_fingerprint(member) for member in members},
    }
    try:
        with transaction.atomic():
            # École verrouillée : deux impressions simultanées n'ont jamais le même N° de carte.
            School.objects.select_for_update().get(pk=school.pk)
            number = IdCard.objects.aggregate(last=Max("number"))["last"] or 0
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
                number += 1
                card = IdCard(
                    number=number,
                    token_hash=fingerprint(token),
                    last4=token[-4:],
                    face_hash=faces[holder.pk],
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
            (
                item.card,
                {
                    "number": item.card.number,
                    "last4": item.card.last4,
                    "valid_until": until.isoformat(),
                },
            )
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
        "to_reprint": len(stale_students()) + len(stale_staff()),
    }


# Carte à réimprimer : ce qu'elle imprime de la personne a changé depuis l'émission.


def _hash(values: tuple) -> str:
    raw = json.dumps(values, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def student_fingerprint(enrollment: Enrollment) -> str:
    """Noms, naissance, sexe, nationalité, N° ID, matricule, photo et classe de l'élève."""
    student = enrollment.student
    return _hash(
        (
            student.last_name,
            student.middle_name,
            student.first_name,
            student.sex,
            student.birth_date,
            student.birth_place,
            student.nationality,
            student.national_id,
            student.matricule,
            student.photo.name,
            enrollment.class_group.name,
        )
    )


def member_fingerprint(member: Membership) -> str:
    """Noms, fonction (ou rôles) et photo du membre du personnel (`roles` préchargés)."""
    user = member.user
    return _hash(
        (
            user.last_name,
            user.middle_name,
            user.first_name,
            _position(member),
            member.photo.name,
        )
    )


def needs_reprint(card: IdCard | None, current: str) -> bool:
    return card is not None and card.face_hash != current


def _with_face(items: QuerySet, field: str, outer: str) -> QuerySet:
    face = active().filter(**{field: OuterRef(outer)}).values("face_hash")[:1]
    return items.annotate(card_face=Subquery(face)).filter(card_face__isnull=False)


def stale_students() -> list[Enrollment]:
    """Élèves dont la carte active n'imprime plus ce qui est vrai aujourd'hui (une requête)."""
    items = _with_face(students_list(), "student", "student")
    return [item for item in items if item.card_face != student_fingerprint(item)]


def stale_staff() -> list[Membership]:
    items = _with_face(staff_list(), "member", "pk")
    return [item for item in items if item.card_face != member_fingerprint(item)]


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
    # Laissées de côté : pas de photo officielle alors que l'école l'exige (`require_photo`).
    without_photo: int = 0


def _batch(pending: QuerySet, photo: str, require_photo: bool) -> tuple[list, int, int]:
    """Les `MAX_PER_PRINT` premiers, le nombre des suivants et, si la photo est exigée, le nombre
    de ceux qui n'en ont pas (jamais choisis : sinon le même lot reviendrait sans fin)."""
    without = 0
    if require_photo:
        without = pending.filter(**{photo: ""}).count()
        pending = pending.exclude(**{photo: ""})
    found = list(pending[: MAX_PER_PRINT + 1])
    rest = pending.count() - MAX_PER_PRINT if len(found) > MAX_PER_PRINT else 0
    return found[:MAX_PER_PRINT], rest, without


def _has_photo(holder) -> bool:
    return bool(holder.student.photo if isinstance(holder, Enrollment) else holder.photo)


def select(
    *,
    students=(),
    members=(),
    class_group=None,
    missing_only=False,
    missing=None,
    require_photo=False,
) -> Selection:
    """Qui reçoit une carte : une sélection (A.5), une classe (`missing_only` : sans carte
    seulement), les `MAX_PER_PRINT` premiers sans carte (`missing` : `students` ou `staff`) ou
    dont la carte est à réimprimer (`reprint`). Un élève non inscrit cette année ou un compte
    d'une autre école : refusé. `require_photo` : personne sans photo officielle laissée de côté."""
    if missing == "students":
        pending = students_list().filter(~has_active_card("student", "student"))
        found, rest, without = _batch(pending, "student__photo", require_photo)
        return Selection(found, [], rest, without)
    if missing == "staff":
        pending = staff_list().filter(~has_active_card("member"))
        found, rest, without = _batch(pending, "photo", require_photo)
        return Selection([], found, rest, without)
    if missing == "reprint":
        people = [*stale_students(), *stale_staff()]
    elif class_group is not None:
        chosen = students_list().filter(class_group=class_group)
        if missing_only:
            chosen = chosen.filter(~has_active_card("student", "student"))
        people = list(chosen[:MAX_PER_PRINT])
    else:
        enrollments = list(students_list().filter(student_id__in=students)) if students else []
        team = list(staff_list().filter(pk__in=members)) if members else []
        if len(enrollments) != len(set(students)):
            raise ValidationError({"students": _("Only students enrolled this year get a card.")})
        if len(team) != len(set(members)):
            raise ValidationError({"members": _("Unknown staff member.")})
        people = [*enrollments, *team]
    kept = [person for person in people if _has_photo(person)] if require_photo else people
    without, rest = len(people) - len(kept), 0
    if missing == "reprint":
        rest, kept = max(len(kept) - MAX_PER_PRINT, 0), kept[:MAX_PER_PRINT]
    return Selection(
        [person for person in kept if isinstance(person, Enrollment)],
        [person for person in kept if isinstance(person, Membership)],
        rest,
        without,
    )


# Impression (maquette `gestion/cartes-modeles.html`, d'après les cartes congolaises fournies)

RELIEF = Path(__file__).resolve().parents[1] / "core/static/core/site/relief.svg"


@cache
def _relief() -> str:
    """Lignes de relief de la marque (blanches, très pâles) posées sur les bandes de couleur."""
    import base64

    return "data:image/svg+xml;base64," + base64.b64encode(RELIEF.read_bytes()).decode()


def _mix(color: str, share: float) -> str:
    """`color` mêlée de blanc (`share` = part de la couleur) : teintes claires de la carte."""
    rgb = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(255 - (255 - part) * share):02X}" for part in rgb)


def _image(field) -> str:
    """Photo (PNG ou JPEG) intégrée au PDF ; vide sans photo lisible."""
    if not field:
        return ""
    try:
        with field.open("rb") as file:
            kind = photo_kind(file)
    except OSError:
        return ""
    return data_uri(field, kind, PHOTO_TYPES)


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper()


def _position(member: Membership) -> str:
    """Fonction en clair (« Enseignante · Mathématiques »), sinon ses rôles (préchargés)."""
    return member.title or " · ".join(sorted(role.name for role in member.roles.all()))


def _born(student: Student) -> tuple[str, str]:
    """(« Né à » / « Née à », « Goma, le 14/03/2010 ») ; vide sans lieu ni date."""
    when = student.birth_date.strftime("%d/%m/%Y") if student.birth_date else ""
    if student.birth_place and when:
        value = _("%(place)s, on %(date)s") % {"place": student.birth_place, "date": when}
    else:
        value = student.birth_place or when
    if not value:
        return "", ""
    female = student.sex == Student.Sex.FEMALE
    label = pgettext("card, female", "Born in") if female else pgettext("card, male", "Born in")
    return label, value


def _student_face(student: Student, enrollment: Enrollment | None, chosen: set, phones) -> dict:
    surnames = " ".join(part for part in (student.last_name, student.middle_name) if part)
    rows = [(_("Names"), f"{surnames.upper()} {student.first_name}".strip())]
    if "birth" in chosen and (born := _born(student))[0]:
        rows.append(born)
    if "sex" in chosen:
        rows.append((_("Sex"), student.sex))
    if "nationality" in chosen and student.nationality:
        rows.append((_("Nationality"), student.nationality))
    if "national_id" in chosen and student.national_id:
        rows.append((_("ID No."), student.national_id))
    rows.append((_("Class"), enrollment.class_group.name if enrollment else ""))
    back = []
    if "guardian_phone" in chosen and (phone := phones.get(student.family_id)):
        back.append((_("Guardian"), phone))
    if "address" in chosen and (address := _address(student)):
        back.append((_("Address"), address))
    return {
        "kind": "student",
        "name": student.full_name,
        "rows": rows,
        "matricule": student.matricule,
        "back_rows": back,
        "photo": _image(student.photo),
    }


def _staff_face(member: Membership) -> dict:
    user = member.user
    return {
        "kind": "staff",
        "name": user.get_full_name(),
        "last_names": " ".join(part for part in (user.last_name, user.middle_name) if part),
        "first_name": user.first_name,
        "position": _position(member),
        "rows": [],
        "back_rows": [],
        "photo": _image(member.photo),
    }


def _face(item: Issued, enrollment: Enrollment | None, chosen: set, phones: dict) -> dict:
    card = item.card
    if card.student_id:
        face = _student_face(card.student, enrollment, chosen, phones)
    else:
        face = _staff_face(card.member)
    return {
        **face,
        "initials": _initials(face["name"]),
        "orientation": "land" if card.student_id else "port",
        "number": f"{card.number:04d}",
        "qr": qr_code(TOKEN_PREFIX + item.token),
        "issued_on": timezone.localdate(card.created_at),
        "valid_until": card.valid_until,
    }


def _pages(faces: list[dict], layout: str) -> list[tuple[str, str, list]]:
    """Pages du PDF (`orientation`, `side`, faces) : `card` = recto puis verso de chaque carte
    (imprimante à cartes) ; `sheet` = planches A4 (10 élèves en paysage ou 9 membres du personnel
    en portrait), rectos puis versos dont chaque rangée est inversée (impression recto verso
    retournée sur le grand côté : chaque verso tombe derrière son recto)."""
    if layout == CARD:
        return [(face["orientation"], side, [face]) for face in faces for side in ("front", "back")]
    pages = []
    for orientation in ("land", "port"):
        group = [face for face in faces if face["orientation"] == orientation]
        columns, per_sheet = GRID[orientation]
        for start in range(0, len(group), per_sheet):
            chunk = group[start : start + per_sheet]
            padded = chunk + [None] * (-len(chunk) % columns)
            backs = [
                face
                for row in range(0, len(padded), columns)
                for face in reversed(padded[row : row + columns])
            ]
            pages += [(orientation, "front", chunk), (orientation, "back", backs)]
    return pages


def _guardian_phones(students: list[Student]) -> dict:
    """Téléphone du responsable principal de chaque famille (une requête)."""
    guardians = Guardian.objects.filter(
        family_id__in={student.family_id for student in students}
    ).exclude(phone="")
    phones = {}
    for guardian in guardians.order_by("-is_primary", "full_name"):
        phones.setdefault(guardian.family_id, str(guardian.phone))
    return phones


def document(issued: list[Issued], enrollments: dict, layout: str) -> tuple[str, list[str]]:
    """Début du HTML (styles) et corps de chaque page, pour `printing.prepare_at`."""
    school = require_current_school()
    year = organisation.current_year()
    settings = school.card
    platform = PlatformSettings.load()
    color = settings["color"] or platform.primary_color
    chosen = set(settings["printed_fields"])
    students = [item.card.student for item in issued if item.card.student_id]
    phones = _guardian_phones(students) if "guardian_phone" in chosen and students else {}
    header = school_header(school)
    authorities = ""
    if "authorities" in chosen:
        authorities = settings["authorities_text"] or _(
            "The civil, military and police authorities are kindly requested to assist the "
            "holder of this card."
        )
    shared = {
        **header,
        "layout": layout,
        "color": color,
        "text_color": colors.text_color(color) or colors.WHITE,
        "tint": _mix(color, 0.09),
        "soft": _mix(color, 0.22),
        "relief": _relief(),
        "platform_name": platform.name,
        "year_name": year.name,
        "city": school.city,
        "host": school.url.split("://", 1)[-1],
        "authorities": authorities,
        "back_text": settings["back_text"],
        "head_title": (header["signer"] or {}).get("title") or _("The head of the school"),
    }
    faces = [_face(item, enrollments.get(item.card.student_id), chosen, phones) for item in issued]
    head = render_to_string("attendance/cards.html", shared)
    bodies = [
        render_to_string(
            "attendance/_card_page.html",
            {**shared, "orientation": orientation, "side": side, "faces": chunk},
        )
        for orientation, side, chunk in _pages(faces, layout)
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
    # Le format du matricule dit à l'appareil s'il vérifie la clé de contrôle (MAT.1).
    template = School.objects.values_list("matricule_format", flat=True).get(
        pk=require_current_school().pk
    )
    raw = "|".join(str(value) for part in (cards, pupils, people) for value in part.values())
    return hashlib.sha256(f"{raw}|{template}".encode()).hexdigest()[:16]


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


def photo_url(holder) -> str | None:
    """Photo officielle pour l'appareil de pointage (droit de pointer suffit) ; l'adresse change
    avec chaque photo (cache de l'appareil)."""
    if isinstance(holder, Student):
        kind, field = "students", holder.photo
    else:
        kind, field = "staff", holder.photo
    if not field:
        return None
    version = field.name.rsplit("/", 1)[-1].split(".")[0].removeprefix("photo-")
    return f"/api/attendance/photos/{kind}/{holder.pk}/?v={version}"


def roster_staff() -> list[Membership]:
    members = list(staff().select_related("user").order_by("pk"))
    cards = {card.member_id: card for card in active().filter(member__in=members)}
    for member in members:
        card = cards.get(member.pk)
        member.card_hash = card.token_hash if card else ""
        member.card_last4 = card.last4 if card else ""
    return members
