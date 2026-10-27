# EDT.5a — Horaire des interrogations et des examens : serveur (issue #397)

**But** : le directeur des études fixe, pour une période ou les examens, les épreuves de chaque classe (cours, jour, heures, salle, surveillant), voit les conflits, puis publie.
**Découpage** (taille : modèle + contrôles + publication + écran + PDF ne tiennent pas dans une PR) : 5a serveur (ici), 5b écran + impression + lecture (#398, maquette dessinée d'abord).
**Modèle** (`timetable/exams.py`) : `ExamSchedule` [T] (une par période, `status` brouillon/publié, `published_at/by`) et `ExamSitting` [T] (`schedule`, `course`, `kind` interrogation/examen, `date`, `start`, `end`, `room`, `invigilator`). Pas de clé vers `Evaluation` (la note se saisit à part, 8.2).
**Contrôles** (rouge, bloquent la publication) : une classe a deux épreuves qui se chevauchent ; un surveillant (ou la salle) à deux endroits ; date hors des dates de la période ; fin avant début. Orange : surveillant absent ce jour (disponibilité EDT.1b), épreuve sur un jour férié du calendrier.
**API** : `GET/POST /api/timetable/exams/<période>/`, `PATCH/DELETE …/exams/sittings/<id>/`, `POST/DELETE …/exams/<période>/publish/` (publier / rouvrir, droit publish).
**Hors périmètre** : écran, PDF, lecture enseignants/Portail, notification (5b). Pas d'auto-placement par le solveur (le DE place à la main, comme dit au plan).
**Tests** : isolation entre écoles (lecture, écriture, publication) ; 403 sans droit ; chaque contrôle rouge ; publication refusée avec du rouge, puis acceptée, journal écrit ; épreuve modifiable seulement en brouillon.
**Documents** : `04`, `05`, `06`, `03` (journal), spec § 13, `reference.md`, `make demo` (épreuves de la 1re période de l'ITIG) + `07` § 4, `A-FAIRE.md` § 11.
**Risques** : requêtes du rapport en nombre constant (une requête par table), pas de N+1 ; `make demo` : ajouter au scénario de `test_demo.py`.
