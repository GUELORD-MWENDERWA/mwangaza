"""Ce que l'école montre aux parents dans le portail (`School.settings["portal"]`, 5.7) : le
téléphone du titulaire de la classe de l'enfant, seulement si elle l'a choisi (c'est le numéro
personnel d'un enseignant ; son nom, lui, est toujours montré). Jamais dans le code.
"""

# `report_requires_payment` (8.4.6) : le PDF du bulletin est retenu tant qu'un frais échu de la
# famille reste impayé, sauf dérogation du préfet.
DEFAULTS = {"teacher_phone": False, "report_requires_payment": False}


def portal_settings(settings: dict) -> dict:
    """Réglages d'après `School.settings`, valeurs par défaut comprises."""
    return {**DEFAULTS, **(settings or {}).get("portal", {})}


def journal_fields(settings: dict) -> dict:
    """Réglages à plat pour le journal de l'école (`portal_teacher_phone`)."""
    return {f"portal_{name}": value for name, value in portal_settings(settings).items()}
