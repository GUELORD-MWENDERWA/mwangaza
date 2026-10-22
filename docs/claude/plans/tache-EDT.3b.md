# Tâche EDT.3b — Écran du calcul de l'horaire

Suite d'EDT.3a (#380, API `/api/timetable/runs/`). Spec : `docs/specs/emploi-du-temps.md` § 7. Issue #379.

- **But** : page « Calcul de l'horaire » (`/timetable/calculate`, sans entrée de menu : bouton « Calculer » de l'éditeur et de « Règles et contrôles ») : brouillon de départ, portée (tout, une classe, un enseignant), temps ; « Calculer » grisé tant que les contrôles ont du rouge (lien vers eux) ; suivi de l'état (attente, en cours avec le temps écoulé), annulation ; résultat : souhaits non tenus, règles qui bloquent en phrases avec le bouton de l'écran qui corrige, « Ouvrir le brouillon calculé » ; les 10 derniers calculs. Console : temps de calcul au plus, **par école** (carte des modules, sous « Emploi du temps » : 30 s, 1 min par défaut, 2 min, 3 min).
- **Serveur** : `School.timetable_max_seconds` (10 à 180, 60 par défaut) ; la demande est ramenée à ce maximum ; `GET …/runs/` rend `{time_limit_max, runs}` (tout ce que l'écran demande en une requête).
- **Hors périmètre** : publication (EDT.4), IA (IA.2b), progression en % (CP-SAT ne la donne pas : temps écoulé sur temps donné).
- **Critères** : maquette dessinée puis écran à 390 et 1440 px ; un calcul suivi jusqu'au bout sans recharger ; chaque code de blocage (rule, absence, teacher_day, course_day, no_gaps, locks, frozen, unit) a sa phrase et son lien.
- **Tests** : serveur — temps ramené au maximum de l'école ; le maximum réglable par la console seulement (l'école ne peut pas) ; liste rendue avec le maximum ; isolation et 403 déjà couverts en EDT.3a. Front — phrases de blocage (Vitest, fonction pure).
- **Regard senior** : un réglage par école plutôt que pour la plateforme (une grande école a besoin de plus, le serveur reste protégé par défaut) ; suivi par interrogation toutes les 2 s seulement pendant un calcul (pas de WebSocket) ; pas de confirmation pour lancer, une pour annuler.
- **Documents** : spec § 7, `04` (champ), `03` journal, `05`, `06`, `07` § 1, `maquettes/README.md`, `reference.md`, `A-FAIRE.md` § 11.
- **Risques** : import circulaire `schools` → `timetable` (constantes dans `timetable/limits.py`) ; `make api` après les docstrings.
