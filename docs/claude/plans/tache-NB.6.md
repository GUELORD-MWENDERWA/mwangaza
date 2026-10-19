# Tâche NB.6 — Seconde session (repêchage)

**But** : après la proclamation de fin d'année, les élèves « repêchage » passent une vraie seconde session : date de l'examen fixée par l'école, convocation imprimable, note signée par l'enseignant du cours (8.4.1, inchangé), délibération de seconde session avec son conseil et son PV ; l'élève garde son pourcentage ; bulletin, situations et passage de classe lisent la décision finale.

**Hors périmètre** : remise du bulletin au parent (8.4.6, 8.8) ; notification des convocations (on imprime) ; heure et salle de l'examen (écrites à la main ou dites par l'école). **Hors ligne** : non (`05` § 5 bis : délibération et PDF en ligne).

**Critères d'acceptation**
- `Deliberation.second_session` (fin d'année seulement ; unique par classe et session) et `exam_on` (date de l'examen). Elle s'ouvre seulement si la dernière proclamation de fin d'année a des élèves « repêchage » ; ses lignes = ces élèves seuls.
- Décisions : admis, double, réorienté, exclu, abandon (jamais « repêchage ») ; proposition d'après les notes de repêchage (`resits.decide`) ; écart motivé ; proclamation, réouverture, conseil et PV comme NB.5 (`?second=true`).
- Notes de repêchage refusées quand la seconde session de la classe est proclamée (rouvrir d'abord).
- Lecture finale unique (`deliberation.year_results`) : la ligne de seconde session remplace la ligne « repêchage » de la première ; bulletin (date et mention), situations (classe et école) et passage de classe la suivent.
- Écran Repêchage : carte « Seconde session » (élèves convoqués, date de l'examen, convocations, lien vers la délibération) ; Délibération : session « Seconde session » (cours repassés, notes) ; maquettes d'abord (`repechage.html`, `deliberation.html`, nouvelle `convocation-repechage.html`).

**Tests obligatoires** : isolation (convocations et seconde session d'une autre école : 404) ; 403 (secrétaire, écriture par un enseignant membre) ; ouverture refusée sans repêchage proclamé ; décision « repêchage » refusée ; note bloquée après proclamation ; bulletin, situation et passage suivent la décision finale ; journal.

**Documents** : `04` (Deliberation), `03` journal, `reference.md` + `A-FAIRE.md` § 11, `07` § 1 et § 4, `maquettes/README.md`, `05`, `06`.

**Risques** : `get_or_create(term=None)` et filtres `term__isnull=True` (deliberation, prior_results, demo) à limiter à la première session ; contrainte unique à remplacer sans perte.
