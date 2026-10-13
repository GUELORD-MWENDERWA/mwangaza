# Tâche 4.25 — Santé de la plateforme (console)

Existant (5.2) : `core/health.py` (base, Redis, travailleurs, disque) dans `console.dashboard()`.

- `health.py` : contrôles `memory` (MemAvailable % libre) et `swap` (% utilisé) lus dans `/proc/meminfo`.
- Planificateur : `tasks.tick` écrit son heure dans Redis (`mwangaza:scheduler:tick`, 1 écriture/15 min,
  en mémoire, rien en base) ; taille de la file = `LLEN celery`.
- Sauvegardes : `sauvegarde.sh` écrit l'heure de la dernière sauvegarde et de la dernière copie B2
  dans Redis (`mwangaza:backup:done|copied`, volume persistant) via `redis-cli` ; 0 dépendance.
- Dernière synchronisation par école : `max(Device.last_seen_at)` (appareils non révoqués), écoles
  réelles ouvertes, 10 plus anciennes d'abord — une requête.
- Un bloc `platform` ajouté au tableau de bord (même endpoint, super-admin) ; carte « Plateforme »
  dans le tableau de bord de la console.
- Retiré : graphes, historique, alertes (Sentry, Healthchecks, UptimeRobot, Lightsail le font) ;
  `/api/health/` inchangé.
- Tests : seuils mémoire/swap/âge sauvegarde, pas de fuite entre écoles (écoles d'essai exclues),
  accès refusé hors super-admin (déjà couvert pour le tableau de bord).
- Risque : Redis redémarré sans sauvegarde → « inconnue » (jamais faux « bon »).
