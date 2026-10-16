"""Organisation scolaire de l'école courante (C1-C3) : années créées depuis un modèle, découpage
(semestres, périodes, examens), niveaux, options, classes, format du matricule.

Droit `classes.manage`, vérifié par l'API. Chaque changement va dans le journal de l'école
(domaine `organisation`), dans la transaction de l'action. On ne supprime que ce qui ne sert plus :
la base protège ce qui est utilisé (une classe qui a des élèves, un niveau qui a des classes).
"""

from collections.abc import Iterator
from copy import copy
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max, ProtectedError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics import courses
from apps.academics.models import Evaluation
from apps.accounts.models import Membership, User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.finance import services as finance
from apps.schools import matricule
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Term, Track
from apps.sync import changes as sync_changes

YEAR_NAME_TAKEN = ApiError(
    "year_name_taken", _("The school already has a school year with this name."), 409
)
YEAR_IS_CURRENT = ApiError("year_is_current", _("The current school year cannot be deleted."), 409)
YEAR_IN_USE = ApiError("year_in_use", _("This school year has classes: delete them first."), 409)
LEVEL_NAME_TAKEN = ApiError(
    "level_name_taken", _("The school already has a level with this name."), 409
)
LEVEL_IN_USE = ApiError("level_in_use", _("This level is used by classes."), 409)
TRACK_NAME_TAKEN = ApiError(
    "track_name_taken", _("The school already has a track with this name."), 409
)
TRACK_CODE_TAKEN = ApiError(
    "track_code_taken", _("The school already has a track with this code."), 409
)
TRACK_IN_USE = ApiError("track_in_use", _("This track is used by classes."), 409)
CLASS_EXISTS = ApiError("class_exists", _("This class already exists this school year."), 409)
CLASS_IN_USE = ApiError("class_in_use", _("This class has students: it cannot be deleted."), 409)
TERM_IN_USE = ApiError("term_in_use", _("A removed period is already used."), 409)

# Au-delà, c'est une erreur de saisie (un secondaire en a 7, un primaire 9).
MAX_TERMS = 40


def _invalid(path: str, message, code: str, **params) -> ValidationError:
    return ValidationError({path: ValidationError(message, code=code, params=params or None)})


# Années scolaires


class YearTemplate(models.TextChoices):
    """Modèles de découpage (C1). Le primaire attend son modèle officiel (question Q12) : une
    école du primaire part du modèle en trimestres ou d'un découpage vide, et l'ajuste."""

    SECONDARY = "secondary", _("RDC secondary: 2 semesters, 4 periods, 2 exam sessions")
    TRIMESTERS = "trimesters", _("3 terms, 6 periods, 3 exam sessions")
    EMPTY = "empty", _("Empty: enter the terms yourself")


@dataclass
class TermNode:
    """Un élément du découpage envoyé par l'école ; `children` : périodes et examens d'un
    semestre ou d'un trimestre. `id` : élément existant (sinon, nouveau)."""

    kind: str
    name: str = ""
    starts_on: date | None = None
    ends_on: date | None = None
    id: UUID | None = None
    children: list["TermNode"] = field(default_factory=list)


def _group(kind: str) -> TermNode:
    return TermNode(
        kind,
        children=[TermNode(Term.Kind.PERIOD), TermNode(Term.Kind.PERIOD), TermNode(Term.Kind.EXAM)],
    )


def template_terms(template: str) -> list[TermNode]:
    if template == YearTemplate.SECONDARY:
        return [_group(Term.Kind.SEMESTER) for _ in range(2)]
    if template == YearTemplate.TRIMESTERS:
        return [_group(Term.Kind.TRIMESTER) for _ in range(3)]
    return []


def _year_data(year: AcademicYear) -> dict:
    return {"name": year.name, "starts_on": year.starts_on, "ends_on": year.ends_on}


def _check_year(name: str, starts_on: date, ends_on: date, *, year_id=None) -> None:
    if starts_on >= ends_on:
        raise _invalid("ends_on", _("The end must come after the start."), "end_before_start")
    if AcademicYear.objects.filter(name__iexact=name).exclude(pk=year_id).exists():
        raise BusinessError(YEAR_NAME_TAKEN)


def create_year(
    *,
    actor: User,
    starts_on: date,
    ends_on: date,
    name: str = "",
    template: str = YearTemplate.SECONDARY,
    copy_classes_from: AcademicYear | None = None,
    copy_fees: bool = False,
) -> AcademicYear:
    """Nouvelle année scolaire depuis un modèle de découpage (C1), avec, en option, les classes
    d'une autre année (niveau, option, section, capacité, cours ; pas les titulaires ni les
    enseignants, qui changent d'une année à l'autre) et ses barèmes (`copy_fees`, droit vérifié
    par l'API). La première année de l'école devient l'année en cours."""
    require_current_school()
    name = name.strip() or f"{starts_on.year}-{ends_on.year}"
    with transaction.atomic():
        _check_year(name, starts_on, ends_on)
        year = AcademicYear.objects.create(
            name=name,
            starts_on=starts_on,
            ends_on=ends_on,
            is_current=not AcademicYear.objects.exists(),
            created_by=actor,
        )
        _write_terms(year, template_terms(template), actor=actor)
        after = {**_year_data(year), "is_current": year.is_current, "template": template}
        if copy_classes_from is not None:
            after["copied_from"] = copy_classes_from.name
            after["class_count"], after["course_count"] = _copy_classes(
                copy_classes_from, year, actor=actor
            )
        audit.record(Action.ORGANISATION_YEAR_CREATED, year, actor=actor, after=after)
        if copy_fees and copy_classes_from is not None:
            finance.copy_fee_rules(copy_classes_from, year, actor=actor)
    return year


def _copy_classes(source: AcademicYear, year: AcademicYear, *, actor: User) -> tuple[int, int]:
    """Classes copiées, puis leurs cours (8.1) : (nombre de classes, nombre de cours)."""
    old = list(source.class_groups.all())
    groups = [
        ClassGroup(
            academic_year=year,
            level_id=group.level_id,
            track_id=group.track_id,
            section=group.section,
            capacity=group.capacity,
            created_by=actor,
        )
        for group in old
    ]
    created = ClassGroup.objects.bulk_create(groups)
    course_count = courses.copy_year_courses(list(zip(old, created, strict=True)), actor=actor)
    sync_changes.touch_config()
    return len(created), course_count


def update_year(
    year: AcademicYear,
    *,
    actor: User,
    name: str | None = None,
    starts_on: date | None = None,
    ends_on: date | None = None,
) -> AcademicYear:
    """Nom et dates ; les dates du découpage doivent rester dans l'année."""
    name = (name or "").strip() or year.name
    starts_on = starts_on or year.starts_on
    ends_on = ends_on or year.ends_on
    _check_year(name, starts_on, ends_on, year_id=year.pk)
    for term in year.terms.all():
        for value in (term.starts_on, term.ends_on):
            if value is not None and not starts_on <= value <= ends_on:
                raise _invalid(
                    "starts_on" if value < starts_on else "ends_on",
                    _("Some terms and periods would fall outside the year: change them first."),
                    "terms_outside_year",
                )
    with transaction.atomic():
        before = _year_data(year)
        year.name, year.starts_on, year.ends_on = name, starts_on, ends_on
        year.save()
        old, new = audit.changes(before, _year_data(year))
        if new:
            audit.record(Action.ORGANISATION_YEAR_UPDATED, year, actor=actor, before=old, after=new)
    return year


def make_current(year: AcademicYear, *, actor: User) -> AcademicYear:
    """L'année des inscriptions et des écrans par défaut (une seule par école)."""
    if year.is_current:
        return year
    with transaction.atomic():
        AcademicYear.objects.filter(is_current=True).update(is_current=False)
        year.is_current = True
        year.save(update_fields=["is_current", "updated_at"])
        audit.record(
            Action.ORGANISATION_YEAR_UPDATED,
            year,
            actor=actor,
            before={"is_current": False},
            after={"is_current": True},
        )
    return year


def delete_year(year: AcademicYear, *, actor: User) -> None:
    """Une année créée par erreur : ni en cours, ni avec des classes."""
    if year.is_current:
        raise BusinessError(YEAR_IS_CURRENT)
    with transaction.atomic():
        if year.class_groups.exists():
            raise BusinessError(YEAR_IN_USE)
        audit.record(Action.ORGANISATION_YEAR_DELETED, year, actor=actor, before=_year_data(year))
        try:
            year.delete()
        except ProtectedError:
            raise BusinessError(YEAR_IN_USE) from None


def current_year() -> AcademicYear | None:
    return AcademicYear.objects.filter(is_current=True).first()


# Découpage


def _walk(nodes: list[TermNode]) -> Iterator[tuple[str, TermNode, TermNode | None]]:
    """Chaque élément avec son chemin (`terms.0.children.1`) et son parent."""
    for index, node in enumerate(nodes):
        path = f"terms.{index}"
        yield path, node, None
        for child_index, child in enumerate(node.children):
            yield f"{path}.children.{child_index}", child, node


def _check_terms(year: AcademicYear, nodes: list[TermNode]) -> None:
    items = list(_walk(nodes))
    if len(items) > MAX_TERMS:
        raise _invalid("terms", _("Too many terms and periods."), "too_many_terms")
    existing = set(year.terms.values_list("id", flat=True))
    seen: set[UUID] = set()
    errors: dict[str, ValidationError] = {}

    def error(path: str, message, code: str) -> None:
        errors.setdefault(path, ValidationError(message, code=code))

    for path, node, parent in items:
        if node.id is not None:
            if node.id not in existing:
                error(f"{path}.id", _("Unknown term."), "unknown_term")
            elif node.id in seen:
                error(f"{path}.id", _("This term appears twice."), "duplicate_term")
            seen.add(node.id)
        if parent is None and node.children and node.kind not in Term.GROUPS:
            error(f"{path}.kind", _("Only a semester or a term has periods."), "not_a_group")
        if parent is not None and node.kind in Term.GROUPS:
            error(f"{path}.kind", _("Only periods and exams go inside."), "nested_group")
        for bound in ("starts_on", "ends_on"):
            value = getattr(node, bound)
            if value is not None and not year.starts_on <= value <= year.ends_on:
                error(f"{path}.{bound}", _("This date is outside the school year."), "outside_year")
        if node.starts_on and node.ends_on and node.starts_on > node.ends_on:
            error(f"{path}.ends_on", _("The end must come after the start."), "end_before_start")
        if parent is not None:
            if parent.starts_on and node.starts_on and node.starts_on < parent.starts_on:
                error(f"{path}.starts_on", _("Outside its semester or term."), "outside_parent")
            if parent.ends_on and node.ends_on and node.ends_on > parent.ends_on:
                error(f"{path}.ends_on", _("Outside its semester or term."), "outside_parent")
    if errors:
        raise ValidationError(errors)


def terms_snapshot(year: AcademicYear) -> list[dict]:
    """Le découpage tel qu'il est noté au journal : genre, nom, place du parent, dates."""
    terms = list(year.terms.all())
    index = {term.pk: position for position, term in enumerate(terms)}
    return [
        {
            "kind": term.kind,
            "name": term.name,
            "parent": index.get(term.parent_id),
            "starts_on": term.starts_on,
            "ends_on": term.ends_on,
        }
        for term in terms
    ]


def _write_terms(year: AcademicYear, nodes: list[TermNode], *, actor: User) -> None:
    existing = {term.pk: term for term in year.terms.all()}
    # Une période ou des examens déjà notés (8.2.1) gardent leur genre : sinon leurs notes
    # sortiraient du bulletin. Retirés, la base les protège.
    graded = set(
        Evaluation.objects.filter(term__academic_year=year).values_list("term_id", flat=True)
    )
    kept: set[UUID] = set()
    parents: dict[int, Term] = {}
    for order, (_path, node, parent_node) in enumerate(_walk(nodes)):
        term = existing.get(node.id) if node.id is not None else None
        if term is not None and term.pk in graded and term.kind != node.kind:
            raise BusinessError(TERM_IN_USE)
        if term is None:
            term = Term(academic_year=year, created_by=actor)
        term.kind = node.kind
        term.name = node.name.strip()
        term.starts_on = node.starts_on
        term.ends_on = node.ends_on
        term.order = order
        term.parent = parents[id(parent_node)] if parent_node is not None else None
        term.save()
        kept.add(term.pk)
        parents[id(node)] = term
    removed = [term for pk, term in existing.items() if pk not in kept]
    try:
        # Enfants d'abord : un semestre retiré emporte ses périodes.
        for term in sorted(removed, key=lambda term: term.parent_id is None):
            term.delete()
    except ProtectedError:
        raise BusinessError(TERM_IN_USE) from None


def set_terms(year: AcademicYear, nodes: list[TermNode], *, actor: User) -> AcademicYear:
    """Remplace le découpage de l'année (noms, dates, éléments ajoutés ou retirés)."""
    _check_terms(year, nodes)
    with transaction.atomic():
        before = terms_snapshot(year)
        _write_terms(year, nodes, actor=actor)
        after = terms_snapshot(year)
        if after != before:
            audit.record(
                Action.ORGANISATION_TERMS_CHANGED,
                year,
                actor=actor,
                before={"terms": before},
                after={"terms": after},
            )
    return year


# Niveaux


def _level_data(level: Level) -> dict:
    return {
        "name": level.name,
        "report_title": level.report_title,
        "cycle": level.cycle,
        "has_state_exam": level.has_state_exam,
    }


def _check_level_name(name: str, *, level_id=None) -> None:
    if Level.objects.filter(name__iexact=name).exclude(pk=level_id).exists():
        raise BusinessError(LEVEL_NAME_TAKEN)


def create_level(
    *, actor: User, name: str, cycle: str, has_state_exam: bool = False, report_title: str = ""
) -> Level:
    """Nouveau niveau, placé après les autres."""
    require_current_school()
    name = name.strip()
    with transaction.atomic():
        _check_level_name(name)
        last = Level.objects.aggregate(last=Max("order"))["last"]
        level = Level.objects.create(
            name=name,
            report_title=report_title.strip(),
            cycle=cycle,
            has_state_exam=has_state_exam,
            order=0 if last is None else last + 1,
            created_by=actor,
        )
        audit.record(
            Action.ORGANISATION_LEVEL_CREATED, level, actor=actor, after=_level_data(level)
        )
    return level


def update_level(
    level: Level,
    *,
    actor: User,
    name: str | None = None,
    cycle: str | None = None,
    has_state_exam: bool | None = None,
    report_title: str | None = None,
) -> Level:
    name = level.name if name is None else name.strip()
    _check_level_name(name, level_id=level.pk)
    with transaction.atomic():
        before = _level_data(level)
        level.name = name
        level.cycle = cycle or level.cycle
        if report_title is not None:
            level.report_title = report_title.strip()
        if has_state_exam is not None:
            level.has_state_exam = has_state_exam
        level.save()
        old, new = audit.changes(before, _level_data(level))
        if new:
            audit.record(
                Action.ORGANISATION_LEVEL_UPDATED, level, actor=actor, before=old, after=new
            )
    return level


def reorder_levels(level_ids: list[UUID], *, actor: User) -> list[Level]:
    """Nouvel ordre des niveaux : la liste complète des niveaux de l'école."""
    levels = {level.pk: level for level in Level.objects.all()}
    if len(level_ids) != len(set(level_ids)) or set(level_ids) != set(levels):
        raise _invalid("ids", _("Give every level of the school once."), "incomplete_levels")
    before = [level.name for level in sorted(levels.values(), key=lambda lv: lv.order)]
    with transaction.atomic():
        for order, pk in enumerate(level_ids):
            level = levels[pk]
            if level.order != order:
                level.order = order
                level.save(update_fields=["order", "updated_at"])
        after = [levels[pk].name for pk in level_ids]
        if after != before:
            audit.record(
                Action.ORGANISATION_LEVELS_REORDERED,
                actor=actor,
                before={"levels": before},
                after={"levels": after},
            )
    return [levels[pk] for pk in level_ids]


def delete_level(level: Level, *, actor: User) -> None:
    with transaction.atomic():
        audit.record(
            Action.ORGANISATION_LEVEL_DELETED, level, actor=actor, before=_level_data(level)
        )
        try:
            level.delete()
        except ProtectedError:
            raise BusinessError(LEVEL_IN_USE) from None


# Options


def _track_data(track: Track) -> dict:
    return {"name": track.name, "code": track.code}


def _check_track(name: str, code: str, *, track_id=None) -> None:
    others = Track.objects.exclude(pk=track_id)
    if others.filter(name__iexact=name).exists():
        raise BusinessError(TRACK_NAME_TAKEN)
    if others.filter(code=code).exists():
        raise BusinessError(TRACK_CODE_TAKEN)


def create_track(*, actor: User, name: str, code: str) -> Track:
    require_current_school()
    name, code = name.strip(), code.strip().upper()
    with transaction.atomic():
        _check_track(name, code)
        track = Track.objects.create(name=name, code=code, created_by=actor)
        audit.record(
            Action.ORGANISATION_TRACK_CREATED, track, actor=actor, after=_track_data(track)
        )
    return track


def update_track(
    track: Track, *, actor: User, name: str | None = None, code: str | None = None
) -> Track:
    """Un code changé ne touche que les matricules donnés ensuite."""
    name = track.name if name is None else name.strip()
    code = track.code if code is None else code.strip().upper()
    _check_track(name, code, track_id=track.pk)
    with transaction.atomic():
        before = _track_data(track)
        track.name, track.code = name, code
        track.save()
        old, new = audit.changes(before, _track_data(track))
        if new:
            audit.record(
                Action.ORGANISATION_TRACK_UPDATED, track, actor=actor, before=old, after=new
            )
    return track


def delete_track(track: Track, *, actor: User) -> None:
    with transaction.atomic():
        audit.record(
            Action.ORGANISATION_TRACK_DELETED, track, actor=actor, before=_track_data(track)
        )
        try:
            track.delete()
        except ProtectedError:
            raise BusinessError(TRACK_IN_USE) from None


# Classes


def homeroom_candidates():
    """Titulaires possibles : le personnel actif de l'école courante (jamais celui d'une autre)."""
    school = require_current_school()
    return User.objects.filter(
        is_active=True,
        memberships__school=school,
        memberships__is_active=True,
    ).order_by("last_name", "middle_name", "first_name")


def _check_teacher(user: User | None) -> None:
    if user is None:
        return
    school = require_current_school()
    active = Membership.objects.filter(user=user, school=school, is_active=True).exists()
    if not (active and user.is_active):
        raise _invalid("homeroom_teacher", _("Choose a member of the school's staff."), "not_staff")


def _class_data(group: ClassGroup) -> dict:
    teacher = group.homeroom_teacher
    return {
        "level": group.level.name,
        "track": group.track.name if group.track else None,
        "section": group.section,
        "capacity": group.capacity,
        "homeroom_teacher": str(teacher) if teacher else None,
    }


def _check_class_unique(group: ClassGroup) -> None:
    same = ClassGroup.objects.filter(
        academic_year_id=group.academic_year_id,
        level_id=group.level_id,
        track_id=group.track_id,
        section=group.section,
    ).exclude(pk=group.pk)
    if same.exists():
        raise BusinessError(CLASS_EXISTS)


_CLASS_FIELDS = {"level", "track", "section", "capacity", "homeroom_teacher"}


def _apply_class_fields(group: ClassGroup, fields: dict) -> None:
    unknown = fields.keys() - _CLASS_FIELDS
    if unknown:
        raise TypeError(f"Champs de classe inconnus : {sorted(unknown)}")
    for name, value in fields.items():
        if name == "section":
            value = (value or "").strip().upper()
        setattr(group, name, value)
    if "homeroom_teacher" in fields:
        _check_teacher(group.homeroom_teacher)


def create_class_group(*, actor: User, academic_year: AcademicYear, **fields) -> ClassGroup:
    """Nouvelle classe de l'année (C2) : `level`, `track`, `section`, `capacity`,
    `homeroom_teacher`."""
    require_current_school()
    group = ClassGroup(academic_year=academic_year, created_by=actor)
    _apply_class_fields(group, {"section": "", **fields})
    with transaction.atomic():
        _check_class_unique(group)
        group.save()
        audit.record(
            Action.ORGANISATION_CLASS_CREATED, group, actor=actor, after=_class_data(group)
        )
    return group


def update_class_group(group: ClassGroup, *, actor: User, **fields) -> ClassGroup:
    changed = copy(group)  # `group` reste tel quel si le changement est refusé
    _apply_class_fields(changed, fields)
    _check_class_unique(changed)
    with transaction.atomic():
        before = _class_data(group)
        _apply_class_fields(group, fields)
        group.save()
        old, new = audit.changes(before, _class_data(group))
        if new:
            audit.record(
                Action.ORGANISATION_CLASS_UPDATED, group, actor=actor, before=old, after=new
            )
    return group


def delete_class_group(group: ClassGroup, *, actor: User) -> None:
    """Seulement une classe sans élève (C2)."""
    with transaction.atomic():
        audit.record(
            Action.ORGANISATION_CLASS_DELETED, group, actor=actor, before=_class_data(group)
        )
        try:
            group.delete()
        except ProtectedError:
            raise BusinessError(CLASS_IN_USE) from None


# Matricule


def matricule_example(template: str) -> str:
    """« Prochain matricule » (C3) : avec l'année en cours et l'option la première dans l'ordre
    alphabétique, et le prochain numéro de l'année."""
    from apps.students.services import next_matricule_number

    year = current_year()
    track = Track.objects.order_by("name").first()
    return matricule.render(
        template,
        year=year.starts_on.year if year else timezone.localdate().year,
        number=next_matricule_number(year),
        track_code=track.code if track else "",
    )


def set_matricule_format(
    value: str | None = None, *, actor: User, automatic: bool | None = None
) -> School:
    """Nouveau format, ou choix d'attribuer un matricule (`automatic`, C5) : ils valent pour les
    inscriptions et les imports suivants, jamais pour les matricules déjà donnés."""
    school_id = require_current_school().pk
    changes = {}
    if value is not None:
        changes["matricule_format"] = value.strip()
        try:
            matricule.validate_matricule_format(changes["matricule_format"])
        except ValidationError as exc:
            raise ValidationError({"matricule_format": exc}) from None
    if automatic is not None:
        changes["auto_matricule"] = automatic
    with transaction.atomic():
        school = School.objects.select_for_update().get(pk=school_id)
        before = {
            name: getattr(school, name)
            for name, new in changes.items()
            if getattr(school, name) != new
        }
        if before:
            for name in before:
                setattr(school, name, changes[name])
            school.save(update_fields=[*before, "updated_at"])
            audit.record(
                Action.ORGANISATION_MATRICULE_FORMAT_CHANGED,
                school,
                actor=actor,
                before=before,
                after={name: changes[name] for name in before},
            )
    return school
