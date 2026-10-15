"""Élèves, familles et inscriptions de l'école courante (D2-D4).

Droit `students.edit`, vérifié par l'API. Chaque changement va dans le journal de l'école
(domaine `students`), dans la transaction de l'action. Élèves et inscriptions acceptent un
identifiant donné par l'appareil (UUID v7) : le même envoi rejoué ne crée rien de plus.
"""

import secrets
from datetime import date, timedelta
from functools import partial
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.errors import ApiError, BusinessError
from apps.core.ids import uuid7
from apps.core.tenancy import require_current_school, use_all_schools
from apps.finance import services as finance
from apps.schools import matricule
from apps.schools.models import AcademicYear, ClassGroup, School
from apps.students.models import (
    FAMILY_CODE_ALPHABET,
    FAMILY_CODE_LENGTH,
    Enrollment,
    Family,
    Guardian,
    MatriculeSequence,
    Student,
)
from apps.students.photos import photo_kind

POSSIBLE_DUPLICATE = ApiError(
    "possible_duplicate",
    _("A student with the same names and date of birth already exists: confirm to create it."),
    409,
)
ALREADY_ENROLLED = ApiError(
    "already_enrolled", _("This student is already enrolled this school year."), 409
)
CLASS_OTHER_YEAR = ApiError(
    "class_other_year", _("The new class must be in the same school year."), 409
)
MATRICULE_TAKEN = ApiError(
    "matricule_taken", _("Another student already has this student number."), 409
)
# Un identifiant donné par l'appareil qui sert déjà ailleurs (jamais dit où).
ID_TAKEN = ApiError("id_taken", _("This identifier is already used."), 409)
MAX_GUARDIANS = 10
_STUDENT_FIELDS = (
    "last_name",
    "middle_name",
    "first_name",
    "sex",
    "birth_date",
    "birth_place",
    "national_id",
    "permanent_number",
    "nationality",
    "origin_province",
    "origin_territory",
    "address",
    "photo_consent",
    "previous_school",
)


def _json(value):
    return value.isoformat() if isinstance(value, date) else value


# Familles


def new_family_code() -> str:
    """8 caractères au hasard, sans caractère ambigu, unique sur toute la plateforme."""
    while True:
        code = "".join(secrets.choice(FAMILY_CODE_ALPHABET) for _ in range(FAMILY_CODE_LENGTH))
        with use_all_schools():
            taken = Family.all_schools.filter(code=code).exists()
        if not taken:
            return code


def _guardians_data(family: Family) -> list[dict]:
    return [
        {
            "full_name": g.full_name,
            "relationship": g.relationship,
            "phone": g.phone,
            "email": g.email,
            "is_primary": g.is_primary,
            "is_emergency_contact": g.is_emergency_contact,
        }
        for g in family.guardians.all()
    ]


def _write_guardians(family: Family, guardians: list[dict], *, actor: User) -> None:
    """Remplace les tuteurs de la famille par la liste envoyée (ceux qui ont un `id` sont
    modifiés, les autres créés, les absents retirés). Un seul contact principal : le premier
    de la liste si aucun n'est choisi."""
    if len(guardians) > MAX_GUARDIANS:
        raise ValidationError({"guardians": _("At most 10 guardians.")}, code="too_many")
    if sum(bool(g.get("is_primary")) for g in guardians) > 1:
        raise ValidationError({"guardians": _("Only one main contact.")}, code="several_primary")
    chosen = any(g.get("is_primary") for g in guardians)
    existing = {g.pk: g for g in family.guardians.all()}
    kept = []
    for index, data in enumerate(guardians):
        data = dict(data)
        guardian_id = data.pop("id", None)
        guardian = existing.get(guardian_id) if guardian_id else Guardian(family=family)
        if guardian is None:
            raise ValidationError(
                {"guardians": _("Unknown guardian for this family.")}, code="unknown_guardian"
            )
        if guardian._state.adding:
            guardian.created_by = actor
        for name, value in data.items():
            setattr(guardian, name, value.strip() if isinstance(value, str) else value)
        guardian.is_primary = bool(data.get("is_primary")) if chosen else index == 0
        guardian.save()
        kept.append(guardian.pk)
    family.guardians.exclude(pk__in=kept).delete()


def create_family(*, actor: User, guardians: list[dict]) -> Family:
    require_current_school()
    with transaction.atomic():
        family = Family.objects.create(code=new_family_code(), created_by=actor)
        _write_guardians(family, guardians, actor=actor)
        audit.record(
            Action.STUDENTS_FAMILY_CREATED,
            family,
            actor=actor,
            after={"guardians": _guardians_data(family)},
        )
    return family


def update_family(family: Family, *, actor: User, guardians: list[dict]) -> Family:
    with transaction.atomic():
        before = _guardians_data(family)
        _write_guardians(family, guardians, actor=actor)
        after = _guardians_data(family)
        if before != after:
            audit.record(
                Action.STUDENTS_FAMILY_UPDATED,
                family,
                actor=actor,
                before={"guardians": before},
                after={"guardians": after},
            )
    return family


# Le parent qui a perdu son code ou son mot de passe a ce délai pour se servir du nouveau code.
RENEWED_CODE_DAYS = 30


def renew_family_code(family: Family, *, actor: User) -> Family:
    """« Nouveau code » (M10) : l'ancien code ne marche plus ; le nouveau sert une seule fois,
    pendant 30 jours, à activer le portail ou à choisir un nouveau mot de passe (portail)."""
    with transaction.atomic():
        old = family.code
        family.code = new_family_code()
        family.code_expires_at = timezone.now() + timedelta(days=RENEWED_CODE_DAYS)
        family.save(update_fields=["code", "code_expires_at", "updated_at"])
        audit.record(
            Action.STUDENTS_FAMILY_CODE_RENEWED,
            family,
            actor=actor,
            after={"code_expires_at": family.code_expires_at.isoformat()},
            label=old,
        )
    return family


def set_portal_access(family: Family, *, actor: User, suspended: bool) -> Family:
    """« Suspendre l'accès » (M10) : le portail ne montre plus rien de cette famille, sans
    supprimer le compte du parent ; « Rétablir l'accès » le rouvre."""
    if (family.portal_suspended_at is not None) == suspended:
        return family
    with transaction.atomic():
        family.portal_suspended_at = timezone.now() if suspended else None
        family.save(update_fields=["portal_suspended_at", "updated_at"])
        action = Action.STUDENTS_PORTAL_SUSPENDED if suspended else Action.STUDENTS_PORTAL_RESTORED
        audit.record(action, family, actor=actor, label=family.code)
    return family


# Élèves


def _student_data(student: Student) -> dict:
    data = {name: _json(getattr(student, name)) for name in _STUDENT_FIELDS}
    data["family"] = student.family.code
    data["matricule"] = student.matricule
    data["photo"] = bool(student.photo)
    return data


def _clean(fields: dict) -> dict:
    return {
        name: value.strip() if isinstance(value, str) else value
        for name, value in fields.items()
        if name in _STUDENT_FIELDS
    }


def possible_duplicates(fields: dict, *, student_id=None):
    """Même nom, même prénom et même date de naissance dans l'école : un avertissement, pas un
    blocage (`docs/04` § 3)."""
    if not fields.get("birth_date"):
        return Student.objects.none()
    return Student.objects.filter(
        last_name__iexact=fields.get("last_name", ""),
        first_name__iexact=fields.get("first_name", ""),
        birth_date=fields["birth_date"],
    ).exclude(pk=student_id)


def create_student(
    *,
    actor: User,
    family: Family | None = None,
    guardians: list[dict] | None = None,
    allow_duplicate: bool = False,
    student_id: UUID | None = None,
    **fields,
) -> tuple[Student, bool]:
    """Élève avec sa famille : une famille existante, ou une nouvelle avec `guardians`.
    Renvoie `(élève, créé)` ; `créé` est faux quand le même envoi est rejoué."""
    require_current_school()
    if student_id is not None:
        replayed = Student.objects.filter(pk=student_id).first()
        if replayed is not None:
            return replayed, False
        with use_all_schools():
            taken = Student.all_schools.filter(pk=student_id).exists()
        if taken:
            raise BusinessError(ID_TAKEN)
    fields = _clean(fields)
    duplicates = [] if allow_duplicate else list(possible_duplicates(fields)[:5])
    if duplicates:
        raise BusinessError(
            POSSIBLE_DUPLICATE,
            duplicates=[
                {
                    "id": str(other.pk),
                    "last_name": other.last_name,
                    "middle_name": other.middle_name,
                    "first_name": other.first_name,
                    "matricule": other.matricule,
                }
                for other in duplicates
            ],
        )
    with transaction.atomic():
        if family is None:
            family = create_family(actor=actor, guardians=guardians or [])
        extra = {"id": student_id} if student_id else {}
        student = Student.objects.create(family=family, created_by=actor, **extra, **fields)
        audit.record(
            Action.STUDENTS_STUDENT_CREATED, student, actor=actor, after=_student_data(student)
        )
    return student, True


def update_student(
    student: Student,
    *,
    actor: User,
    family: Family | None = None,
    matricule: str | None = None,
    **fields,
) -> Student:
    """Identité, famille (liaison D4) ou matricule corrigé à la main. Une famille qui n'a plus
    d'enfant après la liaison est supprimée (saisie en double)."""
    with transaction.atomic():
        before = _student_data(student)
        left_family = None
        for name, value in _clean(fields).items():
            setattr(student, name, value)
        if family is not None and family.pk != student.family_id:
            left_family, student.family = student.family, family
        if matricule is not None and matricule.strip() != student.matricule:
            value = matricule.strip()
            if value and Student.objects.filter(matricule=value).exclude(pk=student.pk).exists():
                raise BusinessError(MATRICULE_TAKEN)
            student.matricule = value
        student.save()
        _record_student_update(student, before, actor=actor)
        if left_family is not None and not left_family.students.exists():
            _delete_family(left_family, actor=actor)
    return student


def set_photo(student: Student, photo, *, actor: User) -> Student:
    """Photo de l'élève (PNG ou JPEG déjà vérifié) ; `photo=None` l'efface. L'ancien fichier est
    supprimé après l'enregistrement. `photo_consent` dit seulement si elle peut servir sur la
    carte et le portail (H3)."""
    with transaction.atomic():
        before = _student_data(student)
        old_photo = student.photo.name
        if photo is None:
            student.photo = ""
        else:
            student.photo.save(photo_name(photo), photo, save=False)
        student.save()
        _record_student_update(student, before, actor=actor)
        _delete_photo_after_commit(old_photo, student)
    return student


def photo_name(photo) -> str:
    kind = "png" if photo_kind(photo) == "png" else "jpg"
    return f"photo-{uuid7().hex[-12:]}.{kind}"


def _record_student_update(student: Student, before: dict, *, actor: User) -> None:
    old, new = audit.changes(before, _student_data(student))
    if new:
        audit.record(Action.STUDENTS_STUDENT_UPDATED, student, actor=actor, before=old, after=new)


def _delete_photo_after_commit(old_name: str, student: Student) -> None:
    if old_name and old_name != student.photo.name:
        transaction.on_commit(partial(student.photo.storage.delete, old_name))


def _delete_family(family: Family, *, actor: User) -> None:
    audit.record(
        Action.STUDENTS_FAMILY_DELETED,
        family,
        actor=actor,
        before={"code": family.code, "guardians": _guardians_data(family)},
        label=family.code,
    )
    family.delete()


# Inscriptions et matricule


def next_matricule_number(year: AcademicYear | None) -> int:
    """Numéro du prochain matricule de l'année (« Prochain matricule », C3)."""
    if year is None:
        return 1
    last = (
        MatriculeSequence.objects.filter(academic_year=year)
        .values_list("last_number", flat=True)
        .first()
    )
    return (last or 0) + 1


def _give_matricule(year: AcademicYear, group: ClassGroup) -> str:
    """Prochain matricule de l'année au format de l'école ; vide si l'école n'en attribue pas
    (C5). L'année est verrouillée pendant la transaction : deux inscriptions simultanées n'ont
    jamais le même numéro. Un numéro déjà pris (matricule saisi à la main ou importé) est sauté."""
    automatic, template = School.objects.values_list("auto_matricule", "matricule_format").get(
        pk=require_current_school().pk
    )
    if not automatic:
        return ""
    AcademicYear.objects.select_for_update().get(pk=year.pk)
    sequence, _created = MatriculeSequence.objects.get_or_create(academic_year=year)
    track_code = group.track.code if group.track_id else ""
    number = sequence.last_number
    while True:
        number += 1
        value = matricule.render(
            template, year=year.starts_on.year, number=number, track_code=track_code
        )
        if not Student.objects.filter(matricule=value).exists():
            break
    sequence.last_number = number
    sequence.save(update_fields=["last_number", "updated_at"])
    return value


def _enrollment_data(enrollment: Enrollment) -> dict:
    return {
        "school_year": enrollment.academic_year.name,
        "class": enrollment.class_group.name,
        "status": enrollment.status,
        "left_on": _json(enrollment.left_on),
    }


def enroll(
    student: Student,
    *,
    actor: User,
    class_group: ClassGroup,
    enrolled_on: date | None = None,
    enrollment_id: UUID | None = None,
) -> tuple[Enrollment, bool]:
    """Inscrit l'élève pour l'année de la classe (D3), avec les frais dus d'après les barèmes. Sa
    première inscription dans l'école lui donne son matricule (si l'école en attribue, C5) ; il
    le garde ensuite. Renvoie `(inscription, créée)`."""
    if enrollment_id is not None:
        replayed = Enrollment.objects.filter(pk=enrollment_id).first()
        if replayed is not None:
            return replayed, False
        with use_all_schools():
            taken = Enrollment.all_schools.filter(pk=enrollment_id).exists()
        if taken:
            raise BusinessError(ID_TAKEN)
    year = class_group.academic_year
    with transaction.atomic():
        if Enrollment.objects.filter(student=student, academic_year=year).exists():
            raise BusinessError(ALREADY_ENROLLED)
        extra = {"id": enrollment_id} if enrollment_id else {}
        enrollment = Enrollment.objects.create(
            student=student,
            academic_year=year,
            class_group=class_group,
            enrolled_on=enrolled_on or timezone.localdate(),
            created_by=actor,
            **extra,
        )
        if not student.matricule and (number := _give_matricule(year, class_group)):
            student.matricule = number
            student.save(update_fields=["matricule", "updated_at"])
        audit.record(
            Action.STUDENTS_ENROLLED,
            enrollment,
            actor=actor,
            after={**_enrollment_data(enrollment), "matricule": student.matricule},
        )
        finance.sync_charges(Enrollment.objects.filter(pk=enrollment.pk), actor=actor)
    return enrollment, True


def update_enrollment(
    enrollment: Enrollment,
    *,
    actor: User,
    class_group: ClassGroup | None = None,
    status: str | None = None,
    left_on: date | None = None,
) -> Enrollment:
    """Changement de classe dans la même année, ou départ (transféré, abandon, exclu…) : la
    date de départ vaut aujourd'hui si elle n'est pas donnée ; retour en « actif » : effacée.
    Les frais dus suivent la nouvelle classe, ou les barèmes du moment au retour ; un départ
    les laisse tels quels (l'élève garde ses dettes)."""
    if class_group is not None and class_group.academic_year_id != enrollment.academic_year_id:
        raise BusinessError(CLASS_OTHER_YEAR)
    with transaction.atomic():
        before = _enrollment_data(enrollment)
        if class_group is not None:
            enrollment.class_group = class_group
        if status is not None:
            enrollment.status = status
        if enrollment.status == Enrollment.Status.ACTIVE:
            enrollment.left_on = None
        elif left_on is not None or enrollment.left_on is None:
            enrollment.left_on = left_on or timezone.localdate()
        enrollment.save()
        old, new = audit.changes(before, _enrollment_data(enrollment))
        if new:
            audit.record(
                Action.STUDENTS_ENROLLMENT_UPDATED, enrollment, actor=actor, before=old, after=new
            )
            finance.sync_charges(Enrollment.objects.filter(pk=enrollment.pk), actor=actor)
    return enrollment
