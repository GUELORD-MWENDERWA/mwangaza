"""Grilles de cours officielles qui pré-remplissent celle d'une classe (`01` § 8.6 : « programme
officiel pré-rempli quand disponible ») ; l'école ajuste ensuite. Sources et limites :
`docs/claude/recherches/2026-09-26-bulletins-rdc.md`. Ce sont des données nationales, pas celles
d'une école : les mêmes pour toutes.

Une grille : (nom, maximum par période, avec examen, heures par semaine ou None). Les formulaires
de bulletin ne donnent pas les heures ; le barème Électronique les donne.
"""

from dataclasses import dataclass

Row = tuple[str, int, bool, int | None]


@dataclass(frozen=True)
class OfficialGrid:
    key: str
    # Référence du document officiel, la même dans toutes les langues.
    reference: str
    courses: tuple[Row, ...]
    # Cours imprimés sur le formulaire mais barrés pour cette option : jamais notés.
    untaught: tuple[str, ...] = ()


def _same(maximum: int, names: tuple[str, ...], *, exam: bool = True) -> tuple[Row, ...]:
    return tuple((name, maximum, exam, None) for name in names)


_FIRST_THREE = ("Religion", "Éducation civique et morale", "Éducation à la vie")

GRIDS = (
    # 7e et 8e de l'éducation de base (1re et 2e année secondaire sur le formulaire).
    OfficialGrid(
        "basic_education",
        "IGE/P.S/005",
        _same(
            20,
            (
                *_FIRST_THREE,
                "Informatique",
                "Anglais",
                "Dessin",
                "Éducation physique",
                "Musique",
            ),
        )
        + _same(30, ("Géographie", "Histoire", "Sciences", "Technologie"))
        + _same(60, ("Français", "Mathématique")),
    ),
    # Électricité, 3e et 4e année (1re et 2e des humanités).
    OfficialGrid(
        "electricity",
        "IGE/P.S/100",
        _same(10, _FIRST_THREE)
        + _same(
            20,
            (
                "Anglais",
                "Géographie / actualité",
                "Histoire",
                "Chimie",
                "Physique",
                "Mécanisme",
                "Instruments et méthodes de mesure",
                "Technologie mécanique",
                "Informatique",
            ),
        )
        + _same(
            40,
            (
                "Dessin électrique",
                "Dessin industriel",
                "Électricité générale",
                "Mécanique générale",
                "Technologie électrique",
            ),
        )
        + _same(50, ("Français", "Mathématique"))
        + _same(100, ("Atelier électrique", "Laboratoire électrique"), exam=False),
    ),
    # Mécanique générale, 3e et 4e année (1re et 2e des humanités).
    OfficialGrid(
        "general_mechanics",
        "IGE/P.S/094",
        _same(10, _FIRST_THREE)
        + _same(
            20,
            (
                "Anglais",
                "Géographie / actualité",
                "Histoire",
                "Chimie",
                "Physique",
                "Électricité",
                "Informatique",
                "Métallurgie",
            ),
        )
        + _same(
            40,
            (
                "Dessin industriel",
                "Mécanique générale",
                "Résistance des matériaux",
                "Technologie mécanique",
            ),
        )
        + _same(50, ("Français", "Mathématique"))
        + _same(100, ("Pratique professionnelle",), exam=False),
    ),
    # Électronique, barème du programme national (EDIDEPS 2006, publié en 2009) : 41 heures et
    # 500 points par période. 3e et 4e année ; les 5e et 6e ne sont pas reprises (le total publié
    # de la 6e ne tombe pas juste).
    OfficialGrid(
        "electronics_1",
        "EDIDEPS 2009",
        (
            ("Anglais", 30, True, 2),
            ("Chimie", 20, True, 2),
            ("Éducation civique et politique", 40, True, 2),
            ("Éducation physique", 20, True, 1),
            ("Français", 60, True, 5),
            ("Géographie", 20, True, 1),
            ("Histoire", 20, True, 1),
            ("Mathématiques", 60, True, 6),
            ("Physique", 20, True, 2),
            ("Dessin industriel", 30, True, 2),
            ("Dessin et schémas électriques", 20, True, 2),
            ("Électricité générale", 40, True, 3),
            ("Électronique générale", 30, True, 3),
            ("Mécanique générale", 20, True, 2),
            ("Technologie électrique", 20, True, 2),
            ("Atelier électrique", 50, False, 5),
        ),
    ),
    OfficialGrid(
        "electronics_2",
        "EDIDEPS 2009",
        (
            ("Anglais", 30, True, 2),
            ("Chimie", 20, True, 1),
            ("Éducation civique et politique", 40, True, 2),
            ("Éducation physique", 20, True, 1),
            ("Français", 60, True, 5),
            ("H.G.A.", 20, True, 1),
            ("Mathématiques", 60, True, 6),
            ("Physique", 20, True, 1),
            ("Dessin et schémas électriques", 20, True, 2),
            ("Électricité générale", 40, True, 4),
            ("Électronique générale", 50, True, 5),
            ("Instruments, appareillage et méthode de mesure", 20, True, 1),
            ("Technologie électronique", 20, True, 2),
            ("Atelier électronique", 40, False, 4),
            ("Labo électronique", 40, False, 4),
        ),
    ),
)

# 3e année d'électronique industrielle (formulaire IGE/P.S/137, bulletin fourni le 2026-10-15) :
# tous les cours du formulaire ; ceux que l'option ne suit pas y sont barrés (tirets).
_ELECTRONICS_3_UNTAUGHT = (
    "Automate programmable",
    "Hyperfréquence",
    "Maintenance informatique",
    "Microprocesseur",
    "Physique",
    "Régulation",
)
GRIDS += (
    OfficialGrid(
        "electronics_3",
        "IGE/P.S/137",
        (
            *_same(10, ("Religion", "Éducation à la vie", "Éducation civique et morale")),
            *_same(
                20,
                (
                    "Actualités",
                    "Anglais",
                    "Automate programmable",
                    "Circuits logiques",
                    "Hyperfréquence",
                    "Informatique industrielle",
                    "Instruments et mesures",
                    "Maintenance informatique",
                    "Microprocesseur",
                    "Physique",
                    "Régulation",
                    "Schéma électronique",
                    "Technologie électronique",
                ),
            ),
            *_same(40, ("Électricité", "Électronique", "Radio électronique")),
            *_same(50, ("Français", "Mathématiques")),
            *_same(100, ("Atelier électronique", "Labo électronique"), exam=False),
        ),
        untaught=_ELECTRONICS_3_UNTAUGHT,
    ),
)

BY_KEY = {grid.key: grid for grid in GRIDS}

# Catégorie de chaque cours pour les règles de délibération (NB.4) : le français et les
# mathématiques sont les cours principaux, un cours sans examen (atelier, laboratoire, pratique
# professionnelle) est pratique, les branches d'option sont celles de la spécialité ; le reste
# est général. L'école corrige dans sa grille.
MAIN_COURSES = {"Français", "Mathématique", "Mathématiques"}
OPTION_COURSES = {
    "electricity": {
        "Dessin électrique",
        "Dessin industriel",
        "Électricité générale",
        "Mécanique générale",
        "Technologie électrique",
    },
    "general_mechanics": {
        "Dessin industriel",
        "Mécanique générale",
        "Résistance des matériaux",
        "Technologie mécanique",
    },
    "electronics_1": {"Électricité générale"},
    "electronics_2": {"Électricité générale", "Électronique générale"},
    "electronics_3": {"Électricité", "Électronique", "Radio électronique"},
}


def category_of(grid: OfficialGrid, name: str, has_exam: bool) -> str:
    if name in MAIN_COURSES:
        return "main"
    if not has_exam:
        return "practical"
    return "option" if name in OPTION_COURSES.get(grid.key, ()) else "general"
