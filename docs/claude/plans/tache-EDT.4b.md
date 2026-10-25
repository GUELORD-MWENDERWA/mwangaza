# Tâche EDT.4b — Lecture de l'horaire publié (issue #383)

**But** : l'horaire publié se lit là où on en a besoin — « Mon horaire » de l'enseignant dans la Gestion (ses cours et sa classe de titulaire), même sans réseau ; l'horaire de la classe de l'enfant dans le Portail ; une notification par personne quand une publication change ses heures.

**Hors périmètre** : impressions (EDT.4c), abréviations des cours (EDT.4c), heures prestées et remplacements (EDT.6), horaire des examens (EDT.5).

**Critères d'acceptation**
- `timetable/schedule.py` : séances de la version publiée de l'année en cours, avec début et fin d'après la grille de la classe ; quelques requêtes, quel que soit le nombre de séances.
- `GET /api/timetable/mine/` (tout compte de l'école, module `timetable`) : ses séances + celles de la classe dont il est titulaire. `GET /api/portal/children/<id>/timetable/` : séances de la classe de l'enfant (404 sinon).
- Publier notifie, regroupé en une seule par personne : les enseignants dont les séances changent (Gestion, « Mon horaire ») et les parents des classes touchées (Portail, page de l'enfant) ; nouvelle sorte `timetable_published`, coupable dans les préférences.
- Gestion : menu « Mon horaire » (`grades.enter` ou `grades.enter_any`, module `timetable`), lu en ligne puis gardé sur l'appareil (table Dexie `reads`), lu à l'ouverture de l'application ; hors ligne : la copie gardée avec sa date.
- Portail : carte « Horaire de la classe » (un jour à la fois, aujourd'hui d'abord), gardée par le service worker comme le reste du portail.

**Regard senior** : pas d'ajout à l'instantané ni au `ChangeLog` (une écriture par publication et par appareil pour rien) : la dernière lecture en ligne est gardée, comme les notes (8.2.3), et relue à chaque ouverture de l'application. Notification dans la transaction de publication (`bulk_create`, une par personne ; l'envoi sur l'écran part déjà par lots de 200).

**Tests obligatoires** : isolation (école B ne lit pas l'horaire de A, ni par « mine » ni par le portail), parent d'une autre famille → 404, permission (module coupé → 403), séances de l'enseignant seulement, notification : une seule par personne, seulement aux touchés, rien pour un horaire identique ; vitest de la lecture gardée ; `test_demo.py` : l'enseignant de démo a des séances.

**Documents** : `04` (sorte de notification), `03` journal, `05`, `06`, `07` § 1, `maquettes/README.md` + 2 maquettes (`gestion/mon-horaire.html`, `portail/enfant-horaire.html`), `reference.md` et `A-FAIRE.md` § 11 (API, écran), skill `hors-ligne` (table `reads`).

**Risques** : enseignant dans deux grilles (vacations) → liste par jour triée par heure, pas de tableau commun ; version publiée en vigueur plus tard → la dire ; migration du choix `kind`.
