"""Élèves fictifs de `make demo` : ~800 à l'ITIG, ~150 aux Volcans, avec leurs familles
(fratries comprises) et une inscription en 2026-2027 dans une classe de leur âge.

Noms inventés à partir de noms courants du Kivu ; téléphones dans la plage fictive `+24300…`
(jamais un vrai numéro). Tirage fixe par école : deux lancements donnent les mêmes élèves.
Créés une seule fois par école : un nouveau lancement garde les élèves déjà là, et ceux que
l'utilisateur a ajoutés en essayant l'application."""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from apps.core.tenancy import use_school
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


@dataclass(frozen=True)
class DemoStudents:
    count: int
    phone_prefix: str  # 3 chiffres après +24300


DEMO_STUDENTS = {
    "itig": DemoStudents(count=800, phone_prefix="2"),
    "volcans": DemoStudents(count=150, phone_prefix="3"),
}

LAST_NAMES = [
    "Kasereka", "Kambale", "Muhindo", "Paluku", "Katembo", "Mbusa", "Kakule", "Mumbere",
    "Sikuli", "Musubao", "Vagheni", "Kyakimwa", "Bisimwa", "Cirhuza", "Mugisho", "Byamungu",
    "Bahati", "Habimana", "Nzabonimpa", "Bakungu", "Mastaki", "Kombi", "Lwanzo", "Maombi",
    "Kilolo", "Mulumba", "Ilunga", "Tshibanda", "Ngoy", "Kalume", "Lukusa", "Matabaro",
]  # fmt: skip
FEMALE_MIDDLE_NAMES = [
    "Kahindo", "Kavira", "Masika", "Kasoki", "Mapendo", "Furaha", "Zawadi", "Neema",
    "Kavugho", "Mbambu", "Asifiwe", "Riziki",
]  # fmt: skip
MALE_FIRST_NAMES = [
    "Jean", "Paul", "Pierre", "Joseph", "Emmanuel", "David", "Daniel", "Moïse", "Josué",
    "Christian", "Patrick", "Éric", "Justin", "Samuel", "Fiston", "Héritier", "Dieudonné",
    "Junior", "Blaise", "Olivier", "Espoir", "Gloire", "Prince", "Isaac",
]  # fmt: skip
FEMALE_FIRST_NAMES = [
    "Esther", "Marie", "Grâce", "Rachel", "Sarah", "Ruth", "Deborah", "Christelle", "Gloria",
    "Divine", "Merveille", "Bénédicte", "Chance", "Nadège", "Arlette", "Jeanne", "Francine",
    "Rebecca", "Anuarite", "Solange", "Pascaline", "Elisabeth",
]  # fmt: skip
BIRTH_PLACES = ["Goma", "Goma", "Goma", "Sake", "Rutshuru", "Butembo", "Bukavu", "Masisi"]
QUARTIERS = {
    "Goma": ["Himbi", "Katindo", "Mapendo", "Mikeno", "Les Volcans", "Lac Vert", "Kyeshero"],
    "Karisimbi": ["Katoyi", "Majengo", "Mabanga Nord", "Mabanga Sud", "Murara", "Kasika"],
}
AVENUES = [
    "du Lac", "des Écoles", "de la Paix", "Kituku", "Mont Goma", "des Palmiers", "Nyiragongo",
]  # fmt: skip
# Âge à la rentrée selon le niveau (7e EB : 12 ans).
LEVEL_AGE = {"7e EB": 12, "8e EB": 13, "1re": 14, "2e": 15, "3e": 16, "4e": 17}


def _family_code(rng: random.Random, taken: set[str]) -> str:
    while True:
        code = "".join(rng.choice(FAMILY_CODE_ALPHABET) for _ in range(FAMILY_CODE_LENGTH))
        if code not in taken:
            taken.add(code)
            return code


def _address(rng: random.Random) -> dict:
    commune = rng.choice(list(QUARTIERS))
    return {
        "commune": commune,
        "quartier": rng.choice(QUARTIERS[commune]),
        "avenue": rng.choice(AVENUES),
        "number": str(rng.randint(1, 250)),
    }


def _guardians(rng: random.Random, family: Family, last_name: str, phones) -> list[Guardian]:
    mother = f"{rng.choice(FEMALE_MIDDLE_NAMES)} {rng.choice(FEMALE_FIRST_NAMES)}"
    father = f"{last_name} {rng.choice(MALE_FIRST_NAMES)}"
    if rng.random() < 0.8:
        people = [("father", father), ("mother", mother)]
    else:
        people = [("guardian", f"{rng.choice(LAST_NAMES)} {rng.choice(MALE_FIRST_NAMES)}")]
    return [
        Guardian(
            family=family,
            full_name=name,
            relationship=relationship,
            phone=next(phones),
            is_primary=index == 0,
            is_emergency_contact=index == 0,
        )
        for index, (relationship, name) in enumerate(people)
    ]


def _student(
    rng: random.Random, family: Family, last_name: str, group: ClassGroup, address: dict
) -> Student:
    sex = rng.choice(Student.Sex.values)
    female = sex == Student.Sex.FEMALE
    age = LEVEL_AGE.get(group.level.name, 14) + rng.choice([0, 0, 0, 1, 1, 2])
    birth_date = date(2026 - age, 1, 1) + timedelta(days=rng.randint(0, 364))
    return Student(
        family=family,
        last_name=last_name,
        middle_name=rng.choice(FEMALE_MIDDLE_NAMES if female else LAST_NAMES),
        first_name=rng.choice(FEMALE_FIRST_NAMES if female else MALE_FIRST_NAMES),
        sex=sex,
        birth_date=birth_date,
        birth_place=rng.choice(BIRTH_PLACES),
        nationality="Congolaise",
        origin_province="Nord-Kivu",
        address=address,
        photo_consent=rng.random() < 0.7,
    )


def _create(school: School, demo: DemoStudents, shared_guardians: list[Guardian]) -> None:
    rng = random.Random(f"mwangaza-demo-{school.code}")
    year = AcademicYear.objects.get(is_current=True)
    groups = list(ClassGroup.objects.filter(academic_year=year).select_related("level", "track"))
    # Places dans les classes, au hasard, jusqu'au nombre d'élèves voulu.
    seats = [groups[index % len(groups)] for index in range(demo.count)]
    rng.shuffle(seats)
    taken_codes = set(Family.all_schools.values_list("code", flat=True))
    phones = (f"+24300{demo.phone_prefix}{number:06d}" for number in range(1, 10**6))

    families, guardians, students = [], [], []
    while len(students) < demo.count:
        family = Family(code=_family_code(rng, taken_codes))
        address = _address(rng)
        last_name = rng.choice(LAST_NAMES)
        if shared_guardians and not families:
            # Famille qui a aussi des enfants à l'ITIG : mêmes parents, fiche et code à part.
            guardians += [
                Guardian(
                    family=family,
                    full_name=g.full_name,
                    relationship=g.relationship,
                    phone=g.phone,
                    is_primary=g.is_primary,
                    is_emergency_contact=g.is_emergency_contact,
                )
                for g in shared_guardians
            ]
        else:
            guardians += _guardians(rng, family, last_name, phones)
        families.append(family)
        size = rng.choices([1, 2, 3, 4], weights=[62, 26, 9, 3])[0]
        for _ in range(min(size, demo.count - len(students))):
            students.append(_student(rng, family, last_name, seats[len(students)], address))

    Family.objects.bulk_create(families)
    Guardian.objects.bulk_create(guardians)
    enrollments = []
    for number, (student, group) in enumerate(zip(students, seats, strict=True), start=1):
        student.matricule = matricule.render(
            school.matricule_format,
            year=year.starts_on.year,
            number=number,
            track_code=group.track.code if group.track else "",
        )
        enrollments.append(
            Enrollment(
                student=student,
                academic_year=year,
                class_group=group,
                enrolled_on=year.starts_on - timedelta(days=rng.randint(0, 40)),
            )
        )
    Student.objects.bulk_create(students)
    Enrollment.objects.bulk_create(enrollments)
    MatriculeSequence.objects.update_or_create(
        academic_year=year, defaults={"last_number": len(students)}
    )


def create_demo_students(schools: dict[str, School]) -> None:
    shared: list[Guardian] = []
    for code, demo in DEMO_STUDENTS.items():
        school = schools[code]
        with use_school(school):
            if not Student.objects.exists():
                _create(school, demo, shared)
            first = Family.objects.order_by("created_at", "id").first()
            if code == "itig" and first is not None:
                shared = list(first.guardians.all())
