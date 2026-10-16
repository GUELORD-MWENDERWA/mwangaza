"""Saisie des points de l'école (`School.settings["grading"]`, 8.4.0) : soit des devoirs détaillés
(interrogations, devoirs, travaux pratiques : une note chacun), soit seulement le total de la
période (ou des examens), reporté sur la fiche de cotation. Réglage de tout l'établissement ;
chaque cours peut y déroger (`Course.grade_entry`). Jamais dans le code.
"""

DETAILED = "detailed"
TOTALS = "totals"
ENTRIES = (DETAILED, TOTALS)
ENTRY_CHOICES = [(entry, entry) for entry in ENTRIES]
DEFAULTS = {"entry": DETAILED}


def grading_settings(settings: dict) -> dict:
    """Réglages d'après `School.settings`, valeurs par défaut comprises."""
    return {**DEFAULTS, **(settings or {}).get("grading", {})}


def journal_fields(settings: dict) -> dict:
    """Réglages à plat pour le journal de l'école (`grading_entry`)."""
    return {f"grading_{name}": value for name, value in grading_settings(settings).items()}
