# Espace de travail de Claude

Les fichiers de travail de Claude Code : ce qui prépare, justifie ou contrôle le code, sans être un document de référence du projet.

| Dossier | Contenu | Nom des fichiers |
|---|---|---|
| `plans/` | Plan de chaque tâche, écrit **avant** de coder : fichiers touchés, tests prévus, décisions à prendre. Mis à jour si le plan change en cours de route. | `tache-0.1.md` |
| `recherches/` | Notes de recherche avec sources : informations web, comparaison de bibliothèques, règles scolaires RDC / EPST, formats officiels. | `AAAA-MM-JJ-sujet.md` |
| `revues/` | Anciennes revues `/verifier`, jusqu'à la tâche 1.7. Depuis, le résultat tient en quelques lignes dans la PR (section « Tests ») : plus de fichier ici. | `tache-1.1.md` |

## Règles

- Les documents de référence restent dans `docs/01` à `05` ; l'état du projet dans `docs/06-suivi.md`. Ce dossier ne les remplace pas.
- Une recherche qui change une règle ou le modèle de données devient une proposition dans `docs/06-suivi.md` (« Questions ouvertes ») ; on ne modifie `docs/01` à `05` qu'après accord.
- Pas de données personnelles ici (elles vont dans `docs/ecole-pilote/prive/`).
