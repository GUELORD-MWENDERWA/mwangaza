"""Espaces de démonstration (`docs/07-a-fournir.md` § 4, `03` § 4 bis) : ce qu'est un espace à
remplir (`DemoSpace`), les deux écoles de `make demo` et leur organisation.

L'ITIG n'est que l'école d'exemple : ce qui la décrit vient d'ici, jamais du code de l'application.
Les données d'exemple sont rangées par **profil** (`itig` : grande école technique, ≈ 800 élèves ;
`volcans` : petite, ≈ 150), pas par code d'école : la console en remplit d'autres espaces (4.17.2).
"""

import io
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.academics.models import Evaluation, GradeSheet
from apps.accounts.models import User
from apps.accounts.modules import ALL_MODULES
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
            "name": "ITIG DON BOSCO",
            "official_name": "INSTITUT TECHNIQUE INDUSTRIEL DE GOMA - ITIG DON BOSCO",
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
            "sheet_size": "half",
            "header": "Institut Technique Industriel\nGoma · Nord-Kivu\n+243 000 000 000",
            "footer": "Conservez ce reçu. Aucun remboursement sans reçu.",
        },
    },
    "volcans": {
        "primary_color": "#7A3E00",
        # Imprimante ordinaire : reçus sur un tiers de feuille A4.
        "receipt": {
            "printer": "sheet",
            "sheet_size": "third",
            "header": "Quartier Himbi, Goma\nvolcans@example.org",
            "footer": "Merci de payer à temps.",
        },
        # Saisie des points sans devoirs (8.4.0) : seulement le total de la période.
        "grading": {"entry": "totals"},
    },
}


def make_demo_refusal() -> str | None:
    """Pourquoi `make demo` ne doit pas tourner sur cette plateforme, ou `None`. La commande remet
    à zéro l'identité de la plateforme, le super-admin fictif et ses deux espaces : jamais là où
    un espace réel existe, ni par-dessus un espace d'un autre type (`03` § 4 bis)."""
    if School.objects.filter(environment=School.Environment.LIVE).exists():
        return "Cette plateforme a un espace réel."
    taken = (
        School.objects.filter(code__in=MAKE_DEMO_NUMBERS)
        .exclude(environment=School.Environment.DEMO)
        .values_list("code", flat=True)
    )
    if taken:
        codes = ", ".join(sorted(taken))
        return f"Code pris par un espace qui n'est pas de démonstration : {codes}."
    return None


def create_demo_schools(*, password: str, shared_totp_key: bool) -> list[DemoSpace]:
    """Les deux espaces de `make demo`, créés ou remis comme au départ (nom, abonnement, pas
    suspendus). Cherchés par code **et** type : le type d'un espace existant n'est jamais écrit
    (code pris par un autre type : `make_demo_refusal`, et la base refuse le doublon)."""
    spaces = []
    for code, fields in _make_demo_schools().items():
        school, _created = School.objects.update_or_create(
            code=code,
            environment=School.Environment.DEMO,
            defaults={**fields, "setup_completed_at": timezone.now(), "modules": ALL_MODULES},
        )
        numbers = MAKE_DEMO_NUMBERS[code]
        spaces.append(DemoSpace(school, code, numbers, password, shared_totp_key, with_logo=True))
    return spaces


def demo_signature(seed: int, *, stamp: bool = False) -> ContentFile:
    """Image fictive (PNG détouré) : un paraphe, ou un cachet rond (jamais l'image d'une école)."""
    image = Image.new("RGBA", (400, 400 if stamp else 160), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if stamp:
        ink = (30, 60, 140, 200)
        draw.ellipse((10, 10, 390, 390), outline=ink, width=8)
        draw.ellipse((70, 70, 330, 330), outline=ink, width=4)
        draw.line([(120, 200), (280, 200)], fill=ink, width=6)
    else:
        ink = (20, 30, 90, 255)
        points = [(10 + i * 38, 90 + ((i * 53 + seed * 29) % 70) - 35) for i in range(10)]
        draw.line(points, fill=ink, width=5, joint="curve")
    return ContentFile(_png(image), name="demo.png")


def _png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def create_demo_look(spaces: list[DemoSpace]) -> None:
    """Couleur, réglages du reçu et logo du profil, remis comme au départ ; pas de logo noir et
    blanc."""
    for space in spaces:
        school, look = space.school, DEMO_LOOKS[space.profile]
        for logo in (school.logo, school.logo_monochrome):
            if logo:
                logo.delete(save=False)
        school.primary_color = look["primary_color"]
        school.settings = {
            "receipt": look["receipt"],
            **({"grading": look["grading"]} if "grading" in look else {}),
        }
        school.logo, school.logo_monochrome = "", ""
        for image in (school.stamp, school.head_signature):
            if image:
                image.delete(save=False)
        school.head_name, school.head_title = "Mukendi Kabasele", "Préfet des études"
        school.epst_code, school.regime = "9000001", School.Regime.CONVENTION
        school.province, school.city, school.commune = "Nord-Kivu", "Goma", "Karisimbi"
        school.save()
        school.stamp.save("stamp.png", demo_signature(0, stamp=True))
        school.head_signature.save("signature.png", demo_signature(1))
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
    classes = [("7EB", "", "ABC", 45), ("8EB", "", "ABC", 45)]
    for code in ("ELEC", "ELO", "MG", "MA"):
        for level in ("1HT", "2HT", "3HT", "4HT"):
            sections = "AB" if (code, level) == ("ELEC", "1HT") else "A"
            classes.append((level, code, sections, 45 if code == "ELEC" else 40))
    return classes


# Titre du bulletin de chaque niveau de l'ITIG, tel que l'école l'écrit (HT : humanité technique).
REPORT_TITLES = {
    "7EB": "7ème Éducation de Base",
    "8EB": "8ème Éducation de Base",
    "1HT": "1ère Humanité Technique",
    "2HT": "2ème Humanité Technique",
    "3HT": "3ème Humanité Technique",
    "4HT": "4ème Humanité Technique",
}

DEMO_ORGANISATIONS = {
    "itig": DemoOrganisation(
        matricule_format="ITIG-{AAAA}-{0000}",
        levels=[
            ("7EB", Level.Cycle.BASIC),
            ("8EB", Level.Cycle.BASIC),
            *[(name, Level.Cycle.SECONDARY_TECHNICAL) for name in ("1HT", "2HT", "3HT", "4HT")],
        ],
        tracks=[
            ("Électricité", "ELEC"),
            ("Électronique", "ELO"),
            ("Mécanique générale", "MG"),
            ("Mécanique automobile", "MA"),
        ],
        classes=_itig_classes(),
        homeroom_class=("3HT", "ELEC", "A"),
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
    """Découpage du modèle secondaire, avec les dates de démonstration. Mis à jour en place,
    chaque élément gardé par sa place : les notes saisies (8.2.1) restent sur leur période ; un
    élément en trop part avec ses évaluations."""
    existing = {term.order: term for term in year.terms.all()}
    wanted = []
    order = 0
    for index, group in enumerate(template_terms(YearTemplate.SECONDARY)):
        span, children = dates[index] if dates else ((None, None), [(None, None)] * 3)
        wanted.append((order, group.kind, None, span))
        parent_order = order
        order += 1
        for child, child_span in zip(group.children, children, strict=True):
            wanted.append((order, child.kind, parent_order, child_span))
            order += 1
    extra = [term.pk for place, term in existing.items() if place >= order]
    GradeSheet.objects.filter(term_id__in=extra).delete()
    Evaluation.objects.filter(term_id__in=extra).delete()
    Term.objects.filter(pk__in=extra).delete()
    terms: dict[int, Term] = {}
    for place, kind, parent_order, (starts_on, ends_on) in wanted:
        term = existing.get(place) or Term(academic_year=year, order=place)
        term.kind, term.name, term.starts_on, term.ends_on = kind, "", starts_on, ends_on
        term.parent = terms[parent_order] if parent_order is not None else None
        term.save()
        terms[place] = term
    # Une période devenue semestre (découpage changé en essayant) ne garde pas de notes.
    gradable = [Term.Kind.PERIOD, Term.Kind.EXAM]
    stale = Evaluation.objects.filter(term__academic_year=year).exclude(term__kind__in=gradable)
    GradeSheet.objects.filter(term__academic_year=year).exclude(term__kind__in=gradable).delete()
    stale.delete()


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
                    name=level_name,
                    defaults={
                        "cycle": cycle,
                        "report_title": REPORT_TITLES.get(level_name, ""),
                        "order": order,
                        # La dernière année du modèle finit par l'Examen d'État (8.3.3).
                        "has_state_exam": order == len(demo.levels) - 1,
                    },
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
