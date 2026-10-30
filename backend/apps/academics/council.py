"""Conseil de délibération d'une classe (NB.5) : ses membres | ceux qui valident les notes
(direction des études : préfet, directeur des études), le titulaire et les enseignants des cours
de la classe —, le secret (eux seuls lisent le tableau avant la proclamation ; seule la direction
des études écrit), les présents, le président et le secrétaire de séance, les observations.

Les membres se calculent (rôles et cours d'aujourd'hui) ; à la proclamation, le conseil est figé
avec les noms dans le `DeliberationSnapshot` : le procès-verbal ne change plus ensuite.
"""

from dataclasses import dataclass, field
from uuid import UUID

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.academics.models import Course, Deliberation
from apps.accounts.models import Membership, User
from apps.accounts.roles import GRADES_VALIDATE
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.schools.models import ClassGroup

NOT_A_MEMBER = ApiError(
    "not_a_member", _("Only the members of the deliberation council see its results."), 403
)
BAD_MEMBER = ApiError("bad_member", _("This person is not a member of the council."), 400)
NOT_PRESENT = ApiError(
    "not_present", _("The chair and the secretary are chosen among those present."), 400
)


@dataclass
class Member:
    user_id: UUID
    name: str
    direction: bool = False
    homeroom: bool = False
    courses: list[str] = field(default_factory=list)


def members(group: ClassGroup) -> list[Member]:
    """Direction des études (droit `grades.validate`), puis le titulaire, puis les enseignants
    des cours de la classe ; comptes actifs dans l'école seulement. Trois requêtes."""
    found: dict[UUID, Member] = {}
    direction = (
        Membership.objects.filter(
            school_id=group.school_id,
            is_active=True,
            user__is_active=True,
            roles__permissions__contains=[GRADES_VALIDATE],
        )
        .select_related("user")
        .distinct()
    )
    for membership in direction:
        user = membership.user
        found[user.pk] = Member(user.pk, user.get_full_name(), direction=True)
    courses = list(
        Course.objects.filter(class_group=group, is_taught=True, teacher__isnull=False)
        .select_related("teacher")
        .order_by("order", "name")
    )
    candidates = {c.teacher_id for c in courses}
    if group.homeroom_teacher_id:
        candidates.add(group.homeroom_teacher_id)
    active = set(
        Membership.objects.filter(
            school_id=group.school_id,
            is_active=True,
            user__is_active=True,
            user_id__in=candidates,
        ).values_list("user_id", flat=True)
    )
    homeroom = group.homeroom_teacher if group.homeroom_teacher_id in active else None
    if homeroom:
        found.setdefault(homeroom.pk, Member(homeroom.pk, homeroom.get_full_name()))
        found[homeroom.pk].homeroom = True
    for course in courses:
        if course.teacher_id in active:
            member = found.setdefault(
                course.teacher_id, Member(course.teacher_id, course.teacher.get_full_name())
            )
            member.courses.append(course.name)

    def order(member: Member) -> tuple:
        return (not member.direction, not member.homeroom, member.name.lower())

    return sorted(found.values(), key=order)


def is_member(user: User, permissions, group: ClassGroup) -> bool:
    """Qui lit le tableau de la classe : la direction des études, le titulaire, un enseignant
    d'un cours de la classe."""
    return (
        GRADES_VALIDATE in permissions
        or group.homeroom_teacher_id == user.pk
        or Course.objects.filter(class_group=group, teacher=user).exists()
    )


def check_member(user: User, permissions, group: ClassGroup) -> None:
    if not is_member(user, permissions, group):
        raise BusinessError(NOT_A_MEMBER)


def _user_id(value) -> str:
    return str(value) if value else ""


def set_council(
    deliberation: Deliberation,
    *,
    present: list[UUID],
    chair: UUID | None,
    secretary: UUID | None,
    remarks: str,
    actor: User,
) -> Deliberation:
    """Présents, président, secrétaire et observations d'une session encore ouverte. Les présents
    sont des membres ; le président et le secrétaire, des présents. Au journal."""
    known = {m.user_id for m in members(deliberation.class_group)}
    present_ids = list(dict.fromkeys(present))
    if any(user_id not in known for user_id in present_ids):
        raise BusinessError(BAD_MEMBER)
    for chosen in (chair, secretary):
        if chosen and chosen not in present_ids:
            raise BusinessError(NOT_PRESENT)
    council = {
        "present": [str(user_id) for user_id in present_ids],
        "chair": _user_id(chair),
        "secretary": _user_id(secretary),
    }
    remarks = remarks.strip()
    with transaction.atomic():
        before = {"council": deliberation.council, "remarks": deliberation.remarks}
        deliberation.council = council
        deliberation.remarks = remarks
        deliberation.save(update_fields=["council", "remarks", "updated_at"])
        audit.record(
            Action.DELIBERATION_COUNCIL,
            deliberation,
            actor=actor,
            before=before if before["council"] or before["remarks"] else None,
            after={"council": council, "remarks": remarks},
            label=deliberation.class_group.name,
        )
    return deliberation


def frozen(deliberation: Deliberation) -> dict:
    """Le conseil tel qu'il est au moment de la proclamation, avec les noms : membres (qualité,
    cours, présence), président, secrétaire, observations."""
    council = deliberation.council or {}
    present = set(council.get("present", []))
    listed = members(deliberation.class_group)
    names = {str(m.user_id): m.name for m in listed}
    return {
        "members": [
            {
                "name": m.name,
                "direction": m.direction,
                "homeroom": m.homeroom,
                "courses": m.courses,
                "present": str(m.user_id) in present,
            }
            for m in listed
        ],
        "chair": names.get(council.get("chair", ""), ""),
        "secretary": names.get(council.get("secretary", ""), ""),
        "remarks": deliberation.remarks,
    }
