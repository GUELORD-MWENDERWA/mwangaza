"""Élèves fictifs d'un espace de démonstration : ~800 pour le profil `itig`, ~150 pour
`volcans`, avec leurs familles (fratries comprises) et une inscription en 2026-2027 dans une
classe de leur âge.

Noms inventés à partir de noms courants du Kivu ; téléphones dans la plage réservée de l'espace
(jamais un vrai numéro). Tirage fixe par école : deux lancements donnent les mêmes élèves.
Créés une seule fois par école : un nouveau lancement garde les élèves déjà là, et ceux que
l'utilisateur a ajoutés en essayant l'application."""

import random
from datetime import date, timedelta

from apps.core.tenancy import use_school
from apps.schools import matricule
from apps.schools.demo import DemoSpace
from apps.schools.models import AcademicYear, ClassGroup
from apps.students.models import (
    FAMILY_CODE_ALPHABET,
    FAMILY_CODE_LENGTH,
    Enrollment,
    Family,
    Guardian,
    MatriculeSequence,
    Student,
)

# Nombre d'élèves de chaque profil.
DEMO_STUDENTS = {"itig": 800, "volcans": 150}

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
    # Hors de `rng` : ajouter des numéros ne change pas le reste des données de démonstration.
    numbers = random.Random(f"{last_name}{birth_date}{group.pk}")
    return Student(
        family=family,
        last_name=last_name,
        middle_name=rng.choice(FEMALE_MIDDLE_NAMES if female else LAST_NAMES),
        first_name=rng.choice(FEMALE_FIRST_NAMES if female else MALE_FIRST_NAMES),
        sex=sex,
        birth_date=birth_date,
        birth_place=rng.choice(BIRTH_PLACES),
        national_id=f"61022-{numbers.randrange(10**12, 10**13)}",
        permanent_number=f"2-{numbers.randrange(10**9, 10**10)}",
        nationality="Congolaise",
        origin_province="Nord-Kivu",
        address=address,
        photo_consent=rng.random() < 0.7,
    )


def _create(space: DemoSpace, shared_guardians: list[Guardian]) -> None:
    school, count = space.school, DEMO_STUDENTS[space.profile]
    rng = random.Random(f"mwangaza-demo-{school.code}")
    year = AcademicYear.objects.get(is_current=True)
    groups = list(ClassGroup.objects.filter(academic_year=year).select_related("level", "track"))
    # Places dans les classes, au hasard, jusqu'au nombre d'élèves voulu.
    seats = [groups[index % len(groups)] for index in range(count)]
    rng.shuffle(seats)
    taken_codes = set(Family.all_schools.values_list("code", flat=True))
    phones = (space.numbers.guardian(number) for number in range(1, 10**4))

    families, guardians, students = [], [], []
    while len(students) < count:
        family = Family(code=_family_code(rng, taken_codes))
        address = _address(rng)
        last_name = rng.choice(LAST_NAMES)
        if shared_guardians and not families:
            # Famille qui a aussi des enfants dans l'autre école de `make demo` : mêmes parents,
            # fiche et code à part.
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
        for _ in range(min(size, count - len(students))):
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


def create_demo_students(spaces: list[DemoSpace]) -> None:
    """Créés une seule fois par espace. Remplis ensemble (`make demo`), deux espaces ont une
    famille en commun : la première du premier a aussi des enfants dans le suivant."""
    shared: list[Guardian] = []
    for space in spaces:
        with use_school(space.school):
            if not Student.objects.exists():
                _create(space, shared)
            first = Family.objects.order_by("created_at", "id").first()
            if not shared and first is not None:
                shared = list(first.guardians.all())


# Fichier Excel fictif pour essayer l'import (D1) : `make demo-excel`.

ITIG_CLASS_LABELS = [
    "7E EB A", "7E EB B", "7E EB C", "8E EB A", "8E EB B", "8E EB C",
    "1RE ELEC A", "1RE ELEC B", "2E ELEC A", "3E ELEC A", "4E ELEC A",
    "1RE ELECTRONIQUE A", "2E ELO A", "3E ELECTRONIQUE A", "4E ELO A",
    "1RE MG A", "2E MG A", "3EME MG A", "4E MG A", "1RE MA A", "2E MA A", "3E MA A", "4E MA A",
]  # fmt: skip


def import_rows(count: int, class_labels: list[str], *, seed: int = 2026) -> list[list]:
    """Lignes d'une liste d'élèves comme en tient un secrétariat : fratries (même parent, même
    téléphone), dates en cellule date ou en texte, et quelques erreurs glissées exprès (date
    impossible, classe inconnue, sexe manquant, ligne en double, téléphone illisible)."""
    rng = random.Random(seed)
    rows = []
    while len(rows) < count:
        last_name = rng.choice(LAST_NAMES).upper()
        parent = f"{last_name} {rng.choice(MALE_FIRST_NAMES)}"
        phone = f"0004{rng.randrange(10**5, 10**6)}"
        for _child in range(rng.choice([1, 1, 1, 2, 2, 3])):
            sex = rng.choice("MF")
            first = rng.choice(MALE_FIRST_NAMES if sex == "M" else FEMALE_FIRST_NAMES)
            middle = rng.choice(FEMALE_MIDDLE_NAMES if sex == "F" else LAST_NAMES).upper()
            born = date(2008, 1, 1) + timedelta(days=rng.randrange(6 * 365))
            rows.append(
                [
                    len(rows) + 1,
                    last_name,
                    middle,
                    first,
                    sex,
                    born if rng.random() < 0.8 else born.strftime("%d/%m/%Y"),
                    rng.choice(BIRTH_PLACES),
                    rng.choice(class_labels),
                    parent,
                    phone,
                ]
            )
    rows = rows[:count]
    for index, mistake in zip(range(13, count, 97), range(5), strict=False):
        row = rows[index]
        if mistake == 0:
            row[5] = "31/02/2009"
        elif mistake == 1:
            row[7] = "1RE ELEC C"
        elif mistake == 2:
            row[4] = ""
        elif mistake == 3:
            rows[index] = [row[0], *rows[index - 5][1:]]
        else:
            row[9] = "09712"
    return rows


IMPORT_HEADERS = [
    "N°", "NOM", "POSTNOM", "PRENOM", "SEXE", "DATE NAISS.", "LIEU NAISS.", "CLASSE",
    "NOM DU PARENT", "TEL",
]  # fmt: skip


def import_workbook(rows: list[list]) -> bytes:
    """Classeur d'une liste d'élèves : un titre, une ligne vide, puis les colonnes."""
    import io

    import openpyxl

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Liste"
    sheet.append(["LISTE DES ÉLÈVES — ANNÉE SCOLAIRE 2026-2027 (données fictives)"])
    sheet.append([])
    sheet.append(IMPORT_HEADERS)
    for row in rows:
        sheet.append(row)
    for cell in sheet["F"][3:]:
        cell.number_format = "DD/MM/YYYY"
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()
