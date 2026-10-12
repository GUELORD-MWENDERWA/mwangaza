"""Relances aux parents (`School.settings["reminders"]`, 5.6.2) : notifications de paiement que
le planificateur envoie chaque matin aux familles qui ont un compte du portail
(`notifications/scheduled.py`) — échéance proche, tant de jours avant ; retard, rappelé tous les
tant de jours. Choisies par l'école, jamais dans le code ; désactivées tant qu'elle ne les a pas
activées (ses paiements d'avant doivent d'abord être saisis, sinon de faux retards partiraient).
"""

DEFAULTS = {"enabled": False, "days_before": 3, "overdue_every_days": 7}


def reminder_settings(settings: dict) -> dict:
    """Réglages d'après `School.settings`, valeurs par défaut comprises."""
    return {**DEFAULTS, **(settings or {}).get("reminders", {})}


def journal_fields(settings: dict) -> dict:
    """Réglages à plat pour le journal de l'école (`reminder_enabled`…)."""
    return {f"reminder_{name}": value for name, value in reminder_settings(settings).items()}
