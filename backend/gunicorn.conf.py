"""Réglages de Gunicorn (PERF.5a), lus tout seuls depuis le dossier de l'application.

`--preload` charge Django une fois dans le processus principal : les travailleurs le partagent
(moins de mémoire, démarrage plus rapide). Aucune connexion ne doit pourtant survivre au
`fork` : celle que le chargement aurait pu ouvrir est fermée avant de créer les travailleurs."""


def when_ready(server) -> None:
    from django.db import connections

    connections.close_all()
