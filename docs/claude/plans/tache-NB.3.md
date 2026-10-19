# Tâche NB.3 — Espace du titulaire

**But** : « Ma classe », pour le titulaire seul : par période (ou examens), les fiches de cotes de sa classe (état, totaux en lecture seule), ce qui manque, la vérification élève par élève (total, %, place, conduite, application), les statistiques de la classe, puis « Bulletins prêts » quand toutes les fiches sont validées ; le directeur des études le voit dans « Suivi des notes » et en est averti.

**Hors périmètre** : délibération par période et PV (NB.5) ; seuils de réussite de l'école (NB.4 : « au moins la moitié » en attendant) ; correction de la conduite ici (reste `discipline.override`, écran Conduite) ; hors ligne : non (calcul au serveur, comme NB.2).

**Regard senior** : aucune copie des notes (le bulletin de la classe, déjà calculé, donne tout) ; un seul petit modèle `ReportCardsReady` (une ligne par classe et période) ; sa validité est calculée (toutes les fiches validées, aucune validée après la déclaration) : pas de crochet dans le renvoi d'une fiche. Classe sans titulaire : « Bulletins » suit encore « classe complète » (personne ne pourrait la dire prête). Le préfet ne voit les notes que si l'école lui donne `grades.validate` (rôle de départ sans droit de notes) : à valider.

**Critères d'acceptation**
- `GET /api/homeroom/?class_group=&term=` : classes dont le compte est titulaire (année en cours), découpage, cours avec état (comme NB.2), statistiques, élèves, état « prêts » ; 403 pour qui n'est pas titulaire de la classe ; requêtes bornées.
- `POST` / `DELETE /api/homeroom/ready/` : 409 `sheets_missing` si une fiche n'est pas validée ; journal `grades.report_cards_ready` / `grades.report_cards_withdrawn` ; notification `report_cards_ready` à `grades.validate`.
- `/api/me/` : `school.homeroom` (menu « Ma classe ») ; « Suivi des notes » : « Bulletins prêts » et bouton « Bulletins » d'après ce signal.
- Écran : maquette `gestion/titulaire` dessinée d'abord ; 390 et 1440 px.

**Tests obligatoires** : isolation (classe d'une autre école : 404) ; 403 (enseignant non titulaire, DE) ; 409 incomplet ; déclaration au journal + notification ; renvoi puis revalidation → plus prête ; retrait ; requêtes bornées ; scénario `make demo`.

**Documents** : 04, 03, 05, 06, 07 § 1 et § 4, maquettes/README, reference.md, A-FAIRE § 11.

**Risques** : choix de notification (migration), `Record<NotificationKind>` du front ; `make messages` ; `make api` ; `ecrans.spec.ts`.
