"""Règles de délibération (8.4.1, NB.4) : chaque règle du règlement de l'école et la règle citée,
préréglages et règles d'un niveau par l'API, années d'avant et âge de l'élève, note de repêchage
saisie et signée par l'enseignant du cours, journal, isolation."""

from datetime import date
from decimal import Decimal

import pytest

from apps.academics import resits
from apps.academics.grades import term_maximum
from apps.academics.models import GENERAL, MAIN, OPTION, PRACTICAL, Course, Evaluation, Grade
from apps.academics.resits import CourseResit, Record
from apps.academics.tests.test_grades import setup
from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.schools import organisation
from apps.schools.models import Level, Term
from apps.schools.pass_rules import CATHOLIC, COMMON, PRESETS
from apps.students.models import Enrollment
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

SETTINGS = "/api/school/settings/"


def fill_year(school, data, course, percents: dict) -> None:
    """Note toutes les périodes et tous les examens du cours : chaque élève à son pourcentage."""
    with use_school(school):
        terms = Term.objects.filter(academic_year=data["year"], kind__in=["period", "exam"])
        for term in terms:
            if term.kind == "exam" and not course.has_exam:
                continue
            maximum = term_maximum(course, term)
            evaluation = Evaluation.objects.create(
                course=course, term=term, name="Total", max_score=maximum
            )
            for enrollment, percent in percents.items():
                Grade.objects.create(
                    evaluation=evaluation,
                    enrollment_id=enrollment,
                    score=Decimal(percent) * maximum / 100,
                )


@pytest.fixture
def physics_teacher(school):
    return MembershipFactory(school=school, roles=["teacher"]).user


@pytest.fixture
def data(school, head, physics_teacher):
    data = setup(school, head, teacher=physics_teacher)
    # Bahati réussit tout ; Kambale a 48 % en Physique (échoué, repêchage ouvert dès 45 %).
    fill_year(school, data, data["physics"], {data["amani"]: 70, data["josue"]: 48})
    fill_year(school, data, data["workshop"], {data["amani"]: 80, data["josue"]: 80})
    return data


def class_url(data) -> str:
    return f"/api/class-groups/{data['a'].pk}/resits/"


def resit_url(data, key="josue", course="physics") -> str:
    return f"/api/resits/enrollments/{data[key]}/courses/{data[course].pk}/"


def student(client, data, key="josue") -> dict:
    rows = client.get(class_url(data)).json()["students"]
    return next(s for s in rows if s["enrollment"] == data[key])


# Chaque règle, sans base de données


def failing(*courses: tuple[str, str], percent=45) -> list[CourseResit]:
    return [
        CourseResit(Course(name=name, category=kind), Decimal(percent)) for name, kind in courses
    ]


MATHS, FRENCH, WORKSHOP = ("Maths", MAIN), ("Français", MAIN), ("Atelier", PRACTICAL)
OPTIONS = [(f"Option {n}", OPTION) for n in range(3)]


@pytest.mark.parametrize(
    ("preset", "record", "expected"),
    [
        # Passe, double sous le seuil, repêchage d'un échec partiel avec le total au seuil.
        (COMMON, Record(Decimal(60)), ("passed", "passed", {})),
        (
            COMMON,
            Record(Decimal(48)),
            ("failed", "below_pass", {"percent": Decimal(48), "threshold": 50}),
        ),
        (COMMON, Record(Decimal(60), failing(MATHS)), ("resit", "resit", {"count": 1})),
        (
            CATHOLIC,
            Record(Decimal(52), failing(MATHS)),
            ("failed", "below_resit", {"percent": Decimal(52), "threshold": 53}),
        ),
        # Limites du repêchage : pratique, nombre, cours principaux ensemble, branches d'option.
        (
            COMMON,
            Record(Decimal(60), failing(WORKSHOP)),
            ("failed", "practical", {"courses": "Atelier"}),
        ),
        (
            COMMON,
            Record(Decimal(60), failing(*[(f"C{n}", GENERAL) for n in range(5)])),
            ("failed", "too_many_resits", {"count": 5, "max": 4}),
        ),
        (
            COMMON,
            Record(Decimal(60), failing(MATHS, FRENCH)),
            ("failed", "main_courses", {"courses": "Maths, Français", "max": 1}),
        ),
        (COMMON, Record(Decimal(60), failing(*OPTIONS)), ("resit", "resit", {"count": 3})),
        (
            CATHOLIC,
            Record(Decimal(60), failing(*OPTIONS)),
            ("failed", "option_courses", {"count": 3, "max": 2}),
        ),
        # Entrer dans la dernière classe : 55 % et aucun échec (préréglage catholique).
        (
            CATHOLIC,
            Record(Decimal(56), enters_final=True),
            ("passed", "passed_final", {"threshold": 55}),
        ),
        (
            CATHOLIC,
            Record(Decimal(70), failing(MATHS), enters_final=True),
            ("failed", "final_class", {"percent": Decimal(70), "threshold": 55}),
        ),
        (COMMON, Record(Decimal(52), enters_final=True), ("passed", "passed", {})),
        # Qui ne peut pas doubler : orienté, exclu (tripler, redoublements), sauf l'élève jeune.
        (
            COMMON,
            Record(Decimal(35)),
            ("orient", "below_orientation", {"percent": Decimal(35), "threshold": 40}),
        ),
        (
            CATHOLIC,
            Record(Decimal(45), age=13),
            ("orient", "below_orientation", {"percent": Decimal(45), "threshold": 50}),
        ),
        (COMMON, Record(Decimal(45), repeated_class=True), ("exclude", "repeated_class", {})),
        (COMMON, Record(Decimal(60), repeated_class=True), ("passed", "passed", {})),
        (
            CATHOLIC,
            Record(Decimal(52), failing(MATHS), repeats=2),
            ("exclude", "max_repeats", {"max": 2}),
        ),
        # Conduite et application : MA, ou ME ou moins, autant de périodes **de suite**.
        (COMMON, Record(Decimal(60), conduct=["MA", "TB", "MA"]), ("passed", "passed", {})),
        (
            COMMON,
            Record(Decimal(60), conduct=["TB", "MA", "MA"]),
            ("exclude", "conduct_ma", {"count": 2}),
        ),
        (
            COMMON,
            Record(Decimal(60), conduct=["ME", "MA", "ME"]),
            ("exclude", "conduct_me", {"count": 3}),
        ),
        (COMMON, Record(Decimal(60), application=["MA", "MA"]), ("passed", "passed", {})),
        (
            CATHOLIC,
            Record(Decimal(60), application=["MA", "MA"]),
            ("exclude", "application_ma", {"count": 2}),
        ),
        # Sans note, ou une note qui manque : pas de décision des notes.
        (COMMON, Record(None, noted=False), ("unranked", "no_grades", {})),
        (COMMON, Record(Decimal(60), complete=False), ("incomplete", "missing_grades", {})),
    ],
)
def test_each_rule_of_the_school_gives_its_outcome_and_is_cited(preset, record, expected):
    assert resits.decide(PRESETS[preset], record) == expected


def test_a_young_student_repeats_instead_of_leaving():
    """Exception d'âge : au moins un an sous l'âge limite du niveau et au moins 40 %."""
    rules = {**PRESETS[CATHOLIC], "age_limit": 14}
    young = Record(Decimal(45), age=13)
    assert resits.decide(rules, young) == ("failed", "age_exception", {"age": 13, "limit": 14})
    assert resits.decide(rules, Record(Decimal(45), age=14))[0] == "orient"
    assert resits.decide(rules, Record(Decimal(38), age=13))[0] == "orient"
    tripled = Record(Decimal(52), failing(MATHS), age=13, repeated_class=True)
    assert resits.decide(rules, tripled)[1] == "age_exception"


# Par l'API : règle citée, préréglages, règles d'un niveau, catégorie des cours


def test_the_proposal_cites_the_rule_and_follows_the_preset_and_the_level(
    api, school, head, physics_teacher, data
):
    director = api(MembershipFactory(school=school, roles=["study_director"]).user)
    rows = director.get(class_url(data)).json()["students"]
    # Bahati n'a aucun cours échoué : absent du tableau. Kambale : 48 % en Physique, 70,9 % de
    # l'année : repêchage.
    assert [r["enrollment"] for r in rows] == [data["josue"]]
    kambale = rows[0]
    assert (kambale["outcome"], kambale["percent"]) == ("resit", "70.9")
    assert (kambale["rule"], kambale["rule_params"]) == ("resit", {"count": 1})
    [course] = kambale["courses"]
    assert (course["course_name"], course["percent"], course["eligible"]) == (
        "Physique",
        "48.0",
        True,
    )
    # La délibération montre la même règle.
    deliberation = director.get(f"/api/class-groups/{data['a'].pk}/deliberation/").json()
    found = next(r for r in deliberation["students"] if r["enrollment"] == data["josue"])
    assert (found["proposed"], found["rule"]) == ("resit", "resit")

    # Préréglage « réseau catholique », donné par l'API puis enregistré comme les autres règles.
    settings = api(head)
    catholic = settings.get(SETTINGS).json()["pass_rule_presets"][CATHOLIC]
    assert settings.patch(SETTINGS, {"pass_rules": catholic}).json()["pass_rules"] == catholic
    assert (
        api(MembershipFactory(school=school, roles=["secretary"]).user)
        .patch(SETTINGS, {"pass_rules": {"resit_percent": 60}})
        .status_code
        == 403
    )

    # Règles du niveau : repêchage à partir de 75 % ; `{}` rend celles de l'école.
    level_url = f"/api/levels/{data['a'].level_id}/"
    level = settings.patch(level_url, {"pass_rules": {"resit_percent": 75}})
    assert level.json()["pass_rules"] == {"resit_percent": 75}
    failed = student(director, data)
    assert (failed["outcome"], failed["rule"]) == ("failed", "below_resit")
    assert failed["rule_params"] == {"percent": "70.9", "threshold": 75}
    assert failed["courses"][0]["eligible"] is False
    assert settings.patch(level_url, {"pass_rules": {}}).json()["pass_rules"] == {}
    assert student(director, data)["outcome"] == "resit"

    # Un cours pratique (atelier, laboratoire) n'a pas de seconde session : l'élève double.
    with use_school(school):
        Course.objects.filter(pk=data["physics"].pk).update(category=PRACTICAL)
    failed = student(director, data)
    assert (failed["outcome"], failed["rule"]) == ("failed", "practical")
    assert api(physics_teacher).put(resit_url(data), {"percent": "60"}).json()["code"] == (
        "not_a_resit_course"
    )


def test_the_course_teacher_enters_and_signs_the_resit_grade_and_it_is_logged(
    api, school, head, physics_teacher, data
):
    other = MembershipFactory(school=school, roles=["teacher"]).user
    assert api(other).put(resit_url(data), {"percent": "60"}).status_code == 403
    assert api(other).get(class_url(data)).status_code == 403

    client = api(physics_teacher)
    assert student(client, data)["courses"][0]["can_enter"] is True
    # Pas de repêchage pour un élève qui a réussi le cours, ni pour un cours réussi.
    assert client.put(resit_url(data, "amani"), {"percent": "60"}).status_code == 400
    workshop = resit_url(data, "josue", "workshop")
    assert client.put(workshop, {"percent": "60"}).status_code == 403  # pas son cours
    director = MembershipFactory(school=school, roles=["study_director"]).user
    assert api(director).put(workshop, {"percent": "60"}).json()["code"] == "not_a_resit_course"
    assert client.put(resit_url(data), {"percent": "101"}).status_code == 400

    done = client.put(resit_url(data), {"percent": "30"}).json()
    [course] = done["courses"]
    assert (course["resit_percent"], course["passed"]) == ("30.0", False)
    assert course["signed_by"] == physics_teacher.get_full_name()
    # Un échec au repêchage pour un seul cours : l'élève passe tant que le seuil de 2 n'est pas
    # atteint ; l'école peut le ramener à 1.
    assert done["outcome"] == "passed"
    api(head).patch(SETTINGS, {"pass_rules": {"resit_failures_to_fail": 1}})
    assert student(client, data)["outcome"] == "failed"
    redone = client.put(resit_url(data), {"percent": "55.5"}).json()
    assert (redone["outcome"], redone["courses"][0]["passed"]) == ("passed", True)

    with use_school(school):
        entries = list(AuditLog.objects.filter(action="resit.grade_changed").order_by("created_at"))
    assert [e.after["percent"] for e in entries] == ["30.0", "55.5"]
    assert entries[1].before["percent"] == "30.0"

    removed = client.delete(resit_url(data)).json()
    assert removed["outcome"] == "resit" and removed["courses"][0]["resit_percent"] is None
    with use_school(school):
        assert AuditLog.objects.filter(action="resit.grade_changed").count() == 3


def test_another_school_cannot_read_or_enter_a_resit_grade(api, other_school, data):
    other = api(
        MembershipFactory(school=other_school, roles=["study_director"]).user, host="beta.localhost"
    )
    assert other.get(class_url(data)).status_code == 404
    assert other.put(resit_url(data), {"percent": "60"}).status_code == 404


def test_earlier_years_age_conduct_and_the_last_class_come_from_the_school_data(
    api, school, head, data
):
    """Ce que les règles lisent dans la base : années d'avant de l'élève (dans cette école),
    date de naissance, conduite de suite, classe suivante avec l'Examen d'État."""
    from apps.academics.models import ConductGrade

    director = api(MembershipFactory(school=school, roles=["study_director"]).user)
    level_url = f"/api/levels/{data['a'].level_id}/"
    # Kambale doit doubler (repêchage fermé dès 75 %) ; il a déjà fait ce niveau l'an passé.
    api(head).patch(level_url, {"pass_rules": {"resit_percent": 75}})
    with use_school(school):
        enrollment = Enrollment.objects.select_related("student").get(pk=data["josue"])
        before = organisation.create_year(
            actor=head, starts_on=date(2025, 9, 1), ends_on=date(2026, 7, 2)
        )
        group = organisation.create_class_group(
            actor=head,
            academic_year=before,
            level=data["a"].level,
            track=data["a"].track,
            section="A",
        )
        Enrollment.objects.create(
            student=enrollment.student, academic_year=before, class_group=group
        )
    tripled = student(director, data)
    assert (tripled["outcome"], tripled["rule"]) == ("exclude", "repeated_class")
    # Né en 2014 : 13 ans à la rentrée 2027, un an sous l'âge limite du niveau (14) : il double.
    with use_school(school):
        enrollment.student.birth_date = date(2014, 3, 1)
        enrollment.student.save()
    api(head).patch(SETTINGS, {"pass_rules": {"age_exception_years": 1}})
    api(head).patch(level_url, {"pass_rules": {"resit_percent": 75, "age_limit": 14}})
    young = student(director, data)
    assert (young["outcome"], young["rule"]) == ("failed", "age_exception")
    assert young["rule_params"] == {"age": 13, "limit": 14}
    api(head).patch(level_url, {"pass_rules": {}})

    # Conduite : 2 périodes MA de suite font proposer le renvoi, même avec de bonnes notes.
    with use_school(school):
        terms = Term.objects.filter(academic_year=data["year"], kind="period").order_by("order")
        for term in (terms[0], terms[2]):
            ConductGrade.objects.create(
                enrollment_id=data["amani"],
                term=term,
                grade="MA",
                reason="Fraude",
                overridden_by=head,
            )
    rows = {r["enrollment"]: r for r in director.get(class_url(data)).json()["students"]}
    assert data["amani"] not in rows  # P1 et P3 : pas de suite
    with use_school(school):
        ConductGrade.objects.create(
            enrollment_id=data["amani"],
            term=terms[1],
            grade="MA",
            reason="Fraude",
            overridden_by=head,
        )
    rows = {r["enrollment"]: r for r in director.get(class_url(data)).json()["students"]}
    assert (rows[data["amani"]]["outcome"], rows[data["amani"]]["rule"]) == (
        "exclude",
        "conduct_ma",
    )

    # Classe suivante avec l'Examen d'État : 75 % et aucun échec pour y entrer.
    with use_school(school):
        Level.objects.create(
            name="Terminale", cycle="secondary_technical", order=99, has_state_exam=True
        )
    api(head).patch(
        SETTINGS,
        {
            "pass_rules": {
                "final_pass_percent": 75,
                "conduct_ma_to_exclude": 0,
                "conduct_me_to_exclude": 0,
                "exclude_repeated_class": False,
            }
        },
    )
    rows = {r["enrollment"]: r for r in director.get(class_url(data)).json()["students"]}
    assert rows[data["josue"]]["rule"] == "final_class"  # 70,9 % et un cours échoué
    assert data["amani"] not in rows  # 77,1 % sans échec : passe

    # Un élève sans aucune note est « non classé » (pas d'échec).
    with use_school(school):
        group_b = Enrollment.objects.get(pk=data["b"]).class_group_id
    other = director.get(f"/api/class-groups/{group_b}/resits/").json()["students"]
    assert [(r["outcome"], r["rule"]) for r in other] == [("unranked", "no_grades")]
