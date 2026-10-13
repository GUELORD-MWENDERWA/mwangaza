# Tâche M.1 — Modules d'une école

- Catalogue `accounts/modules.py` : `students`, `finance`, `communication` (chacun liste ses permissions) ; socle toujours actif : `school.configure`, `classes.manage`, `roles.manage`, `audit.view`.
- `School.modules` (ArrayField, vide par défaut) ; migration 0012 : écoles existantes → tous les modules. Espaces de démonstration (`open_space`, `make demo`) et `SchoolFactory` : tous.
- Application : un seul point, `get_school_access` (+ session support) retire les permissions d'un module absent → 403 partout, `/api/me/` ne les renvoie plus. Aucune donnée supprimée.
- Console : `modules` dans l'API des écoles (PATCH, journal de la plateforme) et carte « Fonctions de l'école » sur la fiche.
- Tests : module absent = 403 puis retour, seul le super-admin les donne, école voisine intacte, journal ; 1 test écran.
- Regard senior : pas de module `portal` / `notifications` / `offline` dans M.1 (ils n'ont pas de permission : leur blocage est dans M.2, avec le front) ; pas de table de liaison : 3 codes dans une liste suffisent.
- Reste pour M.2 : menu piloté par `/me`, message « Aucun module », portail, synchro, relances et notifications qui ignorent les écoles sans le module, création d'école avec ses modules.
- Risque : une école neuve sans module ne peut rien faire jusqu'à ce que la plateforme coche ses modules (voulu).
