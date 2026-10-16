"""Règles de réussite de l'école (`School.settings["pass_rules"]`, 8.4.1) : à quel pourcentage de
l'année un élève réussit et un cours est échoué, quels cours échoués ouvrent un examen de
repêchage, et combien de cours échoués au repêchage font échouer l'élève. Valeurs de départ
proposées (`07` I16, à confirmer par l'école) ; chaque école les règle. Jamais dans le code.
"""

BAND = "band"
ANY_FAILED = "any_failed"
MODES = (BAND, ANY_FAILED)
MODE_CHOICES = [(mode, mode) for mode in MODES]
DEFAULTS = {
    "pass_percent": 50,
    "course_pass_percent": 50,
    "resit_mode": BAND,
    "resit_floor_percent": 45,
    "resit_failures_to_fail": 2,
    # Cours échoués au plus qui peuvent être repêchés ; au-delà, l'échec est proposé.
    "max_resit_courses": 4,
}
FIELDS = tuple(DEFAULTS)


def pass_rules_settings(settings: dict) -> dict:
    """Règles d'après `School.settings`, valeurs par défaut comprises."""
    return {**DEFAULTS, **(settings or {}).get("pass_rules", {})}


def class_rules(settings: dict, level_rules: dict | None) -> dict:
    """Règles d'une classe : celles de l'école, que le niveau de la classe (7e, 3e…) peut
    remplacer champ par champ (`Level.pass_rules`, vide : celles de l'école)."""
    return {**pass_rules_settings(settings), **(level_rules or {})}


def journal_fields(settings: dict) -> dict:
    """Règles à plat pour le journal de l'école (`pass_rules_resit_mode`…)."""
    return {f"pass_rules_{name}": value for name, value in pass_rules_settings(settings).items()}
