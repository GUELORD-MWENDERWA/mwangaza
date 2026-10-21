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


def proposed(hours: int) -> list[int]:
    """Séances calculées quand l'école n'en donne pas : des blocs de 2 heures à partir de
    4 heures, sinon des heures seules."""
    if hours >= 4:
        return [2] * (hours // 2) + [1] * (hours % 2)
    return [1] * hours


def sessions(course) -> list[int]:
    hours = course.weekly_hours or 0
    pattern = parse_pattern(course.lesson_pattern) or []
    return pattern if sum(pattern) == hours and pattern else proposed(hours)


def spans_break(course) -> bool:
    """Vide = oui pour un cours pratique (atelier, laboratoire)."""
    if course.can_span_break is not None:
        return course.can_span_break
    return course.category == PRACTICAL


def max_per_day(course, school_max: int) -> int:
    """Heures du cours au plus par jour : celles du cours, sinon la règle de l'école, qui ne
    descend jamais sous la plus longue séance (un atelier de 6 h d'un bloc reste possible)."""
    if course.max_per_day:
        return course.max_per_day
    return max(school_max, *sessions(course), 0)
