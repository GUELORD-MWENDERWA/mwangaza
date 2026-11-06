# Lot 9 — Emploi du temps fini et IA

**But** : le directeur des études publie l'horaire des épreuves (enseignants et parents le lisent), note les heures non données ou en plus et imprime la fiche des heures prestées pour la paie ; l'IA aide sans jamais décider : grille de cours tirée d'un bulletin, réponses aux questions de chiffres, brouillons d'annonces. Tâches : EDT.5b (#398), EDT.6, IA.5, IA.3, IA.4 ; issue #434.

## Parties (une conversation chacune)
- [x] ① Maquettes du lot ; serveur des 5 tâches : PDF et notification des épreuves, lecture enseignant et Portail ; `LessonException`, calcul du mois, fiche PDF, export Excel ; usages `course_grid_from_pdf`, `assistant`, `drafting` — **Opus**
- [x] ② Écrans : horaire des épreuves, heures prestées, grille depuis un bulletin, assistant, brouillon IA — Sonnet
- [x] ③ Fin du lot : captures 390 / 1440, définition de « fini », `/verifier`, tous les `.md`, aide, PR — Sonnet

## Décisions (regard senior)
- IA.3 : l'IA ne reçoit **aucune donnée d'élève** ; elle traduit la question en une requête d'une liste fermée (impayés, encaissements, effectifs, charge des enseignants ; résultats d'une période avec le lot 10), JSON vérifié par schéma ; le **code** calcule avec les permissions de la personne et rend chiffres + lien vers l'écran. Un appel court par question, aucune injection possible par les données. Absences : avec le lot 10 (présences pas encore faites). Limites : questions par personne et par jour, 3 questions d'avant en contexte (console).
- IA.4 : brouillons dans l'éditeur d'annonce (circulaire, relance aux familles) et de convocation ; la personne modifie et publie. Appréciations de bulletin : aucune case d'appréciation saisie dans le bulletin → reportées avec cette case (à valider).
- IA.5 : le fichier (PDF ≤ 3 pages ou photo) n'est jamais lu par notre serveur, seulement contrôlé (signature, poids, pages), gardé le temps de l'appel puis effacé ; la réponse remplit l'écran « Cours et maxima », enregistré par l'endpoint existant.
- EDT.6 : on ne note que les exceptions ; total calculé à la demande (agrégats par version de l'horaire et jours de cours du mois, `SchoolEvent` congés retirés), jamais stocké. Nouveau droit `timetable.record_exceptions`.

- ① fait (2026-11-06) : `exams.upcoming` / `pages` (+ `/api/timetable/exams/<p>/print/`), `exams` dans `/api/timetable/mine/` et l'horaire d'un enfant, notification = sorte `timetable_published` (qui coupe l'une coupe l'autre) ; `timetable/worked.py` + `/api/timetable/worked/` (`day/`, `exceptions/`, `…/cancel/`, `sheet/`, `export/`), un cours commun = une heure, versions par jour ; `ai/questions.py`, `drafting.py`, `course_grid.py` + `/api/ai/questions|drafts|course-grid/` ; socle : pièce jointe hors file (`ai-uploads/`, effacée après l'appel, purge), comptage exact des jetons avant un fichier (gratuit), `daily_limit` par usage (console). Assistant : impayés, encaissements, effectifs, charges (résultats et absences avec le lot 10). Démo : épreuves de la période en cours (à venir), 4 exceptions récentes. Pour ② : console (champ « par jour »), libellés `kind`, menu « Heures prestées » (droit `timetable.record_exceptions`). Pour ③ : `04`, spec EDT § 12, `reference.md`, `07` § 4, À valider (sorte de notification partagée, liste de l'assistant, appréciations reportées).

- ② fait (2026-11-06) : menu « Horaire des épreuves » (`timetable.manage`) et « Heures prestées » (`timetable.record_exceptions`) ; `useAiCall` (un clic = un appel, lecture toutes les 2 s) ; bouton « Question » dans la barre du haut (panneau, conversation gardée dans l'onglet) ; « Brouillon IA » dans annonces et convocations ; « Lire un bulletin » dans Cours et maxima ; épreuves à venir dans « Mon horaire » et le Portail. Les surveillants et remplaçants se choisissent parmi les enseignants ayant des cours (liste `timetable/courses`). Reste pour ③ : captures (ajouter les écrans à `apercu/ecrans.spec.ts`), articles d'aide, docs.

## Hors périmètre
Appel en classe (V1.5), absences dans l'assistant (lot 10), calcul de la paie (lot 12).

## Critères d'acceptation
Épreuves publiées → notification, PDF par classe, lecture enseignant et Portail ; une absence retire l'heure, un remplacement la donne au remplaçant, congé non compté ; Excel du mois juste ; l'IA ne fait qu'un appel par demande et n'écrit rien seule.

## Tests obligatoires
Isolation (épreuves, exceptions, fiche, export, fichier envoyé, assistant) ; 403 sans `timetable.record_exceptions`, sans `ai.use` ou droit de l'écran hôte ; journal des exceptions et de leur annulation ; calcul du mois (congé, remplacement, changement de version) ; assistant : question d'un écran interdit → refus sans chiffre.

## Documents à mettre à jour
`05`, `06`, `03` (journal), `04` (LessonException), spec EDT § 11-12, `07`, `reference.md`, `A-FAIRE.md` § 11, `maquettes/README.md`, aide.

## Risques
`import_cancellation.py` (aucune clé vers un élève prévue) ; Redis petit : jamais le fichier dans la file Celery ; prix et champs de l'API à relire (skill `claude-api`).
