# Impression des bulletins et capacité du serveur — mesures du 2026-10-16

Déclencheur : l'utilisateur imprime 35 bulletins de la démo ITIG en ≈ 1 min et la carte « Santé du serveur » de la console montre 15 % de mémoire libre, 39 % de swap.

## Serveur (Lightsail, 2 vCPU, 2 Go, 60 Go)
- Mémoire : 1 586 Mo utilisés, 319 Mo disponibles ; swap 807 Mo sur 2 Go ; charge CPU 0,1 au repos ; disque 17 % utilisé.
- Conteneurs : `django` **752 / 768 Mo (98 %)**, `celery` 193 / 512, `db` 68 / 512, `caddy` 20 / 192, `redis` 4 / 96.
- Cause : gunicorn, 3 travailleurs synchrones, `--timeout 120`, sans recyclage ; un travailleur garde **593 Mo** après l'impression d'une classe (WeasyPrint ne rend pas la mémoire à l'système).

## Impression (mesurée sur la machine de développement, mêmes données que la démo)
| Mesure | Valeur |
|---|---|
| Calcul de la classe (35 élèves) | 0,3 s |
| Contextes + gabarits (35) | 3,8 s |
| **WeasyPrint, un bulletin** | **≈ 1,9 s** (2,7 s la première page, polices comprises), linéaire : 5 → 9,8 s, 10 → 19 s |
| 35 bulletins en un seul document | ≈ 67 s au repos, **173 s** machine chargée |
| Mémoire du processus | 202 Mo avant, **≈ 13 Mo par page**, 700 Mo à 35 pages |
| Taille du PDF | ≈ 95 Ko par bulletin |
| Où va le temps | mise en page du tableau (≈ 80 %), écriture du PDF 0,3 s, images négligeables |

Conséquences : une classe de 45 (capacité de l'ITIG) dépasse le délai de 120 s de gunicorn sur un serveur chargé (erreur 502) ; deux impressions simultanées dépassent la mémoire du conteneur ; l'impression bloque un des 3 travailleurs web.

## Base de données (démo ITIG : 800 élèves, une période de notes)
49 Mo en tout (notes 21 Mo pour 57 745 lignes, charges 7 Mo, paiements 1 Mo). Une année complète ≈ 100 à 150 Mo par école de 800 élèves ; 60 Go de disque = pas un facteur limitant. `shared_buffers` 128 Mo, 100 connexions.

## Capacité estimée (estimations, à mesurer en PERF.4)
- Usage courant (saisie, caisse, consultation) : requêtes de 10 à 50 ms ; 3 travailleurs tiennent plusieurs dizaines de requêtes par seconde ; **mémoire** limite d'abord : ≈ 10 à 15 écoles actives sans impression.
- Impression de tous les bulletins d'une école de 1 200 élèves ≈ 38 min d'un cœur. Deux écoles qui impriment en même temps saturent les deux cœurs ; quatre en même temps = file d'attente de plusieurs heures. D'où : impression en tâche de fond, une à la fois, et PDF gardés (parents, réimpression).
- Aujourd'hui : 1 espace (démonstration), 0 école réelle.
- Seuils pour changer de machine : 2 écoles réelles ou attente d'impression > 10 min → 4 Go (≈ 20 $/mois) ; 6 écoles réelles → 8 Go / 4 vCPU. Avant : ne rien acheter, corriger le logiciel.
