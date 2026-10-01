"""Seuils d'alerte au directeur (`School.settings["alerts"]`, M5, 4.2) : écart de caisse par
devise au-delà duquel une clôture est signalée, nombre d'annulations demandées par un caissier
dans une journée au-delà duquel il est signalé, heure à laquelle une caisse encore ouverte est
signalée. Choisis par l'école, jamais dans le code ; lus par le tableau de bord (G3).
"""

from datetime import time

from apps.core.money import Currency

# 10,00 $ et 20 000 FC (montants en plus petite unité : centimes, francs).
DEFAULT_DIFFERENCES = {Currency.USD.value: 1000, Currency.CDF.value: 20000}
DEFAULTS = {
    "difference_minor": DEFAULT_DIFFERENCES,
    "cancellations_per_day": 3,
    "closing_time": "18:00",
}


def alert_settings(settings: dict) -> dict:
    """Seuils d'après `School.settings`, valeurs par défaut comprises (chaque devise aussi)."""
    saved = (settings or {}).get("alerts", {})
    differences = {**DEFAULT_DIFFERENCES, **saved.get("difference_minor", {})}
    return {**DEFAULTS, **saved, "difference_minor": differences}


def closing_time(settings: dict) -> time:
    return time.fromisoformat(alert_settings(settings)["closing_time"])


def journal_fields(settings: dict) -> dict:
    """Seuils à plat pour le journal de l'école (`alert_difference_usd`…)."""
    alerts = alert_settings(settings)
    return {
        **{
            f"alert_difference_{currency.lower()}": amount
            for currency, amount in alerts["difference_minor"].items()
        },
        "alert_cancellations_per_day": alerts["cancellations_per_day"],
        "alert_closing_time": alerts["closing_time"],
    }
