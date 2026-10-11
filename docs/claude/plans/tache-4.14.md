# Tâche 4.14 — Annuler un import (issue #157)

**Besoin (D6)** : un fichier importé dans la mauvaise année ou les mauvaises classes ne se rattrape pas ; aucun écran ne retrouve un import passé.

**Serveur** (`students`)
- Modèle : `Student.student_import` (lien gardé, vide pour un élève saisi à la main) ; `StudentImport` : état `cancelled`, `cancelled_at`, `cancelled_by`, `cancel_reason`, `cancelled_count`, `matricule_start` (numéro du matricule avant l'import). Migration.
- `imports.run` remplit le lien et `matricule_start`.
- `imports.cancellation(imp)` : élèves à retirer, élèves gardés et pourquoi (une requête, sous-requêtes `Exists`).
- `imports.cancel(imp, actor, reason)` : une transaction, import verrouillé ; efface frais dus, inscriptions, élèves, puis les familles restées sans élève ; `ChangeLog` `delete` en un envoi (les appareils retirent les élèves) ; photos effacées après validation ; numéro de matricule repris à `matricule_start` ; une ligne de journal par élève et une pour l'import.
- API : `GET /api/student-imports/` (imports finis, paginés, sans les colonnes lourdes), `GET …/{id}/cancellation/`, `POST …/{id}/cancel/` (`reason`).

**Gestion** : carte « Imports précédents » sur `/students/import` ; sur la page d'un import fini, « Annuler cet import » (fenêtre : nombres, élèves gardés, motif obligatoire) ; import annulé : bandeau avec motif, auteur, date. Maquette `gestion/eleves-import-annulation.html`.

**Tests** : isolation (l'école B n'annule ni ne lit un import de A, ses élèves restent) ; 403 sans `students.import` ; élève avec paiement, réduction, échéancier particulier ou compte parent gardé avec sa famille, les autres retirés ; ni paiement ni reçu touché ; motif obligatoire ; déjà annulé → 409 ; journal ; `ChangeLog` `delete` ; fichier ré-importable après ; Vitest : fenêtre (motif, gardés).

**Décisions (regard senior)**
- **Par élève, pas tout ou rien** : un seul paiement ne bloque pas l'annulation de 800 élèves ; l'élève touché reste, l'écran le nomme.
- **Effacement réel**, pas d'état « annulé » sur l'élève : sinon chaque liste, total et doublon devrait l'exclure. Les frais dus jamais payés partent avec l'inscription (exception voulue à « rien n'est effacé dans les finances » : aucun paiement ne les touche).
- **Pas de nouveau droit** : qui importe (`students.import`) annule ; un droit de plus serait donné aux mêmes rôles.
- **Compte parent activé** = élève gardé (4e raison, ajoutée : on n'efface pas ce qu'un parent utilise).
- **Dans la requête, pas en tâche de fond** : suppressions en masse (`_raw_delete`, sans signal par ligne), une dizaine de requêtes pour 800 élèves.
- **Délai de 30 jours** après la fin de l'import (accord de l'utilisateur) : sans lui, un import de septembre annulé par erreur en mars effacerait tous les élèves sans paiement. Un import d'avant cette tâche n'a pas le lien et ne s'annule pas.
