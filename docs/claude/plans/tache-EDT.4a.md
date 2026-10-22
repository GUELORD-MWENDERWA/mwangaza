# Tâche EDT.4a — Publication de l'horaire (#382)

**But** : publier un brouillon depuis l'éditeur ; la version publiée ne bouge plus, l'ancienne est archivée ; publiée et archivées se consultent en lecture et se recopient en brouillon (spec § 10).

**Hors périmètre** : lecture par l'enseignant, Portail, sans réseau, notification (EDT.4b) ; PDF et abréviations (EDT.4c). Découpage : EDT.4 entière ne tenait pas dans une PR.

**Critères d'acceptation**
- `POST /api/timetable/drafts/<id>/publish/` (droit nouveau `timetable.publish`, chef et DE) : refusé (409) si le brouillon a du rouge ; date d'effet dans l'année et pas avant celle de la version en vigueur ; l'ancienne publiée passe en `archived` ; historique « Annuler » vidé ; journal `timetable.published`.
- Gestes, suppression et calcul sur une version publiée ou archivée : refusés (déjà par `_open`, vérifié par test).
- `GET /api/timetable/versions/` : publiée et archivées de l'année ; un brouillon peut copier n'importe quelle version de l'année.
- Éditeur : « Publier » (fenêtre : bilan, date d'effet, version remplacée, blocage expliqué) ; une version publiée / archivée s'ouvre en lecture (bandeau, pas de geste) avec « Nouveau brouillon depuis cette version ». Maquette `gestion/publication-emploi-du-temps.html` d'abord.
- `make demo` : l'horaire calculé de l'ITIG est publié (vérifié dans `test_demo.py`).

**Regard senior** : reste à placer non bloquant (avertissement : une école publie un horaire provisoire en début d'année) ; publication sérialisée par verrou sur l'année (deux publications en même temps ne cassent pas la contrainte d'unicité) ; aucune écriture en plus par requête.

**Tests obligatoires** : isolation (publier / lire une version d'une autre école → 404) ; 403 sans `timetable.publish` ; publication refusée avec conflit ; immuable après publication ; archivage de la précédente ; journal écrit ; date d'effet refusée hors de l'année.

**Documents** : `04` (Timetable, droit), `03` journal, spec § 10, `reference.md`, `A-FAIRE.md` § 11, `07` § 1, `maquettes/README.md`, 05, 06.

**Risques** : droit nouveau → migration des rôles (comme `0016`) ; `RolesPage` liste les droits (ajouter) ; `DraftState` gagne `valid_from`, `published_at`, `published_by`.
