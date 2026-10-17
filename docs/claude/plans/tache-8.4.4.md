# Tâche 8.4.4 — Situation de chaque classe et de l'école

**But** : deux documents imprimables (PDF et aperçu, options d'impression 8.3.4) sur une page « Situations » (droit `grades.validate`) : situation d'une classe (inscrits, abandons, délibérés, admis, repêchage, doublants, réorientés, exclus, taux, écarts ; par cours ; palmarès) et situation de l'école (lauréat et sa classe, par classe : taux, écarts, meilleur élève ; sous-totaux par niveau, total). Critère choisi à chaque édition : règles de la classe (décision de la délibération, repêchage compris) ou moyenne seule (≥ 50 %).

**Hors périmètre** : répartition garçons / filles et formulaires statistiques EPST (V2, `01` « Rapports officiels ») ; passage de classe (8.4.5) ; envoi aux parents (8.4.6, 8.8).

**Critères d'acceptation** : la classe lit la dernière proclamation figée (sinon la délibération en cours, marquée « provisoire ») ; l'école ne compte que les classes proclamées (les autres : « non proclamée ») ; abandons = décision « abandon » + inscription « abandon » ; taux = réussites / délibérés (règles) ou / classés (moyenne) ; par cours : repêchage réussi compté en mode règles ; ex æquo = même place ; PDF noté au journal.

**Tests obligatoires** : isolation (classe d'une autre école → 404), droit refusé (403), comptes et taux des deux critères, lauréat et ex æquo, abandon d'après l'inscription, classe non proclamée exclue du total, journal du PDF.

**Regard senior** : la situation de l'école lit seulement les instantanés JSON (≈ 4 requêtes pour 1 200 élèves, pas de recalcul des notes) ; le recalcul des notes n'a lieu que pour la partie « par cours » d'une classe. Pas de nouveau modèle ni de stockage.

**Documents** : `05`, `06`, `04` (règles des situations), `03` (journal des décisions), `07` § 1, `maquettes/README.md` + maquette `gestion/situations.html`, `reference.md` et `A-FAIRE.md` § 11 (écran et API).

**Risques** : rangées figées sans matricule (lecture des inscriptions de la classe) ; ordre des niveaux (`Level.order`) ; libellés des décisions traduits.
