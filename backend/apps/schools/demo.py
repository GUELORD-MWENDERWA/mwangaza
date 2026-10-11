"""Espaces de démonstration (`docs/07-a-fournir.md` § 4, `03` § 4 bis) : ce qu'est un espace à
remplir (`DemoSpace`), les deux écoles de `make demo` et leur organisation.

L'ITIG n'est que l'école d'exemple : ce qui la décrit vient d'ici, jamais du code de l'application.
Les données d'exemple sont rangées par **profil** (`itig` : grande école technique, ≈ 800 élèves ;
`volcans` : petite, ≈ 150), pas par code d'école : la console en remplit d'autres espaces (4.17.2).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.core.files import File
from django.utils import timezone

from apps.accounts.models import User
from apps.core.tenancy import use_school
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Term, Track
from apps.schools.organisation import YearTemplate, template_terms

# Logo public de l'ITIG (site web), recadré : `docs/ecole-pilote/fiche-itig.md`.
ITIG_LOGO = settings.BASE_DIR.parent / "docs/ecole-pilote/documents/2026-09-25-logo-itig-carre.png"
DEMO_LOGOS = {"itig": ITIG_LOGO}
PHONE_LENGTH = len("+243000001001")


@dataclass(frozen=True)
class DemoNumbers:
    """Numéros d'un espace, dans la plage réservée (`accounts/phone.py`) et tous en +243 00… :
    tapés sans indicatif, ils commencent par `000`. `staff` est suivi des 4 derniers chiffres du
    compte d'exemple (`1004` : comptable), `guardians` d'un compteur."""

    staff: str
    guardians: str

    def of(self, example: str) -> str:
        """Le compte de cet espace qui correspond au compte d'exemple `example`."""
        return f"{self.staff}{example[-4:]}"

    def guardian(self, number: int) -> str:
        return f"{self.guardians}{number:0{PHONE_LENGTH - len(self.guardians)}d}"

    @classmethod
    def block(cls, number: int) -> "DemoNumbers":
        """Bloc d'un espace créé depuis la console : +243 00 BB 0 xxxx pour le personnel,
        +243 00 BB 1 xxxx pour les tuteurs. De 40 à 99 : en dessous, les numéros de `make demo`."""
        if number not in BLOCKS:
            raise ValueError(f"Bloc de numéros de démonstration hors de {BLOCKS} : {number}")
        return cls(f"+24300{number}0", f"+24300{number}1")


BLOCKS = range(40, 100)
# Numéros historiques de `make demo` (écrits dans les documents et les parcours) : personnel des
# deux écoles en +243 000 00x xxx, tuteurs en +243 002… et +243 003….
MAKE_DEMO_NUMBERS = {
    "itig": DemoNumbers("+24300000", "+2430020"),
    "volcans": DemoNumbers("+24300000", "+2430030"),
}


@dataclass(frozen=True)
class DemoSpace:
    """Un espace de démonstration à remplir : son école, le profil des données d'exemple à y
    écrire, ses numéros et le mot de passe de ses comptes."""

    school: School
    profile: str
    numbers: DemoNumbers
    password: str
    # Développement seulement : clé commune de double authentification (`accounts/demo.py`).
    shared_totp_key: bool = False
    # `make demo` seulement : logo public de l'école d'exemple (`DEMO_LOGOS`). Un espace créé
    # depuis la console porte le nom que lui donne le super-admin : pas le logo d'une autre.
    with_logo: bool = False


def _make_demo_schools() -> dict[str, dict]:
    today = timezone.localdate()
    return {
        "itig": {
            "name": "ITIG Don Bosco Goma (démo)",
            "official_name": "Institut Technique Industriel de Goma — ITIG Don Bosco (démo)",
            "status": School.Status.TRIAL,
            "plan": "Essai",
            "trial_ends_on": today + timedelta(days=90),
            "paid_until": None,
        },
        "volcans": {
            "name": "Complexe scolaire Les Volcans (fictif)",
            "official_name": "Complexe scolaire Les Volcans (fictif)",
            "status": School.Status.ACTIVE,
            "plan": "Standard",
            "trial_ends_on": None,
            "paid_until": today + timedelta(days=60),
        },
    }


# Couleur et réglages du reçu (M5) de chaque profil.
DEMO_LOOKS = {
    "itig": {
        # Décision Q8 : couleur de l'ITIG de démonstration.
        "primary_color": "#003C6C",
        # En-tête et mention fictifs, thermique 80 mm.
        "receipt": {
            "printer": "thermal_80",
            "sheet_size": "a6",
            "copies": 1,
            "header": "Institut Technique Industriel\nGoma · Nord-Kivu\n+243 000 000 000",
            "footer": "Conservez ce reçu. Aucun remboursement sans reçu.",
        },
    },
    "volcans": {
        "primary_color": "#7A3E00",
        # Imprimante ordinaire : reçus A6, avec une souche pour l'école.
        "receipt": {
            "printer": "sheet",
            "sheet_size": "a6",
            "copies": 2,
            "header": "Quartier Himbi, Goma\nvolcans@example.org",
            "footer": "Merci de payer à temps.",
        },
    },
}


def create_demo_schools(*, password: str, shared_totp_key: bool) -> list[DemoSpace]:
    """Les deux espaces de `make demo`, créés ou remis comme au départ (nom, abonnement, pas
    suspendus). De démonstration, y compris dans une base d'avant la 4.17 où ils étaient réels."""
    spaces = []
    for code, fields in _make_demo_schools().items():
        school, _created = School.objects.update_or_create(
            code=code,
            defaults={
                **fields,
                "environment": School.Environment.DEMO,
                "setup_completed_at": timezone.now(),
            },
        )
        numbers = MAKE_DEMO_NUMBERS[code]
        spaces.append(DemoSpace(school, code, numbers, password, shared_totp_key, with_logo=True))
    return spaces


def create_demo_look(spaces: list[DemoSpace]) -> None:
    """Couleur, réglages du reçu et logo du profil, remis comme au départ ; pas de logo noir et
    blanc."""
    for space in spaces:
        school, look = space.school, DEMO_LOOKS[space.profile]
        for logo in (school.logo, school.logo_monochrome):
            if logo:
                logo.delete(save=False)
        school.primary_color = look["primary_color"]
        school.settings = {"receipt": look["receipt"]}
        school.logo, school.logo_monochrome = "", ""
        school.save()
        logo = DEMO_LOGOS.get(space.profile) if space.with_logo else None
        if logo is not None and logo.exists():
            with logo.open("rb") as file:
                school.logo.save(logo.name, File(file))


# Organisation scolaire (C1-C3) : structure publique de l'ITIG (`fiche-itig.md`), sections
# inventées en attendant ses classes réelles (I1) ; Volcans, plus petite. Écrite directement dans
# les modèles : `make demo` n'écrit rien dans le journal d'audit.

YEAR = ("2026-2027", date(2026, 9, 1), date(2027, 7, 2))
# Dates des maquettes (I3 en attendant le calendrier de l'ITIG) : semestre, puis ses périodes.
ITIG_TERMS = [
    (
        (date(2026, 9, 7), date(2026, 12, 23)),
        [
            (date(2026, 9, 7), date(2026, 11, 7)),
            (date(2026, 11, 9), date(2026, 12, 12)),
            (date(2026, 12, 14), date(2026, 12, 23)),
        ],
    ),
    (
        (date(2027, 1, 11), date(2027, 6, 25)),
        [
            (date(2027, 1, 11), date(2027, 3, 13)),
            (date(2027, 3, 15), date(2027, 6, 5)),
            (date(2027, 6, 7), date(2027, 6, 25)),
        ],
    ),
]
# L'enseignant de démonstration, titulaire d'une classe (compte d'exemple, `accounts/demo.py`).
HOMEROOM_TEACHER_PHONE = "+243000001008"


@dataclass(frozen=True)
class DemoOrganisation:
    matricule_format: str
    levels: list[tuple[str, str]]
    tracks: list[tuple[str, str]]
    # (niveau, code de l'option ou "", sections, capacité)
    classes: list[tuple[str, str, str, int]]
    homeroom_class: tuple[str, str, str]
    term_dates: list | None = None


def _itig_classes() -> list[tuple[str, str, str, int]]:
    classes = [("7e EB", "", "ABC", 45), ("8e EB", "", "ABC", 45)]
    for code in ("ELEC", "ELO", "MG", "MA"):
        for level in ("1re", "2e", "3e", "4e"):
            sections = "AB" if (code, level) == ("ELEC", "1re") else "A"
            classes.append((level, code, sections, 45 if code == "ELEC" else 40))
    return classes


DEMO_ORGANISATIONS = {
    "itig": DemoOrganisation(
        matricule_format="ITIG-{AAAA}-{0000}",
        levels=[
            ("7e EB", Level.Cycle.BASIC),
            ("8e EB", Level.Cycle.BASIC),
            *[(name, Level.Cycle.SECONDARY_TECHNICAL) for name in ("1re", "2e", "3e", "4e")],
        ],
        tracks=[
            ("Électricité", "ELEC"),
            ("Électronique", "ELO"),
            ("Mécanique générale", "MG"),
            ("Mécanique automobile", "MA"),
        ],
        classes=_itig_classes(),
        homeroom_class=("3e", "ELEC", "A"),
        term_dates=ITIG_TERMS,
    ),
    # Dates du découpage laissées vides : l'école les saisit (« Modifier les dates »).
    "volcans": DemoOrganisation(
        matricule_format="LV/{AA}/{0000}",
        levels=[
            ("7e EB", Level.Cycle.BASIC),
            ("8e EB", Level.Cycle.BASIC),
            ("1re", Level.Cycle.SECONDARY_GENERAL),
            ("2e", Level.Cycle.SECONDARY_GENERAL),
        ],
        tracks=[("Scientifique", "SC"), ("Pédagogie générale", "PG")],
        classes=[
            ("7e EB", "", "A", 40),
            ("8e EB", "", "A", 40),
            ("1re", "SC", "A", 35),
            ("2e", "PG", "A", 35),
        ],
        homeroom_class=("7e EB", "", "A"),
    ),
}


def _demo_terms(year: AcademicYear, dates: list | None) -> None:
    """Découpage du modèle secondaire, avec les dates de démonstration."""
    year.terms.all().delete()
    order = 0
    for index, group in enumerate(template_terms(YearTemplate.SECONDARY)):
        span, children = dates[index] if dates else ((None, None), [(None, None)] * 3)
        parent = Term.objects.create(
            academic_year=year,
            kind=group.kind,
            order=order,
            starts_on=span[0],
            ends_on=span[1],
        )
        order += 1
        for child, (starts_on, ends_on) in zip(group.children, children, strict=True):
            Term.objects.create(
                academic_year=year,
                kind=child.kind,
                parent=parent,
                order=order,
                starts_on=starts_on,
                ends_on=ends_on,
            )
            order += 1


def create_demo_organisation(spaces: list[DemoSpace]) -> None:
    """Crée ou remet à jour l'année 2026-2027 (en cours), son découpage, les niveaux, options et
    classes de démonstration, et le format du matricule. Ce que l'utilisateur a ajouté en
    essayant l'application n'est pas effacé."""
    for space in spaces:
        school, demo = space.school, DEMO_ORGANISATIONS[space.profile]
        teacher = User.objects.get(phone=space.numbers.of(HOMEROOM_TEACHER_PHONE))
        school.matricule_format = demo.matricule_format
        school.save(update_fields=["matricule_format", "updated_at"])
        with use_school(school):
            name, starts_on, ends_on = YEAR
            AcademicYear.objects.exclude(name=name).update(is_current=False)
            year, _created = AcademicYear.objects.update_or_create(
                name=name,
                defaults={"starts_on": starts_on, "ends_on": ends_on, "is_current": True},
            )
            _demo_terms(year, demo.term_dates)
            levels = {}
            for order, (level_name, cycle) in enumerate(demo.levels):
                levels[level_name], _created = Level.objects.update_or_create(
                    name=level_name, defaults={"cycle": cycle, "order": order}
                )
            tracks = {"": None}
            for track_name, track_code in demo.tracks:
                tracks[track_code], _created = Track.objects.update_or_create(
                    code=track_code, defaults={"name": track_name}
                )
            for level_name, track_code, sections, capacity in demo.classes:
                for section in sections:
                    ClassGroup.objects.update_or_create(
                        academic_year=year,
                        level=levels[level_name],
                        track=tracks[track_code],
                        section=section,
                        defaults={
                            "capacity": capacity,
                            "homeroom_teacher": (
                                teacher
                                if (level_name, track_code, section) == demo.homeroom_class
                                else None
                            ),
                        },
                    )
