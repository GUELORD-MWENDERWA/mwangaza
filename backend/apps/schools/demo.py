"""Écoles fictives de `make demo` (`docs/07-a-fournir.md` § 4).

L'ITIG n'est que l'école d'exemple : ce qui la décrit vient d'ici, jamais du code de l'application.
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


def _demo_schools() -> dict[str, dict]:
    today = timezone.localdate()
    return {
        "itig": {
            "name": "ITIG Don Bosco Goma (démo)",
            "official_name": "Institut Technique Industriel de Goma — ITIG Don Bosco (démo)",
            # Décision Q8 : couleur de l'ITIG de démonstration.
            "primary_color": "#003C6C",
            "status": School.Status.TRIAL,
            "plan": "Essai",
            "trial_ends_on": today + timedelta(days=90),
            "paid_until": None,
            # Reçus (M5) : en-tête et mention fictifs, thermique 80 mm.
            "settings": {
                "receipt": {
                    "printer": "thermal_80",
                    "sheet_size": "a6",
                    "copies": 1,
                    "header": "Institut Technique Industriel\nGoma · Nord-Kivu\n+243 000 000 000",
                    "footer": "Conservez ce reçu. Aucun remboursement sans reçu.",
                }
            },
        },
        "volcans": {
            "name": "Complexe scolaire Les Volcans (fictif)",
            "official_name": "Complexe scolaire Les Volcans (fictif)",
            "primary_color": "#7A3E00",
            "status": School.Status.ACTIVE,
            "plan": "Standard",
            "trial_ends_on": None,
            "paid_until": today + timedelta(days=60),
            # Imprimante ordinaire : reçus A6, avec une souche pour l'école.
            "settings": {
                "receipt": {
                    "printer": "sheet",
                    "sheet_size": "a6",
                    "copies": 2,
                    "header": "Quartier Himbi, Goma\nvolcans@example.org",
                    "footer": "Merci de payer à temps.",
                }
            },
        },
    }


def create_demo_schools() -> dict[str, School]:
    """Crée les écoles, ou les remet comme au départ (nom, couleur, abonnement, pas suspendues,
    réglages du reçu, logo de démonstration, pas de logo noir et blanc)."""
    schools = {}
    for code, fields in _demo_schools().items():
        existing = School.objects.filter(code=code).first()
        for logo in (existing.logo, existing.logo_monochrome) if existing else ():
            if logo:
                logo.delete(save=False)
        school, _created = School.objects.update_or_create(
            code=code, defaults={**fields, "logo": "", "logo_monochrome": ""}
        )
        logo = DEMO_LOGOS.get(code)
        if logo is not None and logo.exists():
            with logo.open("rb") as file:
                school.logo.save(logo.name, File(file))
        schools[code] = school
    return schools


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
# L'enseignant de démonstration des deux écoles (`accounts/demo.py`).
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


def create_demo_organisation(schools: dict[str, School]) -> None:
    """Crée ou remet à jour l'année 2026-2027 (en cours), son découpage, les niveaux, options et
    classes de démonstration, et le format du matricule. Ce que l'utilisateur a ajouté en
    essayant l'application n'est pas effacé."""
    teacher = User.objects.get(phone=HOMEROOM_TEACHER_PHONE)
    for code, demo in DEMO_ORGANISATIONS.items():
        school = schools[code]
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
