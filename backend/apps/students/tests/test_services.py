"""Règles des élèves : matricule (format de l'école, séquence par année, gardé toute la
scolarité), code famille, doublon potentiel, inscriptions, classe protégée, journal."""

from datetime import date
from uuid import UUID

import pytest
from django.core.exceptions import ValidationError

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.errors import BusinessError
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.schools import organisation
from apps.students import services
from apps.students.models import FAMILY_CODE_ALPHABET, Enrollment, Student
from apps.students.tests.conftest import GUARDIAN, enrolled, new_student

pytestmark = pytest.mark.django_db


def test_first_enrollment_gives_the_matricule_of_the_school_format(school, head, alpha):
    with use_school(school):
        organisation.set_matricule_format("AL/{OPT}-{AA}-{000}", actor=head)
    first = enrolled(school, head, alpha["group"])
    second = enrolled(school, head, alpha["group"], first_name="Esther", sex="F")

    assert (first.matricule, second.matricule) == ("AL/ELEC-26-001", "AL/ELEC-26-002")

    # 4.13 (C5) : l'école n'en attribue plus ; le numéro suivant n'est pas consommé.
    with use_school(school):
        organisation.set_matricule_format(actor=head, automatic=False)
    without = enrolled(school, head, alpha["group"], first_name="Daniel")
    with use_school(school):
        organisation.set_matricule_format(actor=head, automatic=True)
    third = enrolled(school, head, alpha["group"], first_name="Neema", sex="F")
    assert (without.matricule, third.matricule) == ("", "AL/ELEC-26-003")


def test_the_matricule_is_kept_at_re_enrollment_and_numbers_restart_each_year(school, head, alpha):
    student = enrolled(school, head, alpha["group"])
    with use_school(school):
        next_year = organisation.create_year(
            actor=head, starts_on=date(2027, 9, 1), ends_on=date(2028, 7, 2)
        )
        group = organisation.create_class_group(
            actor=head, academic_year=next_year, level=alpha["other_level"], track=alpha["track"]
        )
        services.enroll(student, actor=head, class_group=group)
        student.refresh_from_db()
    newcomer = enrolled(school, head, group, first_name="Esther", sex="F")

    assert student.matricule == "ALPHA-2026-0001"
    assert newcomer.matricule == "ALPHA-2027-0001"


def test_a_number_already_taken_is_skipped(school, head, alpha):
    """Matricule importé ou corrigé à la main : le suivant ne le reprend pas."""
    imported = new_student(school, head, last_name="Imani")
    with use_school(school):
        services.update_student(imported, actor=head, matricule="ALPHA-2026-0001")

    assert enrolled(school, head, alpha["group"]).matricule == "ALPHA-2026-0002"


def test_each_school_has_its_own_sequence(school, other_school, head, other_head, alpha, beta):
    enrolled(school, head, alpha["group"])
    enrolled(school, head, alpha["group"], first_name="Esther", sex="F")

    assert enrolled(other_school, other_head, beta["group"]).matricule == "BETA-2026-0001"
    with use_school(school):
        example = organisation.matricule_example("ALPHA-{AAAA}-{0000}")
    assert example == "ALPHA-2026-0003"


def test_family_code(school, head):
    student = new_student(school, head)
    code = student.family.code

    assert len(code) == 8 and set(code) <= set(FAMILY_CODE_ALPHABET)


def test_same_names_and_birth_date_warn_but_do_not_block(school, head):
    fields = {"birth_date": date(2012, 3, 14)}
    new_student(school, head, **fields)

    with pytest.raises(BusinessError) as error, use_school(school):
        services.create_student(
            actor=head, guardians=[], last_name="KASEREKA", first_name="jean", sex="M", **fields
        )
    assert error.value.error.code == "possible_duplicate"
    new_student(school, head, allow_duplicate=True, **fields)


def test_the_same_student_sent_twice_is_created_once(school, head):
    student_id = uuid7()
    first = new_student(school, head, student_id=student_id)
    again = new_student(school, head, student_id=student_id)

    assert first.pk == again.pk == UUID(str(student_id))
    with use_school(school):
        assert Student.objects.count() == 1


def test_one_enrollment_per_year_and_class_changes_stay_in_the_year(school, head, alpha):
    student = enrolled(school, head, alpha["group"])
    with use_school(school):
        enrollment = Enrollment.objects.get(student=student)
        with pytest.raises(BusinessError) as error:
            services.enroll(student, actor=head, class_group=alpha["group"])
        assert error.value.error.code == "already_enrolled"

        other_year = organisation.create_year(
            actor=head, starts_on=date(2027, 9, 1), ends_on=date(2028, 7, 2)
        )
        group = organisation.create_class_group(
            actor=head, academic_year=other_year, level=alpha["level"]
        )
        with pytest.raises(BusinessError) as error:
            services.update_enrollment(enrollment, actor=head, class_group=group)
        assert error.value.error.code == "class_other_year"

        services.update_enrollment(enrollment, actor=head, status="dropped")
        assert enrollment.left_on is not None
        services.update_enrollment(enrollment, actor=head, status="active")
        assert enrollment.left_on is None


def test_a_class_with_students_cannot_be_deleted(school, head, alpha):
    enrolled(school, head, alpha["group"])

    with pytest.raises(BusinessError) as error, use_school(school):
        organisation.delete_class_group(alpha["group"], actor=head)
    assert error.value.error.code == "class_in_use"


def test_guardians_are_replaced_with_a_single_main_contact(school, head):
    family = new_student(school, head).family
    with use_school(school):
        mother = family.guardians.get()
        father = {"full_name": "Kasereka Paul", "relationship": "father", "is_primary": True}
        guardians = [{"id": mother.pk, **GUARDIAN}, father]
        services.update_family(family, actor=head, guardians=guardians)
        assert [(g.full_name, g.is_primary) for g in family.guardians.all()] == [
            ("Kasereka Paul", True),
            ("Kahindo Neema", False),
        ]
        with pytest.raises(ValidationError):
            services.update_family(
                family, actor=head, guardians=[{**GUARDIAN, "is_primary": True}, father]
            )


def test_changes_are_in_the_journal(school, head, alpha):
    student = enrolled(school, head, alpha["group"], birth_date=date(2012, 3, 14))
    with use_school(school):
        services.update_student(student, actor=head, first_name="Jean-Paul")
        actions = list(AuditLog.objects.order_by("created_at").values_list("action", flat=True))
        updated = AuditLog.objects.get(action=Action.STUDENTS_STUDENT_UPDATED)

    assert [a for a in actions if a.startswith("students.")] == [
        Action.STUDENTS_FAMILY_CREATED,
        Action.STUDENTS_STUDENT_CREATED,
        Action.STUDENTS_ENROLLED,
        Action.STUDENTS_STUDENT_UPDATED,
    ]
    assert (updated.before, updated.after) == ({"first_name": "Jean"}, {"first_name": "Jean-Paul"})
