"""Organisation scolaire (C1-C3) : règles des services, journal d'audit."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.core.errors import BusinessError
from apps.core.tenancy import CrossSchoolError, use_school
from apps.schools import organisation
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Term, Track
from apps.schools.organisation import TermNode, YearTemplate
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

START, END = date(2026, 9, 1), date(2027, 7, 2)


@pytest.fixture
def in_school(school):
    with use_school(school):
        yield school


def journal(action: str) -> list[AuditLog]:
    return list(AuditLog.objects.filter(action=action).order_by("created_at"))


def new_year(actor, template=YearTemplate.SECONDARY, **fields) -> AcademicYear:
    return organisation.create_year(
        actor=actor, starts_on=START, ends_on=END, template=template, **fields
    )


def error_codes(error: ValidationError) -> dict[str, list[str]]:
    return {field: [e.code for e in errors] for field, errors in error.error_dict.items()}


def kinds(year: AcademicYear) -> list[tuple[str, str | None]]:
    return [(term.kind, term.parent.kind if term.parent else None) for term in year.terms.all()]


# Années (C1)


def test_first_year_from_the_secondary_template(in_school, head):
    year = new_year(head)

    assert year.name == "2026-2027"
    assert year.is_current is True
    assert kinds(year) == [
        ("semester", None),
        ("period", "semester"),
        ("period", "semester"),
        ("exam", "semester"),
        ("semester", None),
        ("period", "semester"),
        ("period", "semester"),
        ("exam", "semester"),
    ]
    assert all(term.name == "" and term.starts_on is None for term in year.terms.all())
    [entry] = journal("organisation.year_created")
    assert entry.actor == head
    assert entry.entity_label == "2026-2027"
    assert entry.after == {
        "name": "2026-2027",
        "starts_on": "2026-09-01",
        "ends_on": "2027-07-02",
        "is_current": True,
        "template": "secondary",
    }


def test_trimesters_and_empty_templates(in_school, head):
    trimesters = new_year(head, YearTemplate.TRIMESTERS)
    empty = organisation.create_year(
        actor=head, starts_on=date(2027, 9, 1), ends_on=date(2028, 7, 1), template="empty"
    )

    assert [kind for kind, parent in kinds(trimesters) if parent is None] == ["trimester"] * 3
    assert len(kinds(trimesters)) == 12
    assert empty.terms.count() == 0
    assert empty.is_current is False


def test_year_name_is_unique_and_dates_must_be_in_order(in_school, head):
    new_year(head, name="Année 1")

    with pytest.raises(BusinessError) as taken:
        new_year(head, name="année 1")
    with pytest.raises(ValidationError) as dates:
        organisation.create_year(actor=head, starts_on=END, ends_on=START)

    assert taken.value.error.code == "year_name_taken"
    assert error_codes(dates.value) == {"ends_on": ["end_before_start"]}
    assert AcademicYear.objects.count() == 1


def test_copy_the_classes_of_another_year_without_their_homeroom_teachers(in_school, head):
    year = new_year(head)
    level = organisation.create_level(actor=head, name="3e", cycle="secondary_technical")
    track = organisation.create_track(actor=head, name="Électricité", code="elec")
    organisation.create_class_group(
        actor=head,
        academic_year=year,
        level=level,
        track=track,
        section="a",
        capacity=45,
        homeroom_teacher=head,
    )

    copy = organisation.create_year(
        actor=head,
        starts_on=date(2027, 9, 1),
        ends_on=date(2028, 7, 1),
        copy_classes_from=year,
    )

    [group] = ClassGroup.objects.filter(academic_year=copy)
    assert (group.name, group.capacity, group.homeroom_teacher) == ("3e Électricité A", 45, None)
    entry = journal("organisation.year_created")[-1]
    assert entry.after["copied_from"] == "2026-2027"
    assert entry.after["class_count"] == 1


def test_change_a_year_keeps_its_terms_inside(in_school, head):
    year = new_year(head)
    first = year.terms.first()
    first.starts_on = date(2026, 9, 7)
    first.save()

    with pytest.raises(ValidationError) as error:
        organisation.update_year(year, actor=head, starts_on=date(2026, 9, 10))
    organisation.update_year(year, actor=head, name=" 2026-27 ", ends_on=date(2027, 7, 9))

    assert error_codes(error.value) == {"starts_on": ["terms_outside_year"]}
    year.refresh_from_db()
    assert (year.name, year.starts_on, year.ends_on) == ("2026-27", START, date(2027, 7, 9))
    [entry] = journal("organisation.year_updated")
    assert entry.before == {"name": "2026-2027", "ends_on": "2027-07-02"}
    assert entry.after == {"name": "2026-27", "ends_on": "2027-07-09"}


def test_make_another_year_current(in_school, head):
    first = new_year(head)
    second = organisation.create_year(
        actor=head, starts_on=date(2027, 9, 1), ends_on=date(2028, 7, 1)
    )

    organisation.make_current(second, actor=head)
    organisation.make_current(second, actor=head)  # déjà : rien

    first.refresh_from_db()
    assert (first.is_current, second.is_current) == (False, True)
    assert organisation.current_year() == second
    [entry] = journal("organisation.year_updated")
    assert (entry.entity_id, entry.after) == (second.pk, {"is_current": True})


def test_delete_a_year_only_when_not_current_and_without_classes(in_school, head):
    current = new_year(head)
    other = organisation.create_year(
        actor=head, starts_on=date(2027, 9, 1), ends_on=date(2028, 7, 1)
    )
    level = organisation.create_level(actor=head, name="7e EB", cycle="basic")
    organisation.create_class_group(actor=head, academic_year=other, level=level, section="A")

    with pytest.raises(BusinessError) as is_current:
        organisation.delete_year(current, actor=head)
    with pytest.raises(BusinessError) as in_use:
        organisation.delete_year(other, actor=head)
    ClassGroup.objects.filter(academic_year=other).delete()
    organisation.delete_year(other, actor=head)

    assert is_current.value.error.code == "year_is_current"
    assert in_use.value.error.code == "year_in_use"
    assert list(AcademicYear.objects.all()) == [current]
    assert Term.objects.filter(academic_year_id=other.pk).count() == 0
    [entry] = journal("organisation.year_deleted")
    assert entry.before["name"] == "2027-2028"


# Découpage


def tree(year: AcademicYear) -> list[TermNode]:
    """Le découpage actuel, tel que l'écran l'enverrait."""
    nodes: dict = {}
    roots = []
    for term in year.terms.all():
        node = TermNode(term.kind, term.name, term.starts_on, term.ends_on, term.pk)
        nodes[term.pk] = node
        (nodes[term.parent_id].children if term.parent_id else roots).append(node)
    return roots


def test_set_names_and_dates(in_school, head):
    year = new_year(head)
    nodes = tree(year)
    semester = nodes[0]
    semester.starts_on, semester.ends_on = date(2026, 9, 7), date(2026, 12, 23)
    semester.children[0].starts_on = date(2026, 9, 7)
    semester.children[0].ends_on = date(2026, 11, 7)
    semester.children[2].name = " Examens de Noël "

    organisation.set_terms(year, nodes, actor=head)

    terms = list(year.terms.all())
    assert (terms[1].starts_on, terms[1].ends_on) == (date(2026, 9, 7), date(2026, 11, 7))
    assert terms[3].name == "Examens de Noël"
    assert [term.pk for term in terms] == [node.id for _path, node, _p in organisation._walk(nodes)]
    [entry] = journal("organisation.terms_changed")
    assert entry.entity_id == year.pk
    assert entry.before["terms"][1] == {
        "kind": "period",
        "name": "",
        "parent": 0,
        "starts_on": None,
        "ends_on": None,
    }
    assert entry.after["terms"][1]["starts_on"] == "2026-09-07"


def test_add_and_remove_terms(in_school, head):
    year = new_year(head)
    nodes = tree(year)
    removed = nodes.pop()  # le 2e semestre et ses périodes
    nodes[0].children.insert(2, TermNode("period", name="Période bonus"))

    organisation.set_terms(year, nodes, actor=head)

    assert [(term.kind, term.name) for term in year.terms.all()] == [
        ("semester", ""),
        ("period", ""),
        ("period", ""),
        ("period", "Période bonus"),
        ("exam", ""),
    ]
    assert not Term.objects.filter(pk__in=[removed.id, *[c.id for c in removed.children]])
    assert list(year.terms.values_list("order", flat=True)) == [0, 1, 2, 3, 4]


def test_unchanged_terms_write_nothing_in_the_journal(in_school, head):
    year = new_year(head)

    organisation.set_terms(year, tree(year), actor=head)

    assert journal("organisation.terms_changed") == []


def test_term_rules(in_school, head):
    year = new_year(head)
    other = organisation.create_year(
        actor=head, starts_on=date(2027, 9, 1), ends_on=date(2028, 7, 1)
    )
    nodes = tree(year)
    first, second = nodes
    first.starts_on, first.ends_on = date(2026, 9, 7), date(2026, 12, 23)
    first.children[0].starts_on = date(2026, 9, 1)  # avant son semestre
    first.children[1].starts_on, first.children[1].ends_on = date(2026, 11, 9), date(2026, 11, 1)
    first.children[2].id = other.terms.first().pk  # d'une autre année
    second.ends_on = date(2027, 8, 1)  # après l'année
    second.children[0].kind = "semester"
    nodes.append(TermNode("period", children=[TermNode("exam")]))
    nodes.append(TermNode("exam", id=second.id))

    with pytest.raises(ValidationError) as error:
        organisation.set_terms(year, nodes, actor=head)

    assert error_codes(error.value) == {
        "terms.0.children.0.starts_on": ["outside_parent"],
        "terms.0.children.1.ends_on": ["end_before_start"],
        "terms.0.children.2.id": ["unknown_term"],
        "terms.1.ends_on": ["outside_year"],
        "terms.1.children.0.kind": ["nested_group"],
        "terms.2.kind": ["not_a_group"],
        "terms.3.id": ["duplicate_term"],
    }
    assert journal("organisation.terms_changed") == []


def test_too_many_terms(in_school, head):
    year = new_year(head, YearTemplate.EMPTY)

    with pytest.raises(ValidationError) as error:
        organisation.set_terms(year, [TermNode("period")] * 41, actor=head)

    assert error_codes(error.value) == {"terms": ["too_many_terms"]}


# Niveaux et options (C2)


def test_levels_are_created_in_order_with_unique_names(in_school, head):
    seventh = organisation.create_level(actor=head, name=" 7e EB ", cycle="basic")
    eighth = organisation.create_level(actor=head, name="8e EB", cycle="basic")

    with pytest.raises(BusinessError) as taken:
        organisation.create_level(actor=head, name="7E eb", cycle="basic")
    organisation.update_level(eighth, actor=head, name="8e", cycle="basic")

    assert (seventh.name, seventh.order, eighth.order) == ("7e EB", 0, 1)
    assert taken.value.error.code == "level_name_taken"
    assert [entry.after for entry in journal("organisation.level_created")] == [
        {"name": "7e EB", "cycle": "basic"},
        {"name": "8e EB", "cycle": "basic"},
    ]
    [entry] = journal("organisation.level_updated")
    assert (entry.before, entry.after) == ({"name": "8e EB"}, {"name": "8e"})


def test_reorder_levels(in_school, head):
    first = organisation.create_level(actor=head, name="1re", cycle="secondary_general")
    seventh = organisation.create_level(actor=head, name="7e EB", cycle="basic")

    with pytest.raises(ValidationError) as incomplete:
        organisation.reorder_levels([seventh.pk], actor=head)
    organisation.reorder_levels([seventh.pk, first.pk], actor=head)

    assert error_codes(incomplete.value) == {"ids": ["incomplete_levels"]}
    assert list(Level.objects.values_list("name", flat=True)) == ["7e EB", "1re"]
    [entry] = journal("organisation.levels_reordered")
    assert entry.before == {"levels": ["1re", "7e EB"]}
    assert entry.after == {"levels": ["7e EB", "1re"]}


def test_tracks_have_unique_names_and_capital_codes(in_school, head):
    track = organisation.create_track(actor=head, name="Électricité", code=" elec ")

    with pytest.raises(BusinessError) as name_taken:
        organisation.create_track(actor=head, name="électricité", code="EL")
    with pytest.raises(BusinessError) as code_taken:
        organisation.create_track(actor=head, name="Électronique", code="ELEC")

    assert track.code == "ELEC"
    assert name_taken.value.error.code == "track_name_taken"
    assert code_taken.value.error.code == "track_code_taken"
    [entry] = journal("organisation.track_created")
    assert (entry.actor, entry.after) == (head, {"name": "Électricité", "code": "ELEC"})


def test_a_level_or_track_used_by_a_class_cannot_be_deleted(in_school, head):
    year = new_year(head)
    level = organisation.create_level(actor=head, name="3e", cycle="secondary_technical")
    track = organisation.create_track(actor=head, name="Électricité", code="ELEC")
    unused = organisation.create_track(actor=head, name="Électronique", code="ELO")
    organisation.create_class_group(actor=head, academic_year=year, level=level, track=track)

    with pytest.raises(BusinessError) as level_in_use:
        organisation.delete_level(level, actor=head)
    with pytest.raises(BusinessError) as track_in_use:
        organisation.delete_track(track, actor=head)
    organisation.delete_track(unused, actor=head)

    assert level_in_use.value.error.code == "level_in_use"
    assert track_in_use.value.error.code == "track_in_use"
    assert list(Track.objects.all()) == [track]
    assert journal("organisation.level_deleted") == []
    [entry] = journal("organisation.track_deleted")
    assert entry.before == {"name": "Électronique", "code": "ELO"}


# Classes (C2)


@pytest.fixture
def setup(in_school, head):
    year = new_year(head)
    level = organisation.create_level(actor=head, name="3e", cycle="secondary_technical")
    track = organisation.create_track(actor=head, name="Électricité", code="ELEC")
    return year, level, track


def test_class_name_section_and_audit(setup, head):
    year, level, track = setup

    group = organisation.create_class_group(
        actor=head, academic_year=year, level=level, track=track, section=" a ", capacity=45
    )
    seventh = organisation.create_level(actor=head, name="7e EB", cycle="basic")
    single = organisation.create_class_group(actor=head, academic_year=year, level=seventh)

    assert group.name == "3e Électricité A"
    assert single.name == "7e EB"
    [entry, _] = journal("organisation.class_created")
    assert entry.entity_label == "3e Électricité A"
    assert entry.after == {
        "level": "3e",
        "track": "Électricité",
        "section": "A",
        "capacity": 45,
        "homeroom_teacher": None,
    }


def test_a_class_exists_once_per_year_even_without_track(setup, head):
    year, level, track = setup
    organisation.create_class_group(actor=head, academic_year=year, level=level, section="A")
    group = organisation.create_class_group(
        actor=head, academic_year=year, level=level, track=track, section="A"
    )

    with pytest.raises(BusinessError) as without_track:
        organisation.create_class_group(actor=head, academic_year=year, level=level, section="a")
    with pytest.raises(BusinessError) as moved:
        organisation.update_class_group(group, actor=head, track=None)

    assert without_track.value.error.code == "class_exists"
    assert moved.value.error.code == "class_exists"


def test_homeroom_teacher_is_an_active_member_of_the_school(setup, head, school, other_head):
    year, level, _track = setup
    teacher = MembershipFactory(school=school, roles=["teacher"]).user
    former = MembershipFactory(school=school, roles=["teacher"], is_active=False).user
    group = organisation.create_class_group(
        actor=head, academic_year=year, level=level, homeroom_teacher=teacher
    )

    for stranger in (other_head, former):
        with pytest.raises(ValidationError) as error:
            organisation.update_class_group(group, actor=head, homeroom_teacher=stranger)
        assert error_codes(error.value) == {"homeroom_teacher": ["not_staff"]}
    organisation.update_class_group(group, actor=head, homeroom_teacher=None, capacity=40)

    assert list(organisation.homeroom_candidates()) == sorted(
        [head, teacher], key=lambda user: (user.last_name, user.first_name)
    )
    [entry] = journal("organisation.class_updated")
    assert entry.before == {"capacity": None, "homeroom_teacher": str(teacher)}
    assert entry.after == {"capacity": 40, "homeroom_teacher": None}


def test_delete_a_class(setup, head):
    year, level, _track = setup
    group = organisation.create_class_group(actor=head, academic_year=year, level=level)

    organisation.delete_class_group(group, actor=head)

    assert not ClassGroup.objects.exists()
    [entry] = journal("organisation.class_deleted")
    assert entry.entity_label == "3e"


def test_a_class_cannot_use_a_level_of_another_school(setup, head, other_school):
    year, _level, _track = setup
    with use_school(other_school):
        foreign = Level.objects.create(name="3e", cycle="basic")

    with pytest.raises(CrossSchoolError):
        ClassGroup.objects.create(academic_year=year, level=foreign)


# Matricule (C3)


def test_new_school_gets_a_matricule_format_from_its_code(school):
    assert school.matricule_format == "ALPHA-{AAAA}-{0000}"


def test_set_the_matricule_format(in_school, head):
    new_year(head)
    organisation.create_track(actor=head, name="Mécanique", code="MG")
    organisation.create_track(actor=head, name="Construction", code="CONS")

    organisation.set_matricule_format(" ITIG-{OPT}-{AA}-{0000} ", actor=head)
    organisation.set_matricule_format("ITIG-{OPT}-{AA}-{0000}", actor=head)

    school = School.objects.get(pk=in_school.pk)
    assert school.matricule_format == "ITIG-{OPT}-{AA}-{0000}"
    # Année en cours et première option dans l'ordre alphabétique.
    assert organisation.matricule_example(school.matricule_format) == "ITIG-CONS-26-0001"
    [entry] = journal("organisation.matricule_format_changed")
    assert entry.before == {"matricule_format": "ALPHA-{AAAA}-{0000}"}
    assert entry.after == {"matricule_format": "ITIG-{OPT}-{AA}-{0000}"}


def test_a_wrong_matricule_format_is_refused_on_its_field(in_school, head):
    with pytest.raises(ValidationError) as error:
        organisation.set_matricule_format("ITIG-{0000}", actor=head)

    assert error_codes(error.value) == {"matricule_format": ["matricule_year_missing"]}
    assert journal("organisation.matricule_format_changed") == []
