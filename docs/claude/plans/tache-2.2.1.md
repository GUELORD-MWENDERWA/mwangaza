# Tâche 2.2.1 — Liste des élèves et « Inscrire un élève »

**Serveur**
- `HasSchoolPermission` : `required_permission` peut être une liste (un des droits suffit). Années, options et classes (liste, détail) lisibles avec `students.view` **ou** `classes.manage` ; écritures, niveaux, titulaires possibles, matricule : `classes.manage` seul.
- Recherche sans accents ni casse : extension PostgreSQL `unaccent` (`django.contrib.postgres`, déjà dans Django, pas de dépendance), élèves et familles.
- Liste des élèves : tuteur principal (nom, téléphone) ; filtres `track` et `status` (`active`, `left`, `not_enrolled`) à la place de `enrolled`.

**Front** (`features/students/`) : `StudentsPage` (recherche, filtres année / classe / option / statut, pagination), `NewStudentPage` sur `/app/students/new` (`students.edit`) : identité, adresse, classe (effectif / capacité), famille existante (recherche) ou nouvelle (tuteurs) ; doublon 409 → confirmation → `allow_duplicate` ; élève puis inscription, chacun avec un UUID v7 (renvoi sans doublon). Après l'enregistrement : retour à la liste avec le matricule et le code famille.

**Hors de cette tâche** : ouvrir une fiche, photo, recherche `Ctrl K` → 2.2.2 ; import → 2.3 ; export, sélection → 2.4 ; frais appliqués → 2.6 ; colonnes « Échu non payé », « Paiements » → 2.7 ; hors-ligne → 3.x.

**Tests** : lecture années / classes / options avec `students.view` (caissier oui, enseignant non, écriture refusée) ; recherche sans accents ; filtres statut et option ; option d'une autre école refusée. Front : liste (recherche, filtres) ; formulaire (nouvelle famille, famille existante, doublon confirmé, erreur traduite).

**Risque** : `unaccent` doit exister sur la base de production (extension standard de PostgreSQL, « trusted » depuis la 13).
