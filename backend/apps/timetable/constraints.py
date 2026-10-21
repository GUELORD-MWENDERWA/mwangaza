"""Règles de l'emploi du temps (EDT.1c, spec emploi du temps § 5) : la liste fermée des kinds, le
schéma des paramètres de chacun, leur enregistrement (journal compris) et ce qu'il faut pour les
écrire (cours, enseignants).

Une règle nomme ses cours, enseignants et salles par identifiant : à l'enregistrement, chacun doit
être de l'école (gestionnaire scopé : jamais celui d'une autre) et, pour un cours, enseigné dans
l'année en cours. Ce que l'école règle déjà ailleurs ne devient pas une seconde règle : heures du
même cours par jour, heures par jour et par semaine d'un enseignant, journée sans trou (règles
générales de la grille, cours, disponibilités) ; la stabilité viendra avec le calcul (EDT.3).
"""

from dataclasses import dataclass
from datetime import time
from uuid import UUID

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.academics.courses import active_staff
from apps.academics.models import CATEGORIES, Course
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.schools import organisation
from apps.schools.models import School
from apps.timetable import placement
from apps.timetable.models import MAX_LESSONS_PER_DAY, Room, TimetableRule

Kind = TimetableRule.Kind
HARD, SOFT = TimetableRule.Strength.HARD, TimetableRule.Strength.SOFT
# Cours visés : tous, une catégorie (cours principaux…), tous ceux d'un nom, le cours d'une classe.
ALL, CATEGORY, NAME, COURSE = "all", "category", "name", "course"
MORNING, AFTERNOON = "morning", "afternoon"
# Le matin : une heure qui commence avant midi, quelle que soit la grille (deux vacations).
MIDDAY = time(12, 0)
RULES_LIMIT = 500
GROUP_MAX = 6
GROUPS = (Kind.PARALLEL_COURSES, Kind.JOINT_COURSES)

TOO_MANY_RULES = ApiError("too_many_rules", _("The school already has 500 timetable rules."), 409)
COURSE_GROUPED = ApiError(
    "course_grouped",
    _("One of these courses is already in another group (parallel groups or joint course)."),
    409,
)


def _day(**extra) -> serializers.IntegerField:
    return serializers.IntegerField(
        min_value=1, max_value=7, **{"help_text": "1 = lundi.", **extra}
    )


def _lesson(**extra) -> serializers.IntegerField:
    return serializers.IntegerField(min_value=1, max_value=MAX_LESSONS_PER_DAY, **extra)


class UnavailableSerializer(serializers.Serializer):
    """Une absence : un jour entier, ou une plage horaire de ce jour (début et fin)."""

    weekday = _day()
    start = serializers.TimeField(required=False, format="%H:%M")
    end = serializers.TimeField(required=False, format="%H:%M")

    def validate(self, attrs: dict) -> dict:
        start, end = attrs.get("start"), attrs.get("end")
        if (start is None) != (end is None):
            raise serializers.ValidationError(
                _("Give both the start and the end, or neither for the whole day."),
                code="incomplete_range",
            )
        if start is not None and start >= end:
            raise serializers.ValidationError(_("The end comes after the start."), code="bad_range")
        row = {"weekday": attrs["weekday"]}
        if start is not None:
            row |= {"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")}
        return row


class TargetSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=[ALL, CATEGORY, NAME, COURSE])
    value = serializers.CharField(max_length=100, allow_blank=True, default="")

    def validate(self, attrs: dict) -> dict:
        scope, value = attrs["scope"], attrs["value"].strip()
        if scope == ALL:
            value = ""
        elif scope == CATEGORY and value not in CATEGORIES:
            raise serializers.ValidationError(
                {"value": _("Unknown course category.")}, code="unknown_category"
            )
        elif scope == NAME and not value:
            raise serializers.ValidationError(
                {"value": _("Give the name of the course.")}, code="course_name_missing"
            )
        elif scope == COURSE:
            try:
                value = str(UUID(value))
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"value": _("Choose a course.")}, code="choose_course"
                ) from exc
        return {"scope": scope, "value": value}


def _some_courses(attrs: dict) -> None:
    if attrs["target"]["scope"] == ALL:
        raise serializers.ValidationError(
            {"target": _("Choose the courses concerned.")}, code="choose_courses"
        )


class FixedLessonParams(serializers.Serializer):
    """Heures verrouillées : le cours, le jour, de la `first`e à la `last`e heure, salle
    facultative (vide : celle qu'exige le cours, sinon celle de la classe)."""

    course = serializers.UUIDField()
    weekday = _day()
    first = _lesson()
    last = _lesson()
    room = serializers.UUIDField(allow_null=True, default=None)

    def validate(self, attrs: dict) -> dict:
        if attrs["last"] < attrs["first"]:
            raise serializers.ValidationError(
                {"last": _("The last lesson cannot come before the first.")},
                code="last_before_first",
            )
        return attrs


class CourseNotSlotParams(serializers.Serializer):
    """Pas de ces cours : un jour (vide : tous), à ces heures (numéros) et/ou en dernière heure ;
    un jour sans heure = toute la journée."""

    target = TargetSerializer()
    weekday = _day(allow_null=True, default=None)
    lessons = serializers.ListField(child=_lesson(), max_length=MAX_LESSONS_PER_DAY, default=list)
    last = serializers.BooleanField(default=False)

    def validate(self, attrs: dict) -> dict:
        _some_courses(attrs)
        if attrs["weekday"] is None and not attrs["lessons"] and not attrs["last"]:
            raise serializers.ValidationError(
                {"lessons": _("Choose a day, some lessons, or the last lesson.")},
                code="choose_when",
            )
        return {**attrs, "lessons": sorted(set(attrs["lessons"]))}


class PartOfDayParams(serializers.Serializer):
    target = TargetSerializer()
    part = serializers.ChoiceField(choices=[MORNING, AFTERNOON])
    weekday = _day(allow_null=True, default=None)

    def validate(self, attrs: dict) -> dict:
        _some_courses(attrs)
        return attrs


class GroupParams(serializers.Serializer):
    """Groupes en parallèle (cours d'une même classe) ou cours commun (classes différentes, même
    enseignant)."""

    courses = serializers.ListField(
        child=serializers.UUIDField(), min_length=2, max_length=GROUP_MAX
    )

    def validate(self, attrs: dict) -> dict:
        if len(set(attrs["courses"])) != len(attrs["courses"]):
            raise serializers.ValidationError(
                {"courses": _("A course is chosen twice.")}, code="course_twice"
            )
        return attrs


class RoomUnavailableParams(UnavailableSerializer):
    room = serializers.UUIDField()

    def validate(self, attrs: dict) -> dict:
        return {"room": attrs["room"], **super().validate(attrs)}


class SpreadParams(serializers.Serializer):
    target = TargetSerializer()
    no_consecutive_days = serializers.BooleanField(default=True)


class TeacherCompactParams(serializers.Serializer):
    teacher = serializers.UUIDField(allow_null=True, default=None, help_text="Vide : tous.")


class TeacherFreeDayParams(serializers.Serializer):
    teacher = serializers.UUIDField()
    weekday = _day(allow_null=True, default=None, help_text="Vide : un jour, peu importe lequel.")


@dataclass(frozen=True)
class Spec:
    params: type[serializers.Serializer]
    # Forces permises, celle par défaut d'abord.
    strengths: tuple[str, ...]
    weight: int = 5


SPECS: dict[str, Spec] = {
    Kind.FIXED_LESSON: Spec(FixedLessonParams, (HARD,)),
    Kind.COURSE_NOT_SLOT: Spec(CourseNotSlotParams, (SOFT, HARD)),
    Kind.COURSE_PART_OF_DAY: Spec(PartOfDayParams, (SOFT, HARD), 3),
    Kind.PARALLEL_COURSES: Spec(GroupParams, (HARD,)),
    Kind.JOINT_COURSES: Spec(GroupParams, (HARD,)),
    Kind.ROOM_UNAVAILABLE: Spec(RoomUnavailableParams, (HARD, SOFT)),
    Kind.SPREAD_OVER_WEEK: Spec(SpreadParams, (SOFT, HARD)),
    Kind.TEACHER_COMPACT: Spec(TeacherCompactParams, (SOFT,), 2),
    Kind.TEACHER_FREE_DAY: Spec(TeacherFreeDayParams, (SOFT, HARD)),
}


def matches(target: dict, course: Course) -> bool:
    """Le cours est-il visé (tous, sa catégorie, son nom sans tenir compte de la casse, lui) ?"""
    scope, value = target["scope"], target["value"]
    if scope == CATEGORY:
        return course.category == value
    if scope == NAME:
        return course.name.casefold() == value.casefold()
    if scope == COURSE:
        return str(course.pk) == value
    return True


def _json(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    return value


def _refused(field: str, message, code: str) -> serializers.ValidationError:
    return serializers.ValidationError({"params": {field: [message]}}, code=code)


def _taught(ids: list[str], field: str) -> list[Course]:
    """Les cours de l'école enseignés cette année, dans l'ordre donné ; sinon refus."""
    year = organisation.current_year()
    found = {
        str(course.pk): course
        for course in Course.objects.filter(
            pk__in=ids, class_group__academic_year=year, is_taught=True
        )
    }
    if year is None or len(found) != len(ids):
        raise _refused(field, _("This course is not taught this year."), "not_taught")
    return [found[pk] for pk in ids]


def _room_in_use(pk: str, field: str) -> None:
    if not Room.objects.filter(pk=pk, is_active=True).exists():
        raise _refused(
            field, _("This room does not exist or is no longer in use."), "room_not_in_use"
        )


def _on_staff(pk: str) -> None:
    if not active_staff().filter(pk=pk).exists():
        raise _refused("teacher", _("This person is not on the school's staff."), "not_on_staff")


def _check_objects(kind: str, params: dict) -> None:
    """Chaque cours, salle ou enseignant nommé est de l'école ; les groupes tiennent debout."""
    target = params.get("target")
    if target and target["scope"] == COURSE:
        _taught([target["value"]], "target")
    if kind == Kind.FIXED_LESSON:
        _taught([params["course"]], "course")
        if params["room"]:
            _room_in_use(params["room"], "room")
    elif kind in GROUPS:
        courses = _taught(params["courses"], "courses")
        classes = {course.class_group_id for course in courses}
        if kind == Kind.PARALLEL_COURSES and len(classes) != 1:
            raise _refused(
                "courses", _("Parallel groups are courses of the same class."), "parallel_one_class"
            )
        if kind == Kind.JOINT_COURSES:
            if len(classes) != len(courses):
                raise _refused(
                    "courses",
                    _("A joint course brings together different classes."),
                    "joint_classes",
                )
            teachers = {course.teacher_id for course in courses}
            if len(teachers) != 1 or None in teachers:
                raise _refused(
                    "courses",
                    _("The courses of a joint course need the same teacher."),
                    "joint_teacher",
                )
    elif kind == Kind.ROOM_UNAVAILABLE:
        _room_in_use(params["room"], "room")
    elif kind in (Kind.TEACHER_COMPACT, Kind.TEACHER_FREE_DAY) and params["teacher"]:
        _on_staff(params["teacher"])


def clean(data: dict) -> dict:
    """La règle reçue, vérifiée par le schéma de son kind et rendue en JSON : force et poids par
    défaut du kind, force refusée si le kind ne la permet pas."""
    spec = SPECS[data["kind"]]
    params = spec.params(data=data.get("params") or {})
    if not params.is_valid():
        raise serializers.ValidationError({"params": params.errors})
    values = _json(dict(params.validated_data))
    strength = data.get("strength") or spec.strengths[0]
    if strength not in spec.strengths:
        if spec.strengths == (HARD,):
            message, code = _("This rule is always required."), "always_required"
        else:
            message, code = _("This rule can only be a wish."), "only_wish"
        raise serializers.ValidationError({"strength": [message]}, code=code)
    _check_objects(data["kind"], values)
    return {
        "kind": data["kind"],
        "params": values,
        "strength": strength,
        "weight": data.get("weight") or spec.weight,
        "active": data.get("active", True),
    }


# --------------------------------------------------------------------------- enregistrement


def rules() -> list[TimetableRule]:
    """Les règles de l'école (au plus 500 : pas de pagination), actives d'abord."""
    return list(TimetableRule.objects.all())


def _row(rule: TimetableRule) -> dict:
    return {
        "kind": rule.kind,
        "params": rule.params,
        "strength": rule.strength,
        "weight": rule.weight,
        "active": rule.active,
    }


def _lock_school() -> None:
    """Une écriture de règle à la fois par école : plafond et groupes disjoints exacts."""
    School.objects.select_for_update().only("pk").get(pk=require_current_school().pk)


def _check_groups(fields: dict, exclude: TimetableRule | None = None) -> None:
    """Un cours n'est que dans un groupe actif (parallèles ou cours commun) : les contrôles et le
    calcul comptent ses heures une fois."""
    if fields["kind"] not in GROUPS or not fields["active"]:
        return
    mine = set(fields["params"]["courses"])
    others = TimetableRule.objects.filter(kind__in=GROUPS, active=True)
    if exclude is not None:
        others = others.exclude(pk=exclude.pk)
    if any(mine & set(other.params.get("courses", [])) for other in others):
        raise BusinessError(COURSE_GROUPED)


def create_rule(*, actor, **fields) -> TimetableRule:
    with transaction.atomic():
        _lock_school()
        if TimetableRule.objects.count() >= RULES_LIMIT:
            raise BusinessError(TOO_MANY_RULES)
        _check_groups(fields)
        rule = TimetableRule.objects.create(created_by=actor, **fields)
        audit.record(Action.TIMETABLE_RULE_CHANGED, rule, actor=actor, after=_row(rule))
    return rule


def update_rule(rule: TimetableRule, *, actor, **fields) -> TimetableRule:
    """Toute la règle (kind compris) ; seulement ce qui change va dans le journal."""
    with transaction.atomic():
        _lock_school()
        _check_groups(fields, exclude=rule)
        before = _row(rule)
        for key, value in fields.items():
            setattr(rule, key, value)
        old, new = audit.changes(before, _row(rule))
        if new:
            rule.save()
            audit.record(Action.TIMETABLE_RULE_CHANGED, rule, actor=actor, before=old, after=new)
    return rule


def delete_rule(rule: TimetableRule, *, actor) -> None:
    with transaction.atomic():
        audit.record(Action.TIMETABLE_RULE_DELETED, rule, actor=actor, before=_row(rule))
        rule.delete()


def choices() -> dict:
    """Ce que l'éditeur des règles propose : chaque kind (forces permises, poids par défaut), les
    cours enseignés cette année (classe, enseignant, heures, séances) et leurs enseignants.
    Deux requêtes."""
    year = organisation.current_year()
    courses = (
        list(
            Course.objects.filter(class_group__academic_year=year, is_taught=True)
            .select_related("class_group__level", "class_group__track", "teacher")
            .order_by(
                "class_group__level__order",
                "class_group__track__name",
                "class_group__section",
                "order",
            )
        )
        if year
        else []
    )
    teacher_ids = {course.teacher_id for course in courses if course.teacher_id}
    teachers = sorted(active_staff().filter(pk__in=teacher_ids), key=str)
    return {
        "kinds": [
            {
                "kind": kind,
                "strengths": list(spec.strengths),
                "strength": spec.strengths[0],
                "weight": spec.weight,
            }
            for kind, spec in SPECS.items()
        ],
        "courses": [
            {
                "id": course.pk,
                "name": course.name,
                "category": course.category,
                "class_group": course.class_group_id,
                "class_name": course.class_group.name,
                "teacher": course.teacher_id,
                "weekly_hours": course.weekly_hours or 0,
                "sessions": placement.sessions(course) if course.weekly_hours else [],
            }
            for course in courses
        ],
        "teachers": [{"id": teacher.pk, "name": str(teacher)} for teacher in teachers],
    }
