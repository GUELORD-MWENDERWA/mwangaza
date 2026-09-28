"""Réglages du reçu d'une école (`School.settings["receipt"]`, `docs/04-modele-de-donnees.md` § 1,
M5) : imprimante, taille du reçu sur une feuille A4, exemplaires, lignes d'en-tête et mention.
Choisis par l'école, jamais dans le code ; lus par le reçu imprimé dans le navigateur (3.2.2).
"""

# Thermique 58 ou 80 mm, ou imprimante ordinaire avec une feuille A4 (`sheet`).
PRINTERS = ("thermal_58", "thermal_80", "sheet")
# Sur une feuille A4 : A6 (4 par feuille), A5 (2), petit format ≈ 10 x 7 cm (8) à coller dans le
# cahier de l'élève ; toujours avec des traits de découpe.
SHEET_SIZES = ("a6", "a5", "small")
# 1 : pour l'élève ; 2 : pour l'élève et une souche pour l'école.
COPIES = (1, 2)
HEADER_MAX_LINES = 5

DEFAULTS = {"printer": "thermal_80", "sheet_size": "a6", "copies": 1, "header": "", "footer": ""}


def receipt_settings(settings: dict) -> dict:
    """Réglages du reçu d'après `School.settings`, valeurs par défaut comprises."""
    return {**DEFAULTS, **(settings or {}).get("receipt", {})}


def journal_fields(settings: dict) -> dict:
    """Réglages du reçu à plat pour le journal de l'école (`receipt_printer`…)."""
    return {f"receipt_{key}": value for key, value in receipt_settings(settings).items()}
