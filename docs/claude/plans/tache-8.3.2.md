# Tâche 8.3.2 — Bulletin PDF (issue #48, branche tache/8.3.2-bulletin-pdf)

**But** : PDF A4 (et aperçu HTML) du bulletin d'un élève d'après `class_report` (8.3.1), QR d'authenticité, signature et cachet (DOC.1), écran de choix.
**Hors périmètre** : notes seules sur formulaire pré-imprimé, classe en lot, démo (8.3.3) ; décision de passage (8.4) ; Portail (8.8) ; province, ville, commune, N° ID, N° permanent (pas de champ : lignes à remplir à la main).
**Critères** : `GET /api/class-groups/{id}/report-card/?enrollment&output` ; tableau du formulaire EPST (maxima, rouge sous la moitié, totaux, %, place/effectif, mention) ; QR → `/v/b/<jeton>` (initiales) ; PDF noté ; écran `/app/report-cards`.
**Tests** : droits (caissier, enseignant : 403), PDF audité / aperçu non, autre école et autre classe : 404, jeton d'une autre école : 404, contenu du tableau.
**Documents** : 05, 06, 03 journal, reference.md, A-FAIRE § 11, maquettes/README.
**Risques** : un seul gabarit pour les deux formulaires (colonnes d'après les périodes) ; le calcul de toute la classe pour un élève (une lecture des notes, acceptable).
