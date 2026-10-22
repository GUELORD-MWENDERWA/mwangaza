# Calcul de l'horaire (EDT.3a) — mesures du solveur

2026-10-22, machine de développement (8 Go), OR-Tools 9.15, ITIG de `make demo` : 23 classes, 417 unités (cours ou groupes), 643 séances à placer, ≈ 18 500 départs possibles, 4 ateliers, 1 laboratoire fermé le samedi, 7 règles. Mémoire : pic du processus (`ru_maxrss`), Django compris.

| Essai | Résultat | Temps | Pic |
|---|---|---|---|
| Django chargé, rien d'autre | — | — | ≈ 95 Mo |
| `import cp_model` (tire pandas et numpy) | — | — | + ≈ 80 Mo |
| 1 fil, recherche ordinaire, avec « pas de trou » | rien trouvé | 60 s | 297 Mo |
| 1 fil, sans « pas de trou » | optimal | 3,5 s | 285 Mo |
| 8 fils, avec « pas de trou » | trouvé (par `fj`, recherche locale) | 3,9 s | 368 Mo |
| 1 fil, recherche locale seule (`use_ls_only`) | premier horaire | 3,6 s | 241 Mo |
| **Retenu** : 1 fil, trois temps, 10 s (`make demo`, recherche locale au moins 8 s) | complet, 0 erreur | 10 s | 250 Mo |
| 1 fil, trois temps, 20 s | complet, pénalité 670 | 20 s | 257 Mo |
| **Retenu** : 1 fil, trois temps, 60 s (préréglage) | complet, pénalité 644 | 60 s | 271 Mo |

- **Trois temps** (`solver.solve`) : recherche ordinaire sur 15 % du temps (petits cas résolus, impossibilité prouvée), recherche locale seule jusqu'au premier horaire sur 35 %, puis amélioration à partir de lui (indice) sur le reste. Avec un seul fil, CP-SAT n'essaie jamais la recherche locale de lui-même.
- Horaire calculé vérifié par `checks.draft` : 0 erreur, rien à placer. Souhaits non tenus à 20 s : étalement 112 fois (3 h d'un cours en heures seules : jours qui se suivent souvent inévitables), matinée 16, mathématique en dernière heure 5, trous d'enseignants 2.
- Essai avec les heures de démo d'avant (classes à 41–62 h) : « impossible » prouvé en 4,6 s, règle qui bloque nommée (laboratoire et atelier en parallèle aux séances différentes : nouveau contrôle `group_sessions_differ`).
- **Mémoire** : le calcul ajoute ≈ 160 à 175 Mo à Django, dont ≈ 80 Mo d'import. Au-delà du seuil de 250 Mo de `05` § 8.5 pour tout le processus, sous ce seuil pour le calcul seul. Le travailleur `heavy` est remplacé après une tâche qui dépasse 240 Mo (`--max-memory-per-child`) : la mémoire est rendue juste après. « Grille par grille » ne s'applique pas à l'ITIG (une seule grille). À suivre sur le vrai serveur (EDT.3b) ; OPS.5 (4 Go) seulement si le pic gêne les autres services.
- À essayer si une vraie école est plus lente : plus de temps (180 s), ou des enseignants sur tous les cours (la démo n'en a que sur 10 cours, ce qui allège O2).
