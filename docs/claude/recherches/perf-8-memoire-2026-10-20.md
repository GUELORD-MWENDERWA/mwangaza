# PERF.8 — mémoire du serveur sans gaspillage (2026-10-20)

**Constat** (carte Santé du vrai serveur, une seule école fictive) : mémoire disponible 28 %, swap 10 % ; `django` 258/576 Mo, `worker` 218/288 (76 %), `worker-heavy` 131/384, `scheduler` 111/144 (77 %), `db` 58/256, `redis` 6/64, `caddy` 15/64. Somme des conteneurs ≈ 800 Mo sur ≈ 1,9 Go.

**Cause** : un coût fixe, le même avec 0 ou 20 écoles, pas une fuite ni les données.
- Django entier chargé dans 4 conteneurs : site, travailleur rapide, travailleur lourd, **et le planificateur**, qui ne fait pourtant que poser un nom de tâche dans Redis toutes les 15 minutes.
- Deux travailleurs rapides gardés en permanence pour une file presque vide ; chacun grossit jusqu'à son seuil de renouvellement (150 Mo), d'où les 76 %.
- `django.setup()` + code des tâches : ≈ 136 Mo par processus, dont ≈ 22 Mo de bibliothèques chargées à chaque démarrage sans servir (Web Push avec aiohttp, Excel, QR, Sentry).
- Hors conteneurs (système, Docker, cache) : ≈ 500 Mo à lire sur le serveur (PERF.8b, `make deploy-memoire`).

**Mesures** (cette machine, Python 3.12, réglages de production, mémoire PSS ou RSS) :

| | Avant | Après |
|---|---|---|
| Un processus Django + tâches chargées (RSS) | 136 Mo | 114 Mo |
| Planificateur (RSS) | 139 Mo (Django entier) | 52 Mo (`celery -A beat beat`, sans Django) |
| Travailleur rapide au repos (PSS, tous ses processus) | 213 Mo (`--concurrency=2`) | 135 Mo (`--autoscale=2,1`) |

Sur le serveur, `docker stats` compte un peu moins (pages de fichiers partagées) : attendu ≈ 50 Mo pour `scheduler` et ≈ 135 Mo pour `worker`, soit ≈ 140 à 150 Mo rendus à la machine, plus ≈ 20 Mo dans `django` et `worker-heavy`.

**Fait**
- `backend/task_schedule.py` (files, routes, horaires, sans Django) lu par les réglages et par `backend/beat.py` (application Celery sans Django, `fixups=[]`). Le conteneur `scheduler` ne reçoit plus que `REDIS_URL` : ni mot de passe de la base, ni clé secrète, ni volume des fichiers. Limite 144 → 96 Mo.
- `worker` : `--autoscale=2,1` (un second travailleur s'ouvre quand des tâches attendent, rendu après 30 s). Les limites de temps restent (elles exigent `prefork`, pas des fils).
- `pywebpush`, `openpyxl`, `segno`, `sentry_sdk` importés dans la fonction qui s'en sert ; test `test_heavy_libraries_are_loaded_only_when_used`.
- `MALLOC_ARENA_MAX=2` (image) : un processus à plusieurs fils ne se crée plus une réserve de mémoire par fil. `gc.freeze()` avant la création des travailleurs (Gunicorn `when_ready`, Celery `worker_init`) : les objets chargés restent partagés au lieu d'être recopiés peu à peu.
- `make deploy-memoire` : `free -m`, `docker stats`, 15 processus les plus lourds.

**Gardé exprès** : Argon2 à ≈ 100 Mo par vérification (réglage de Django, un à la fois par processus) ; deux files séparées ; 2 processus × 2 fils pour le site ; renouvellement des travailleurs.

**Écarté** : fusionner les deux travailleurs (un PDF retarderait les notifications) ; travailleur lourd en `solo` (plus de limite de temps ni de renouvellement après un PDF) ; baisser Argon2 (affaiblit les mots de passe).
