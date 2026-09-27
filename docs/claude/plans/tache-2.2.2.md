# Tâche 2.2.2 — fiche élève, fiche famille, recherche `Ctrl K`

**Serveur (`students`)** : `GET /api/students/{id}/history/` (journal de l'élève, de ses inscriptions et de sa famille, sans IP ; `students.view`) ; `GET|POST|DELETE /api/students/{id}/photo/` (image servie par l'API, jamais publique ; PNG / JPEG ≤ 1 Mo reconnus à leurs octets ; `students.edit` pour changer) ; `photo` (adresse) dans la fiche ; 409 `possible_duplicate` avec `duplicates` (id, noms, matricule) ; famille vidée par une liaison → supprimée (audit) ; matricule des enfants dans la fiche famille.
**Règle photo (à valider)** : photo seulement avec le consentement du parent ; retirer le consentement efface la photo. Réduite dans le navigateur (canvas, ~600 px, JPEG) avant l'envoi : pas de Pillow.
**Front** : `students/:id/:tab?` (Identité, Famille, Finances vide jusqu'à 2.7, Historique : frise + parcours), `students/:id/edit` (même formulaire que l'inscription, sans classe ni famille), `families/:id` (enfants, tuteurs modifiables, code) ; « Lier à une autre famille » (recherche existante) ; palette `Ctrl K` dans l'en-tête (élèves : noms, matricule, code famille) ; lignes de la liste et fin d'inscription → fiche ; doublon → lien vers la fiche.
**Hors tâche** : changer de classe, départ, inscrire depuis la fiche → ajoutés à la 2.6 (frais recalculés) ; nouveau code, portail → 4.4 ; impressions → 2.4 ; échu non payé → 2.7.
**E2E** : `globalSetup` renvoie un teardown qui relance `make demo` (mémoire du 2026-09-27).

**Tests** : isolation (historique, photo, liaison vers la famille d'une autre école), permissions (403 photo / historique), audit (photo, suppression de famille), consentement ; Vitest : fiche (onglets, lecture seule sans `students.edit`), doublon → lien, palette.
**Risques** : `<img>` authentifiée par cookie (même origine via le proxy : OK) ; canvas absent de jsdom (réduction isolée, non testée).
