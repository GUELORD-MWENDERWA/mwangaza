# Plan PERF.5b — Tableau de santé compréhensible et guide d'exploitation

**But** : un administrateur non développeur comprend la carte « Santé » de la console et sait quoi faire.
Chaque conteneur : nom français, une phrase de rôle, nom technique en petit ; couleurs 70 / 85 % ;
« arrêté pour manque de mémoire / redémarré à telle heure » ; « Ce que ça veut dire / Que faire » par indicateur ;
synchronisation vide expliquée ; `docs/exploitation.md` lié depuis l'écran.

**Hors périmètre** : alertes envoyées (SMS, e-mail), historique des mesures, images hors serveur (PERF.5c).

**Critères** : maquette `console/tableau-de-bord` à jour ; carte lisible à 390 et 1440 px ; nom de service
normalisé (`mwangaza-worker-1` → `worker`) ; > 70 % attention, > 85 % alerte ; OOM / redémarrage < 24 h visible ;
aucune requête lourde de plus (un `docker inspect` dans le cron existant, 2ᵉ clé Redis de 15 min).

**Tests** : `_containers` (noms, seuils, redémarrage récent, OOM, ligne illisible) ; Vitest (nom clair, rôle,
alerte, synchronisation vide) ; l'isolation ne change pas (console super-admin, déjà testée).

**Documents** : `docs/exploitation.md` (nouveau), `A-FAIRE.md`, `reference.md`, `03` Journal, `infra/README.md`,
`05`, `06`, `07` § 1, `maquettes/README.md`.

**Risques / à vérifier** : `State.OOMKilled` est remis à zéro au redémarrage → on s'appuie sur `RestartCount`
et `StartedAt` ; noms `docker stats` = `<projet>-<service>-<n>` ; cron `conteneurs.sh` à reposer par `make deploy`.
**Regard senior** : pas de lien cliquable par service ni de graphe d'historique (coût, peu utile) ; le lien du guide
pointe vers le dépôt (à noter dans « À valider »).
