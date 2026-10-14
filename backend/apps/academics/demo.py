"""Cours de démonstration (8.1, `docs/07-a-fournir.md` § 4) : chaque classe reçoit une grille
officielle (`official.py`) d'après son niveau et son option, avec des heures inventées quand la
grille n'en donne pas, et quelques cours ont un enseignant parmi les comptes d'exemple. Rejouable :
les cours de la grille sont remis comme au départ, ceux ajoutés en essayant restent."""

from apps.academics.models import Course
from apps.academics.official import BY_KEY
from apps.accounts.models import User
from apps.core.tenancy import use_school
from apps.schools.demo import DemoSpace
from apps.schools.models import ClassGroup
from apps.schools.organisation import current_year

# (niveau, code de l'option) → grille ; une classe sans grille connue n'a pas de cours.
BASIC = "basic_education"
TRACK_GRIDS = {"ELEC": "electricity", "MG": "general_mechanics", "MA": "general_mechanics"}

# Compte d'exemple → cours qu'il donne : (niveau, option, section, cours).
TEACHERS = {
    "itig": {
        # L'enseignant des deux écoles, le chef d'atelier, la directrice des études.
        "+243000001008": [
            (level, "ELEC", section, course)
            for level, section in (("1re", "A"), ("1re", "B"), ("2e", "A"))
            for course in ("Mathématique", "Physique")
        ],
        "+243000001010": [
            ("1re", "ELEC", "A", "Atelier électrique"),
            ("1re", "ELEC", "B", "Atelier électrique"),
            ("2e", "ELEC", "A", "Atelier électrique"),
        ],
        "+243000001002": [("1re", "ELEC", "A", "Français")],
    },
    "volcans": {"+243000001008": [("7e EB", "", "A", "Mathématique")]},
}


def _grid_key(group: ClassGroup) -> str | None:
    if group.level.cycle == group.level.Cycle.BASIC:
        return BASIC
    code = group.track.code if group.track else ""
    if code == "ELO":
        return "electronics_1" if group.level.name == "1re" else "electronics_2"
    return TRACK_GRIDS.get(code)


def create_demo_courses(spaces: list[DemoSpace]) -> None:
    for space in spaces:
        assigned: dict[tuple[str, str, str, str], User] = {}
        for phone, courses in TEACHERS.get(space.profile, {}).items():
            user = User.objects.get(phone=space.numbers.of(phone))
            assigned.update({course: user for course in courses})
        with use_school(space.school):
            year = current_year()
            groups = ClassGroup.objects.filter(academic_year=year).select_related("level", "track")
            existing: dict[tuple, Course] = {
                (course.class_group_id, course.name.casefold()): course
                for course in Course.objects.filter(class_group__academic_year=year)
            }
            created, updated = [], []
            for group in groups:
                key = _grid_key(group)
                if key is None:
                    continue
                code = group.track.code if group.track else ""
                for order, (name, maximum, exam, hours) in enumerate(BY_KEY[key].courses):
                    course = existing.get((group.pk, name.casefold()))
                    if course is None:
                        course = Course(class_group=group, name=name)
                        created.append(course)
                    else:
                        updated.append(course)
                    course.period_max, course.has_exam, course.order = maximum, exam, order
                    # Inventées d'après le maximum : de 1 h (sur 10 ou 20) à 7 h (atelier sur 100).
                    course.weekly_hours = hours or max(1, round(maximum / 15))
                    course.teacher = assigned.get((group.level.name, code, group.section, name))
            Course.objects.bulk_create(created)
            Course.objects.bulk_update(
                updated, ["period_max", "has_exam", "order", "weekly_hours", "teacher"]
            )
