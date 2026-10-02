"""Invitation des familles au portail (H7) : état du portail de chaque famille, familles activées
par classe, lettres d'invitation (deux par feuille A4) et message prêt à partager. Chaque code
remis (lettre en PDF, message) est noté dans le journal ; l'aperçu ne montre jamais le code."""

from django.conf import settings
from django.db.models import Count, Exists, OuterRef, Prefetch, Q, Subquery
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.accounts.phone import InvalidPhoneError, format_phone, normalize_phone
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import qr_code, school_header
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.schools.models import AcademicYear, ClassGroup
from apps.students.documents import HIDDEN_CODE, _code
from apps.students.models import Enrollment, Family, Guardian, Student

ACTIVATED, SUSPENDED, NO_PHONE, CODE_EXPIRED, PENDING = (
    "activated",
    "suspended",
    "no_phone",
    "code_expired",
    "pending",
)
STATUSES = (PENDING, ACTIVATED, NO_PHONE, CODE_EXPIRED, SUSPENDED)
NOT_INVITABLE = ApiError(
    "not_invitable",
    _(
        "This family cannot be invited: its portal is activated, suspended, without a phone "
        "number or with an expired code."
    ),
    400,
)
NOTHING_TO_INVITE = ApiError(
    "nothing_to_invite", _("Every family of this class has activated its account or cannot."), 400
)
_ACTIVE = Enrollment.Status.ACTIVE
_STUDENT_NAMES = ("last_name", "middle_name", "first_name")
_NAMES = tuple(f"student__{name}" for name in _STUDENT_NAMES)


def primary_phone(family: Family) -> str | None:
    """Numéro du tuteur principal (guardians préchargés), celui que l'activation demande."""
    primary = next((guardian for guardian in family.guardians.all() if guardian.is_primary), None)
    if primary is None or not primary.phone:
        return None
    try:
        return normalize_phone(primary.phone)
    except InvalidPhoneError:
        return None


def portal_status(family: Family) -> str:
    """Suspendu, activé, ou pourquoi l'activation est impossible ; sinon « pas encore activé »."""
    if family.portal_suspended_at is not None:
        return SUSPENDED
    if family.activated_at is not None:
        return ACTIVATED
    if primary_phone(family) is None:
        return NO_PHONE
    if family.code_expires_at is not None and family.code_expires_at <= timezone.now():
        return CODE_EXPIRED
    return PENDING


def _invitable() -> Q:
    """Même règle que `portal_status(...) == PENDING`, en SQL."""
    phone = Guardian.objects.filter(family=OuterRef("pk"), is_primary=True).exclude(phone="")
    return (
        Q(portal_suspended_at__isnull=True, activated_at__isnull=True)
        & (Q(code_expires_at__isnull=True) | Q(code_expires_at__gt=timezone.now()))
        & Exists(phone)
    )


def in_class(families, group: ClassGroup):
    """Familles des élèves actifs de la classe, dans l'ordre de la liste de classe."""
    first = Enrollment.objects.filter(
        student__family=OuterRef("pk"), class_group=group, status=_ACTIVE
    ).order_by(*_NAMES)
    return (
        families.filter(Exists(first))
        .annotate(first_child=Subquery(first.values("student__last_name")[:1]))
        .order_by("first_child", "code")
    )


def activation_summary(year: AcademicYear | None) -> dict:
    """Familles et familles activées de l'école, puis de chaque classe de l'année (élèves actifs) ;
    `invitable` : lettres à imprimer. Une famille avec des enfants dans deux classes compte dans
    les deux, une seule fois pour l'école."""
    if year is None:
        return {"families": 0, "activated": 0, "classes": []}
    family = "student__family"
    activated = Q(student__family__activated_at__isnull=False)
    invitable = Exists(Family.objects.filter(_invitable(), pk=OuterRef(family)))
    counts = {
        row["class_group"]: row
        for row in Enrollment.objects.filter(academic_year=year, status=_ACTIVE)
        .values("class_group")
        .annotate(
            families=Count(family, distinct=True),
            activated=Count(family, filter=activated, distinct=True),
            invitable=Count(family, filter=Q(invitable), distinct=True),
        )
    }
    enrolled = Enrollment.objects.filter(
        student__family=OuterRef("pk"), academic_year=year, status=_ACTIVE
    )
    totals = Family.objects.filter(Exists(enrolled)).aggregate(
        families=Count("pk"), activated=Count("pk", filter=Q(activated_at__isnull=False))
    )
    empty = {"families": 0, "activated": 0, "invitable": 0}
    groups = ClassGroup.objects.filter(academic_year=year).select_related("level", "track")
    return {
        **totals,
        "classes": [
            {
                "id": group.pk,
                "name": group.name,
                **{key: counts.get(group.pk, empty)[key] for key in empty},
            }
            for group in groups
        ],
    }


def _letter_families(families):
    year_enrollments = Enrollment.objects.filter(
        academic_year__is_current=True, status=_ACTIVE
    ).select_related("class_group__level", "class_group__track")
    return families.prefetch_related(
        "guardians",
        Prefetch(
            "students",
            queryset=Student.objects.order_by(
                "last_name", "middle_name", "first_name"
            ).prefetch_related(
                Prefetch("enrollments", year_enrollments, to_attr="year_enrollments")
            ),
        ),
    )


def activation_url(code: str = "") -> str:
    """Page d'activation du portail ; le code après « # » est prérempli par le portail et n'est
    jamais envoyé au serveur (ni dans ses journaux)."""
    return f"{settings.PORTAL_URL}/activate" + (f"#{code}" if code else "")


def _letter(family: Family, *, preview: bool) -> dict:
    students = list(family.students.all())
    enrolled = [student for student in students if student.year_enrollments]
    return {
        "children": [
            {
                "name": student.full_name,
                "class": student.year_enrollments[0].class_group.name
                if student.year_enrollments
                else "",
            }
            for student in enrolled or students
        ],
        "phone": format_phone(primary_phone(family)),
        "code": HIDDEN_CODE if preview else _code(family.code),
        "qr": qr_code(activation_url("" if preview else family.code)),
        "expires_at": family.code_expires_at,
    }


def letters(families, *, actor, preview: bool) -> dict:
    """Lettres des familles qui peuvent encore activer leur compte (les autres sont ignorées) ;
    le PDF note chaque famille dans le journal. `NOTHING_TO_INVITE` s'il n'en reste aucune."""
    chosen = [family for family in _letter_families(families) if portal_status(family) == PENDING]
    if not chosen:
        raise BusinessError(NOTHING_TO_INVITE)
    if not preview:
        audit.record_many(
            Action.STUDENTS_FAMILY_INVITATION_PRINTED,
            [(family, {}) for family in chosen],
            actor=actor,
        )
    school = require_current_school()
    return {
        **school_header(school),
        "contact": school.receipt["header"],
        "paper": "a4",
        "portal_url": settings.PORTAL_URL.split("://", 1)[-1],
        "letters": [_letter(family, preview=preview) for family in chosen],
        "printed_by": actor.get_full_name(),
    }


def family_letter(family: Family, *, actor, preview: bool) -> dict:
    """Lettre d'une seule famille (fiche famille) ; refusée si elle ne peut pas être invitée."""
    families = Family.objects.filter(pk=family.pk)
    if portal_status(_letter_families(families).get()) != PENDING:
        raise BusinessError(NOT_INVITABLE)
    return letters(families, actor=actor, preview=preview)


def invitation_message(family: Family, *, actor) -> dict:
    """Message prêt à partager (WhatsApp, SMS) avec le code famille, noté dans le journal."""
    family = _letter_families(Family.objects.filter(pk=family.pk)).get()
    if portal_status(family) != PENDING:
        raise BusinessError(NOT_INVITABLE)
    phone = primary_phone(family)
    lines = [
        gettext(
            "%(school)s: follow your children's payments and the school's announcements on "
            "your phone."
        )
        % {"school": require_current_school().name},
        gettext("1. Open %(url)s") % {"url": activation_url(family.code)},
        gettext("2. Enter your number %(phone)s and the family code %(code)s")
        % {"phone": format_phone(phone), "code": _code(family.code)},
        gettext("3. Choose a password."),
    ]
    if family.code_expires_at:
        lines.append(
            gettext("This code works once, until %(date)s.")
            % {"date": date_format(timezone.localtime(family.code_expires_at), "d/m/Y")}
        )
    lines.append(gettext("Do not give this code to anyone."))
    audit.record(Action.STUDENTS_FAMILY_INVITATION_SHARED, family, actor=actor)
    return {"text": "\n".join(lines), "phone": phone}
