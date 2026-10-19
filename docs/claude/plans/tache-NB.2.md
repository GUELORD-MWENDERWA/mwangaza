# Tâche NB.2 — Tableau du directeur des études

**But** : sur une page, par période, le directeur des études voit l'état de la fiche de cotes de chaque cours de chaque classe (pas commencée, en cours, envoyée, validée, renvoyée), les classes qui n'ont pas tout envoyé et les classes complètes, rappelle les retardataires en un geste et ouvre le tableau synthétique, le palmarès et les bulletins de chaque classe.

**Hors périmètre** : « bulletins prêts » du titulaire (NB.3 : le bouton « Bulletins » suivra ce signal) ; délibération par période et PV (NB.5) ; palmarès de toute l'école (situations, 8.4.4) ; hors ligne : non (calcul et PDF au serveur, `05` § 5 bis).

**Regard senior** : pas de nouvelle page ni de nouveau modèle — « Validation des notes » devient ce tableau (même adresse, même droit) ; la file « à valider » de toutes les périodes est remplacée par le filtre « À valider » de la période. Tableau synthétique = tableau de la classe existant (8.3.6), renommé ; palmarès = un quatrième document des fiches de cotes. Rappel : une notification par enseignant (pas une par cours), un même cours au plus une fois par jour, trace au journal (pas de champ en base).

**Critères d'acceptation**
- `GET /api/grading/validation/?term=` : découpage, dates limites, période choisie (sinon la dernière commencée), classes et cours avec état, enseignant, dernier rappel ; requêtes bornées quel que soit le nombre de classes.
- `POST /api/grading/reminders/` (`term`, `courses`) : `grades.validate` ; cours envoyés, validés, sans enseignant ou déjà rappelés aujourd'hui ignorés ; 409 `notifications_off` sans le module.
- Fiche imprimée `kind=ranking` (palmarès) : place (ex æquo), nom, total, %, mention ; non classés à la fin ; « provisoire » d'après la colonne.
- Écran : maquette `notes-validation` redessinée d'abord ; liens vers `/grade-sheets?class=&kind=&column=` et `/report-cards?class=`.

**Tests obligatoires** : isolation (autre école : rien dans le tableau, rappel 404/400) ; 403 du rappel sans `grades.validate` ; états des cours ; rappel groupé par enseignant, pas deux fois le même jour, au journal ; palmarès trié avec ex æquo ; nombre de requêtes du tableau borné.

**Documents** : 04 (états), 03 (décision), 05, 06, 07 § 1, maquettes/README, reference.md, A-FAIRE § 11, guide si l'écran y est cité.

**Risques** : `notes-validation` utilisée par `ecrans.spec.ts` ; `Record<NotificationKind>` du front ; migration des choix de notification ; `make messages`.
