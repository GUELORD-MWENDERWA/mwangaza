# Tâche 8.4.5 — Passage de classe et confirmation de place (issue #298)

**But.** Après la proclamation, l'école propose à chaque ancien sa place de l'année suivante d'après la décision (admis → niveau suivant, même option et section si elle existe ; doublant → même niveau ; réorienté → classe à choisir ; repêchage → attend ; exclu, abandon, fin d'études → pas de place) ; le parent répond « revient » ou « ne revient pas » au Portail ; l'école inscrit ensuite (frais dus créés par les barèmes de l'année suivante). Rien n'est créé sans ce clic de l'école.

**Hors périmètre.** Verrou d'une année « clôturée » (`AcademicYear.status`) : touche tous les écrans, pas utile pour passer de classe (l'école change déjà d'année en cours dans Organisation). Statut de l'inscription de l'année finie inchangé (l'historique reste tel quel). Passage sans le module `academics` (inscription élève par élève, comme aujourd'hui). Frais de réinscription demandés avant la réponse : 8.4.6 / 8.8.

**Modèle.** `PlaceConfirmation` [T] : `enrollment` (année finie, unique), `class_group` (année suivante), `status` proposée / inscrite / retirée, `answer` (vide, oui, non), `answered_at`, `answered_by`. Année suivante = la première qui commence après ; année de départ = la dernière qui a une suivante, pas après l'année en cours.

**Critères d'acceptation.** Écran « Passage de classe » (droit `students.edit`, module `academics`) : résumé par classe puis élèves d'une classe (décision figée de la dernière proclamation, place proposée modifiable, réponse du parent, état) ; proposer, inscrire, retirer en lot. Portail : carte « Place pour 2027-2028 » à l'accueil, réponse modifiable tant que l'école n'a pas inscrit ; notification au parent. Journal : place proposée, retirée, réponse du parent, inscription (`students.enrolled`). Annulation d'un import : un élève qui a une place est gardé.

**Tests obligatoires.** Isolation (autre école : ni lecture ni écriture, Portail compris) ; 403 sans `students.edit` ; règles (repêchage, exclu, classe non proclamée, classe d'une autre année refusés ; inscription en lot = frais dus + matricule gardé, sans doublon) ; parent : seulement ses enfants, pas après l'inscription ; audit.

**Documents.** `04` (modèle), `03` (journal des décisions), `02` si besoin, `reference.md`, `A-FAIRE.md` § 11, `07` § 1 et § 4, `maquettes/README.md`, `CLAUDE.md` (glossaire), `05`, `06`.

**Risques.** Inscriptions en lot : une seule passe de frais (`sync_charges`), `touch_enrollments` ; `make demo` : année 2027-2028 copiée (classes et barèmes) — `test_demo` crée aussi 2027-2028, à adapter.
