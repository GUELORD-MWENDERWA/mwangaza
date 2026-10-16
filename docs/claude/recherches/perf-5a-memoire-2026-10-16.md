# PERF.5a — mémoire et tâches de fond (2026-10-16)

**Avant** (vrai serveur, tableau de santé du 2026-10-16, une école de test) : celery 256 Mo à 13 h 54 puis 263 Mo à 14 h 15 sur 320 Mo (82 %) **sans activité** (planificateur et 2 travailleurs dans le même conteneur) ; django 317/640, celery-print 128/512, caddy 26/192, db 40/512, redis 4/96. Somme des limites ≈ 2,3 Go (+ `migrate` 512 Mo) pour 2 Go de RAM.

**Après** (`make prod-local`, mêmes images et mêmes limites que le serveur, démo `make demo`, `make perf --users 5`) :

| Conteneur | Limite | Au repos | Sous 5 utilisateurs |
|---|---|---|---|
| django (2 processus × 2 fils, `--preload`) | 576 Mo | 95–135 Mo | 367 Mo |
| worker (file rapide, 2 travailleurs) | 288 Mo | 187 Mo | 187 Mo |
| worker-heavy (file lourde, 1 travailleur) | 384 Mo | 125 Mo | 136 Mo (pic, 23 pages) |
| scheduler (beat) | 144 Mo | 107 Mo | 107 Mo |
| db (PostgreSQL réglé) | 256 Mo | 36 Mo | 72 Mo |
| redis (48 Mo, `volatile-lru`) | 64 Mo | 4 Mo | 4 Mo |
| caddy | 64 Mo | 15–28 Mo | 28 Mo |

Somme des limites ≈ 1,78 Go (`migrate` 384 Mo seulement au démarrage). Aucun arrêt pour manque de mémoire sous 5 utilisateurs ; temps (médiane) : tableau de bord 2,1 s, impayés 2,3 s, élèves 0,6 s, paiements 0,25 s, classes 0,07 s ; impression d'une classe de 45 familles (lettres, file lourde) 12 s.

**Ce que la mesure a appris**
- **Argon2 ≈ 100 Mo par mot de passe vérifié** (réglage de Django). Avec des fils, trois connexions simultanées suffisaient à tuer un processus Gunicorn (conteneur de 448 Mo) : le hachage est maintenant fait un à la fois par processus (`core/hashers.py`, même format de mots de passe).
- Les écrans « Impayés » (+ 90 Mo) et « Tableau de bord » (+ 57 Mo) demandent beaucoup de mémoire par requête et un processus Python ne la rend pas : 2 processus × 2 fils (et non 4 fils) et 576 Mo ; à alléger plus tard (voir `03` § 9).
- Beat seul pèse ≈ 107 Mo (Django entier chargé) : conteneur de 144 Mo (74 %).
- Un PDF lourd (23 pages) : pic de 136 Mo dans le travailleur lourd ; une tranche de 8 bulletins ≈ 220 Mo (PERF.1) : limite 384 Mo, travailleur renouvelé au-delà de 240 Mo.
- `make perf` : les bulletins demandent des notes validées (409 avec les données de la démo) ; il imprime alors les lettres d'invitation de la classe, et se connecte pour cela avec la directrice des études (`--print-phone`).
