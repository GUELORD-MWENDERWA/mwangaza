"""Réglages du reçu d'une école (`School.settings["receipt"]`, `docs/04-modele-de-donnees.md` § 1,
M5) : imprimante, hauteur de la feuille, lignes d'en-tête et mention. Un reçu par feuille, en un
seul exemplaire (DOC.2).
Choisis par l'école, jamais dans le code ; lus par le reçu imprimé dans le navigateur (3.2.2).
"""

# Thermique 58 ou 80 mm, ou imprimante ordinaire avec une feuille A4 (`sheet`).
PRINTERS = ("thermal_58", "thermal_80", "sheet")
# Imprimante ordinaire : une feuille de la largeur d'un A4 (21 cm) et de hauteur réduite, un reçu
# par feuille : demi A4 (21 x 14,8 cm) ou tiers d'A4 (21 x 9,9 cm).
SHEET_SIZES = ("half", "third")
HEADER_MAX_LINES = 5

DEFAULTS = {"printer": "thermal_80", "sheet_size": "half", "header": "", "footer": ""}


def receipt_settings(settings: dict) -> dict:
    """Réglages du reçu d'après `School.settings`, valeurs par défaut comprises."""
    saved = (settings or {}).get("receipt", {})
    return {**DEFAULTS, **{key: value for key, value in saved.items() if key in DEFAULTS}}


def journal_fields(settings: dict) -> dict:
    """Réglages du reçu à plat pour le journal de l'école (`receipt_printer`…)."""
    return {f"receipt_{key}": value for key, value in receipt_settings(settings).items()}
