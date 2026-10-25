# Tâche EDT.4c — Impressions de l'horaire

**But** : PDF de l'horaire (spec § 11, 1 à 4) : classe, enseignant avec sa charge, salle, horaire général. Page « Imprimer l'horaire » (options + aperçu, comme la liste de classe), bouton dans l'éditeur. En-tête de l'école, file `heavy` si lourd, PDF gardés (PERF.2).

**Hors périmètre** : fiche des heures prestées (EDT.6), horaire des examens (EDT.5), impression par l'enseignant de « Mon horaire », Excel.

**Critères d'acceptation** : `GET /api/timetable/print/?kind=class|teacher|room|general&subject=<id|absent=tous>&timetable=<id|publiée>&output=html|pdf` ; une page par classe / enseignant / salle ; enseignant : heures dues et placées par classe et cours, plafond ; général : abréviations (mêmes que l'écran) + légende, A4 sur 2 pages ou A3 ; récréations ; version non publiée marquée « brouillon ».

**Tests obligatoires** : 403 sans `timetable.manage` (dont l'enseignant) ; isolation (version ou sujet d'une autre école = 404, rien d'elle dans le tout) ; contenu juste (heures, charge, récréation, hors grille) ; PDF gardé relu sans nouvelle mise en page.

**Documents** : 05, 06, spec § 11, reference.md, A-FAIRE § 11, 07 § 1, maquettes/README, 03 (journal), 04 non (aucun modèle).

**Regard senior** : pas de champ « abréviation » saisi (noms courts calculés comme à l'écran, légende imprimée) ; pas de nouveau modèle ; lecture en 4 requêtes pour tout le document (séances, grilles, cours, profils), jamais par page.

**Risques** : séance hors grille (grille changée), séance sur une récréation, cours en parallèle (groupes) dans une case, grilles différentes selon la classe.
