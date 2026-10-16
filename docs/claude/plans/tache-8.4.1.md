# Tâche 8.4.1 — Règles de réussite et repêchage (#294)

**But** : règles de réussite réglables par école (`School.settings["pass_rules"]`), cours échoués et issue proposée calculés d'après les notes de l'année, note de repêchage de chaque cours échoué saisie et signée par l'enseignant du cours.

**Choix (regard senior)** : rien de stocké que la note de repêchage (`ResitGrade` : élève, cours, pourcentage, signataire) ; cours échoués et issue se calculent à la demande avec le bulletin de la classe (une lecture, pas de N+1), comme l'Application. La note est un pourcentage 0-100 (le maximum du cours varie selon les périodes). Signature = nom du signataire et journal ; l'impression de la colonne du bulletin et la décision prise sont en 8.4.2 / 8.4.x.

**Ajout du 2026-10-16** (demande de l'utilisateur) : règles **par niveau** (`Level.pass_rules` sur celles de l'école), « repêchés au plus » (`max_resit_courses`), cours sans seconde session (`Course.resit_allowed`, atelier/labo). Section de classe : non, le niveau suffit.

**Hors périmètre** : décision de délibération (8.4.2), impression de la note sur le bulletin, signature manuscrite (image).

**Critères d'acceptation**
- Carte « Réussite et repêchage » des paramètres : réussite 50 %, cours échoué sous 50 %, repêchage de 45 % (ou tout cours échoué), 2 cours échoués au repêchage = échec (départ, I16 à confirmer).
- Écran « Repêchage » : élèves ayant un cours échoué, note saisie par l'enseignant du cours, issue proposée (admis, repêchage, échec, notes manquantes).

**Tests obligatoires** : règles (bande, tout cours, plancher refusé), droits (autre enseignant 403, cours d'un autre), cours non éligible 400, journal, isolation entre écoles.

**Documents** : `04`, `03`, `05`, `06`, `07` (I16, § 1, § 4), `reference.md`, `maquettes/README.md`.

**Risques** : seuil « à partir de N » (et non « plus que N ») ; élève sans cours échoué absent du tableau.
