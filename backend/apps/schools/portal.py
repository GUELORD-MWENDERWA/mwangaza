"""Ce que l'école montre aux parents dans le portail (`School.settings["portal"]`, 5.7) : le
téléphone du titulaire de la classe de l'enfant, seulement si elle l'a choisi (c'est le numéro
personnel d'un enseignant ; son nom, lui, est toujours montré). Jamais dans le code.
"""

DEFAULTS = {"teacher_phone": False}


def portal_settings(settings: dict) -> dict:
    """Réglages d'après `School.settings`, valeurs par défaut comprises."""
    return {**DEFAULTS, **(settings or {}).get("portal", {})}


def journal_fields(settings: dict) -> dict:
    """Réglages à plat pour le journal de l'école (`portal_teacher_phone`)."""
    return {f"portal_{name}": value for name, value in portal_settings(settings).items()}
