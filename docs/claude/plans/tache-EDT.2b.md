# Tâche EDT.2b — Éditeur de l'horaire : vues par enseignant, par salle, horaire général (#375)

**But** : le même brouillon et les mêmes gestes, vus autrement dans `/timetable` (onglets Classe · Enseignant · Salle · Général), spec § 8.

**Hors périmètre** : impression de l'horaire général (EDT.4), calcul (EDT.3), publication (EDT.4).

**Décisions (regard senior)** :
- Ni API ni requête de plus : l'état du brouillon a déjà toutes les séances, les charges des enseignants (placées / dues / maximum) et les conflits ; les absences viennent de `/api/timetable/teachers/` (existant). Le serveur ne change pas.
- Vues enseignant et salle : la grille de la vue par classe (même composant), sur la grille la plus fréquente de leurs classes ; si leurs classes ont des grilles différentes, un avertissement (séances rangées par numéro d'heure).
- Vue enseignant : cases « Absent » ; pendant un choix, la teinte dit aussi « enseignant absent » (toutes les vues).
- « À placer » : enseignant → ses cours ; salle → les cours dont c'est la salle par défaut.
- Horaire général : classes en lignes, heures en colonnes ; ordinateur : la semaine en noms courts (calculés, distincts dans l'école) ou un jour en clair ; téléphone : un jour. Toucher une séance : même fenêtre ; glisser : dans la ligne de sa classe. Pas d'« À placer » (des centaines à l'ITIG) : heures placées / dues sur chaque ligne, le nom de la classe ouvre sa vue.
- Téléphone : une séance qui commence pendant une autre (conflit, groupes) s'affiche (elle était cachée).

**Critères d'acceptation** : maquettes `emploi-du-temps-enseignant.html` (salle : même page) et `emploi-du-temps-general.html` à 390 et 1440 px ; vue gardée dans l'adresse (`view`, `teacher`, `room`) ; écran comparé à 390 et 1440 px.

**Tests obligatoires** : Vitest : noms courts distincts, grille d'un enseignant, teinte « absent ». Aucun test serveur nouveau : rien n'y change (isolation et 403 des brouillons déjà couverts).

**Documents** : spec § 8, `05`, `06`, `07` § 1, `maquettes/README.md`, `reference.md`, `A-FAIRE.md` § 11, `03` journal.

**Risques** : ≈ 30 classes × 42 cases à l'ITIG (≈ 1 300 éléments) ; `EditorPage.tsx` a déjà 1 030 lignes → vues dans des fichiers à part.
