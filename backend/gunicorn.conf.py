"""Réglages de Gunicorn (PERF.5a), lus tout seuls depuis le dossier de l'application.

`--preload` charge Django une fois dans le processus principal : les travailleurs le partagent
(moins de mémoire, démarrage plus rapide). Aucune connexion ne doit pourtant survivre au
`fork` : celle que le chargement aurait pu ouvrir est fermée avant de créer les travailleurs.

Puis (PERF.8) les objets chargés sortent du ramasse-miettes (`gc.freeze`) : il ne les touche plus,
et ils restent partagés avec les travailleurs au lieu d'être recopiés peu à peu dans chacun."""

import gc


def when_ready(server) -> None:
    from django.db import connections

    connections.close_all()
    gc.collect()
    gc.freeze()
