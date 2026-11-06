"""Réglages des cartes et des présences (lot 10) : `School.settings["card"]` (modèle de carte) et
`School.settings["attendance"]` (heure limite d'arrivée, heure où les parents des absents sont
prévenus, seuil d'alerte des absences non justifiées, 0 = aucune alerte). Jamais dans le code :
chaque école les règle dans ses paramètres.

Carte : `color` vide = bleu de la plateforme ; `back_text` vide = texte par défaut ;
`valid_until` vide = dernier jour de l'année scolaire en cours ; `printed_fields` = champs
facultatifs imprimés (téléphone du responsable et adresse décochés : une carte perdue est lue
par n'importe qui) ; `authorities_text` vide = formule habituelle ; `require_photo` = pas de
carte sans photo officielle.
"""

from datetime import time

# Champs facultatifs de la carte, dans l'ordre d'impression.
CARD_FIELDS = (
    "birth",
    "sex",
    "nationality",
    "national_id",
    "guardian_phone",
    "address",
    "authorities",
)
CARD_DEFAULTS = {
    "color": "",
    "back_text": "",
    "valid_until": None,
    "printed_fields": ["birth", "sex", "authorities"],
    "authorities_text": "",
    "require_photo": True,
}
ATTENDANCE_DEFAULTS = {"late_after": "07:45", "notify_at": "09:00", "alert_after": 3}


def card_settings(settings: dict) -> dict:
    return {**CARD_DEFAULTS, **(settings or {}).get("card", {})}


def attendance_settings(settings: dict) -> dict:
    return {**ATTENDANCE_DEFAULTS, **(settings or {}).get("attendance", {})}


def late_after(settings: dict) -> time:
    """Heure au-delà de laquelle un passage à l'entrée est un retard."""
    return time.fromisoformat(attendance_settings(settings)["late_after"])


def notify_at(settings: dict) -> time:
    """Heure où partent les notifications d'absence du jour (toujours après `late_after`)."""
    return time.fromisoformat(attendance_settings(settings)["notify_at"])


def journal_fields(settings: dict) -> dict:
    """Réglages à plat pour le journal de l'école (`card_color`, `attendance_late_after`)."""
    return {
        **{f"card_{name}": value for name, value in card_settings(settings).items()},
        **{f"attendance_{name}": value for name, value in attendance_settings(settings).items()},
    }
