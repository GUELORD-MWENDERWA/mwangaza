"""Placement d'un cours dans l'horaire (EDT.1b, spec emploi du temps § 4) : séances, maximum par
jour, récréation. Fonctions pures, lues par la grille des cours, les contrôles et le calcul."""

from apps.academics.models import PRACTICAL

# Une séance tient dans une journée.
MAX_SESSION = 12


def parse_pattern(text: str) -> list[int] | None:
    """« 2+2+1 » → [2, 2, 1] ; vide → [] ; illisible → None."""
    text = text.replace(" ", "")
    if not text:
        return []
    parts = text.split("+")
    if not all(part.isdigit() for part in parts):
        return None
    values = [int(part) for part in parts]
    if any(value < 1 or value > MAX_SESSION for value in values):
        return None
    return values


# Un atelier se donne en longs blocs, aussi longs que l'école le veut (« 6 », « 4+3 »… dans ses
# séances, demandé le 2026-10-27), sans la règle de l'école qui limite un cours à 2 h par jour.
# Sans séances saisies : des blocs de 4 h au plus, proposés.
PRACTICAL_BLOCK = 4


def proposed(hours: int, *, practical: bool = False) -> list[int]:
    """Séances calculées quand l'école n'en donne pas : des blocs de 2 heures à partir de
    4 heures, sinon des heures seules ; un cours pratique (atelier), des blocs de 4 heures au
    plus, répartis à parts égales (7 h : 4 + 3 ; 9 h : 3 + 3 + 3)."""
    if practical and hours > 0:
        count = -(-hours // PRACTICAL_BLOCK)
        base, extra = divmod(hours, count)
        return [base + 1] * extra + [base] * (count - extra)
    if hours >= 4:
        return [2] * (hours // 2) + [1] * (hours % 2)
    return [1] * hours


def sessions(course) -> list[int]:
    hours = course.weekly_hours or 0
    pattern = parse_pattern(course.lesson_pattern) or []
    if pattern and sum(pattern) == hours:
        return pattern
    return proposed(hours, practical=course.category == PRACTICAL)


def spans_break(course) -> bool:
    """Vide = oui pour un cours pratique (atelier, laboratoire)."""
    if course.can_span_break is not None:
        return course.can_span_break
    return course.category == PRACTICAL


def max_per_day(course, school_max: int) -> int:
    """Heures du cours au plus par jour : celles du cours, sinon la règle de l'école, qui ne
    descend jamais sous la plus longue séance ; un cours pratique (atelier) n'a pas de limite
    par jour (ses séances peuvent se suivre), sauf celle du cours."""
    if course.max_per_day:
        return course.max_per_day
    if course.category == PRACTICAL:
        return max(course.weekly_hours or 0, 1)
    return max(school_max, *sessions(course), 0)
