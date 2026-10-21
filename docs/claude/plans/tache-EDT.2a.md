# Tâche EDT.2a — Éditeur de l'horaire : brouillon, vue par classe, conflits (#374)

**But** : le DE ouvre un brouillon d'horaire, place les heures d'une classe à la main (glisser sur ordinateur, « Placer / Déplacer vers… » partout), échange, verrouille, change la salle, annule son dernier geste ; il voit tout de suite les conflits (mêmes contrôles qu'au § 6, rejoués par le serveur) et les heures placées / dues. Spec §§ 8, 10.

**Hors périmètre** : vues par enseignant, par salle, horaire général (EDT.2b, #375) ; calcul (EDT.3) ; publication, impressions, Portail (EDT.4) ; souhaits (règles `soft`) dans les conflits : c'est le calcul qui les pèse.

**Décisions (regard senior)** :
- Position d'une heure = (jour, numéro de la 1re heure, longueur), pas une clé vers `TimeSlot` : l'enregistrement d'une grille réécrit ses cases ; même forme que la règle `fixed_lesson`. Une heure devenue hors grille est un conflit, pas une perte.
- Historique des gestes : liste JSON sur `Timetable` (50 derniers), pas de table de plus. Une écriture par geste ; le brouillon est verrouillé (`select_for_update`) pendant le geste.
- Nouveau brouillon : vide avec les heures `fixed_lesson` déjà placées et verrouillées, ou copie d'un autre brouillon (`based_on`).
- Chaque geste renvoie l'état du brouillon (heures, conflits, placées / dues) ; les cours de l'année se lisent une fois. Avant de lâcher une heure, l'écran teinte les cases libres ou en conflit (classe, enseignant, salle) d'après les heures déjà chargées.
- Salle : celle du cours, sinon celle de la classe ; type exigé sans salle choisie → « salle à choisir » (le calcul choisira en EDT.3).
- Journal : brouillon créé ou supprimé, verrou posé ou retiré (spec § 10).

**Critères d'acceptation** : maquette `emploi-du-temps-classe.html` (390, 1440) ; écran `/timetable` ; conflits O1–O3, O5–O7, au plus par jour (cours, enseignant), charge de la semaine, cours dont les séances ont changé ; verrou non déplaçable ; « Annuler » ; `make demo` : un brouillon de l'ITIG avec ses verrous et une classe placée.

**Tests obligatoires** : isolation (brouillon et heures d'une autre école : 404, absents des listes) ; 403 sans `timetable.manage` ; règles du service (hors grille, récréation, séance non due, verrou) ; conflits sur un cas écrit à la main ; annuler ; journal ; nombre de requêtes d'un geste borné.

**Documents** : `04`, spec § 13, `03` journal des décisions, `05` (découpage), `06`, `07` §§ 1 et 4, `maquettes/README.md`, `reference.md`, `A-FAIRE.md` § 11, recherche `docs/claude/recherches/edt-editeurs.md`.

**Risques** : taille de la réponse d'un geste sur l'ITIG (≈ 600 heures) à mesurer ; refonte de `checks._lock_conflicts` sans casser les contrôles 6–7 (tests existants).
