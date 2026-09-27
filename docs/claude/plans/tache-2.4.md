# Tâche 2.4 — Impressions (D5, M11, M6)

- **Dépendance** : WeasyPrint (dans la stack décidée ; libs Pango dans `Dockerfile.dev` et la CI). Pas de QR code (dépendance à valider en 3.2) : l'adresse du portail est écrite en clair (`PORTAL_URL`).
- **Serveur** : `core/documents.py` (gabarit HTML → PDF, classeur Excel, réponses) ; gabarits Django `print_base`, fiche, liste ; textes traduits (`make messages`).
- `GET /api/enrollments/{id}/form/?output=pdf|html&paper=a4|a5&family_code=` : `students.view` ; code famille seulement avec `students.edit`, noté dans l'audit à chaque PDF (`students.family_code_printed`) ; aperçu HTML : code masqué.
- `GET /api/enrollments/class-list/?class_group=&output=pdf|xlsx|html&columns=&blank_columns=&order=` : élèves actifs, NOM POST-NOM Prénom ou matricule, effectif garçons / filles, titulaire, colonnes au choix (matricule, sexe et naissance, téléphone du tuteur principal), 0 à 5 colonnes vides.
- `GET /api/audit/export/` : mêmes filtres que la liste, période `since` + `until` obligatoire (366 jours au plus), `audit.view`, l'export noté (`audit.exported`).
- **Front** : page « Fiche d'inscription » (`/enrollments/:id/form`, aperçu + A4/A5 + code), page « Liste de classe » (`/students/class-list`), bouton « Exporter » du journal ; liens depuis la fiche élève, le bandeau « inscrit » et la liste des élèves.
- **Reporté** : frais de l'année sur la fiche et colonne « situation des paiements » (2.7), sélection multiple depuis la liste des élèves, QR code (3.2).
- **Tests** : isolation (inscription, classe, journal d'une autre école → 404 / rien), 403 (sans `students.view`, code sans `students.edit`, export sans `audit.view`), audit (code imprimé, export), règles (élèves actifs seulement, ordre, période obligatoire), PDF réel (`%PDF`), Excel (colonnes). Front : un test par page (code caché sans droit, adresse d'export avec les filtres).
- **Risque** : WeasyPrint absent de la CI → installer `libpango` dans le job backend.
