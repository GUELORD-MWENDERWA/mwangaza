# Tâche 8.2.1 — Saisie des notes en ligne

**But** : l'enseignant (ses cours), le titulaire (sa classe) et le secrétariat (toutes les classes) saisissent les notes d'une période ou des examens : évaluations libres (nom, maximum), note de période **ramenée au maximum** par une règle de trois, **une décimale** (décisions du 2026-10-15).

**Hors périmètre** : date limite, envoi, validation, motif et historique (8.2.2) ; hors ligne (8.2.3) ; bulletin, places, mentions (8.3).

**Critères d'acceptation**
- `Evaluation` (cours, période ou examens, nom, maximum, ordre) et `Grade` (évaluation, inscription, note 0 à maximum, une décimale), `TenantModel`, identifiants UUID v7 acceptés du client (hors ligne en 8.2.3).
- Droits `grades.enter` (ses cours + classe dont on est titulaire) et `grades.enter_any` (toutes) ; modèle de départ : enseignant, secrétaire, directeur des études ; migration : `enter_any` aux rôles qui ont `courses.configure`. Module `academics`.
- API : `GET /api/grading/` (périodes et cours que je peux noter), `GET`/`PUT /api/courses/<id>/terms/<id>/grades/` (feuille d'un seul envoi : évaluations ajoutées / modifiées / retirées, cases changées). Examens seulement pour un cours avec examen ; maximum = 2 × maximum de période.
- Journal : une entrée par enregistrement (cases et évaluations changées), pas une par note.
- Un cours, une période ou un élève noté ne se retire plus (409 existants ; annulation d'un import : raison « notes »).
- Écran « Saisie des notes » (maquette `gestion/notes-saisie`) : tableau à l'ordinateur, une carte par élève au téléphone ; total et % recalculés en direct ; « incomplet » ; Entrée = case suivante.
- `make demo` : notes de la 1re période de l'ITIG (3 évaluations par cours, quelques cases vides).

**Tests obligatoires** : isolation (feuille d'une autre école introuvable, ni lue ni écrite), 403 sans droit et pour le cours d'un autre enseignant, titulaire autorisé, note > maximum refusée, règle de trois et arrondi, journal, cours noté non retirable.

**Documents** : 04 (Evaluation, Grade, droits), 03 (décisions), 05, 06, reference.md, A-FAIRE § 11, 07 § 4, maquettes/README.

**Risques** : taille de `make demo` (≈ 30 000 notes : `bulk_create` par paquets) ; deux sessions qui enregistrent la même feuille : cases changées seulement, dernière écriture gagnante.
