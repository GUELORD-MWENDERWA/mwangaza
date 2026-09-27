"""Format du matricule de l'école (C3) : un texte avec des variables entre accolades.

- `{AAAA}` : année de début de l'année scolaire (2026) ; `{AA}` : ses deux derniers chiffres (26) ;
- `{0000}` : numéro de l'élève dans l'année, sur autant de chiffres que de zéros (3 à 6) ;
- `{OPT}` : code de l'option de la classe (`ELEC`) ; classe sans option : la variable disparaît
  avec un séparateur voisin (`ITIG-{OPT}-{AAAA}-{0000}` → `ITIG-2026-0001`).

Le numéro repart à 1 chaque année (`04` § 3) : le format doit donc contenir l'année, sinon deux
élèves de deux années auraient le même matricule. La génération (séquence par école et par
année) vient avec les inscriptions (2.1).
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

MAX_LENGTH = 60
YEAR_VARIABLES = frozenset({"AAAA", "AA"})
TRACK_VARIABLE = "OPT"
_VARIABLE = re.compile(r"\{([^{}]*)\}")
_NUMBER = re.compile(r"0{3,6}")
# Hors des variables : lettres sans accent, chiffres et séparateurs.
_LITERAL = re.compile(r"[A-Za-z0-9./_-]*")
_SEPARATORS = "-/._"
# Sans option : `{OPT}` et le séparateur qui le suit, sinon celui qui le précède.
_NO_TRACK = re.compile(rf"\{{OPT\}}[{re.escape(_SEPARATORS)}]|[{re.escape(_SEPARATORS)}]?\{{OPT\}}")


def default_format(school_code: str) -> str:
    """Format d'une nouvelle école : son code en majuscules, l'année, un numéro à 4 chiffres."""
    return f"{school_code.upper()}-{{AAAA}}-{{0000}}"


def validate_matricule_format(value: str) -> None:
    variables = _VARIABLE.findall(value)
    literal = _VARIABLE.sub("", value)
    if "{" in literal or "}" in literal:
        raise ValidationError(_("A brace is not closed."), code="matricule_braces")
    for name in variables:
        if not (_NUMBER.fullmatch(name) or name in YEAR_VARIABLES or name == TRACK_VARIABLE):
            raise ValidationError(
                _("Unknown variable {%(name)s}: use {AAAA}, {AA}, {0000} or {OPT}."),
                code="matricule_unknown_variable",
                params={"name": name},
            )
    if not _LITERAL.fullmatch(literal):
        raise ValidationError(
            _("Outside the variables, use only letters without accents, digits and - / . _"),
            code="matricule_characters",
        )
    numbers = [name for name in variables if _NUMBER.fullmatch(name)]
    if not numbers:
        raise ValidationError(_("Add the number, e.g. {0000}."), code="matricule_number_missing")
    if len(numbers) > 1:
        raise ValidationError(_("The number appears twice."), code="matricule_number_twice")
    if not YEAR_VARIABLES & set(variables):
        raise ValidationError(
            _("Add the year, {AAAA} or {AA}: numbers start again at 1 each year."),
            code="matricule_year_missing",
        )


def render(template: str, *, year: int, number: int, track_code: str = "") -> str:
    """Matricule d'un élève : `year` = année de début de l'année scolaire."""
    if not track_code:
        template = _NO_TRACK.sub("", template)

    def value(match: re.Match) -> str:
        name = match.group(1)
        if name == "AAAA":
            return f"{year:04d}"
        if name == "AA":
            return f"{year % 100:02d}"
        if name == TRACK_VARIABLE:
            return track_code
        return f"{number:0{len(name)}d}"

    return _VARIABLE.sub(value, template)
