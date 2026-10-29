# Espace de travail de Claude

Les fichiers de travail de Claude Code : ce qui prépare, justifie ou contrôle le code, sans être un document de référence du projet.

| Dossier | Contenu | Nom des fichiers |
|---|---|---|
| `reference.md` | Détail des commandes (dont tout ce que crée `make demo`) et chaque écran, chaque API en développement : sorti de `CLAUDE.md` pour qu'il reste court. À compléter dans la PR de chaque tâche qui en ajoute. | — |
| `plans/` | Fiche de chaque lot (depuis le 2026-10-29 ; avant : une par tâche), écrite **avant** de coder : but, parties cochées au fur et à mesure, tests prévus, décisions à prendre. Mise à jour si le plan change en cours de route. | `lot-1.md`, `tache-0.1.md` |
| `recherches/` | Notes de recherche avec sources : informations web, comparaison de bibliothèques, règles scolaires RDC / EPST, formats officiels. | `AAAA-MM-JJ-sujet.md` |

## Règles

- Les documents de référence restent dans `docs/01` à `05` ; l'état du projet dans `docs/06-suivi.md`. Ce dossier ne les remplace pas.
- Une recherche qui change une règle ou le modèle de données devient une proposition dans `docs/06-suivi.md` (« Questions ouvertes ») ; on ne modifie `docs/01` à `05` qu'après accord.
- Pas de données personnelles ici (elles vont dans `docs/ecole-pilote/prive/`).
