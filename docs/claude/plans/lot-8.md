# Lot 8 — Cours communs et notes

**But** : un cours commun à plusieurs classes (tronc commun) a un seul enseignant et une seule fiche de cotes ; un remplaçant peut saisir quand l'enseignant manque ; l'école importe les points depuis Excel ; la conduite se saisit sans réseau.
Tâches : 8.1.2a (#309), 8.1.2b (#310), 8.2.5 (#311), 8.2.4 (#303), HL.2 (#340).

## Parties (une conversation chacune)
- [x] ① Maquettes du lot (cours communs, remplaçant, import Excel) ; 8.1.2a serveur : `CourseGroup`, `Course.course_group`, un enseignant propagé aux cours du groupe, API, audit, démo, tests (isolation, groupe de classes d'une autre école) — **Opus**
- [x] ② 8.1.2a écran « Cours communs » (créer pour un niveau, sortir une classe) + fiche de cotes commune (une page, toutes les classes) — Sonnet
- [x] ③ 8.1.2b charges horaires par groupe, repêchage et délibération inchangés, règle `joint_courses` alimentée par le groupe (un créneau) — **Opus**
- [x] ④ 8.2.5 serveur : `CourseSubstitute`, accès restreint (total + examen, après envoi), correction avec motif, notification du propriétaire — **Opus**
- [x] ⑤ 8.2.5 écran « Remplaçant » + 8.2.4 import Excel des points (modèle, erreurs par ligne, confirmation) — Sonnet
- [x] ⑥ HL.2 conduite et discipline hors ligne (Dexie, file, synchro idempotente, Playwright réseau coupé) — **Opus**
- [x] ⑦ Fin du lot : définition de « fini », `/verifier`, tous les `.md`, articles d'aide, PR — fait dans la conversation de ⑥ (2026-11-05, demandé : pas d'attente)

## Décisions (regard senior)
- Les notes restent par cours de classe (`Grade` → `Evaluation` → `Course`) : les bulletins, le repêchage et la délibération ne changent pas. Le groupe ne stocke que le lien et l'enseignant ; la fiche commune lit et écrit les fiches de chaque classe en une page (un envoi par classe, atomique).
- Évaluations d'un groupe : mêmes noms et mêmes maxima dans chaque classe ; la note de la période est ramenée au maximum de la classe (`period_max`), donc des maxima différents ne gênent pas.
- Un cours n'est que dans un seul groupe ; le groupe porte l'enseignant, les cours le reprennent (une seule source, propagée dans la même transaction).
- Remplaçant : désigné par le directeur des études seul, jamais d'accès aux devoirs ni interrogations (comme NB.1).
- ② fait sans nouvel endpoint : la fiche commune (`grades/joint`, `joint.ts`) lit et enregistre la feuille de chaque classe (même file hors ligne) ; colonnes réunies par nom. Démo : mathématique des 1HT Électricité A et B de `0000001008`. Écart à la maquette : pas de « Voir la fiche de cotes » côté direction (la fiche est celle de l'enseignant). Pour ⑦ : `maquettes/README.md`, `07` § 1 et § 4, `reference.md` (`/courses/joint`, `/grades/joint`, `course_group` de `/api/grading/`).
- ③ : un `CourseGroup` est un cours commun de l'horaire sans règle à écrire (`checks._course_groups`, lu sur les cours déjà chargés) ; un cours n'est jamais à la fois dans un groupe et dans une règle de groupe (409 `course_grouped`, 400 `timetable_grouped`) ; charge et heures sans enseignant comptent le groupe une fois (`courses.weekly_hours`), écran « Charges » : une ligne « commun ». Corrigé : messages d'erreur des cours communs (rendus bruts, jamais traduits). Pour ⑦ : `04`, spec EDT § 4, `reference.md` (`course_group` de `/api/teaching-loads/`).
- ④ : `CourseSubstitute` (un cours, ou le cours commun entier ; motif, fin facultative comprise ; un seul en cours par cours, une désignation échue est remplacée), `grades.validate` seul (`/api/course-substitutes/`), journal et notification `course_teacher` au remplaçant et à l'enseignant. Le remplaçant a l'accès « total » (`replacing` dans `/api/grading/`) ; une feuille commencée par un autre lui reste fermée tant qu'elle n'est pas envoyée (403 `sheet_with_teacher`, en ligne **et hors ligne** : `grades.limited_to_totals`) ; une feuille vide (examens) il la saisit et la signe. Toute note saisie par un autre, changée par qui n'est pas l'enseignant : motif même en brouillon (400 `reason_required`) ; motif au journal et dans la notification `grades_corrected`. Pour ⑤ : ouvrir la boîte du motif sur `reason_required` et « remplacement » dans « Mes cours ». Pour ⑦ : `04`, `reference.md`, À valider (feuille vide ouverte au remplaçant).
- ⑤ : écran « Remplaçants » (`/grade-validation/substitutes`, lien depuis « À valider » ; personnes possibles : `/api/course-substitutes/candidates/`, classes et cours lus dans `/api/grading/validation/`) ; « Mes notes » : « · remplacement » dans le choix du cours, bandeau, fiche encore chez l'enseignant, boîte du motif sur `reason_required` (genre `correct`). Import (8.2.4) : `GET/POST /api/courses/<id>/terms/<t>/grades/import/` (modèle protégé, notes remplies ; contrôle sans écriture, élève par matricule ou nom exact, case vide = rien) ; l'écran enregistre par la saisie (`sendSave` : file hors ligne, motif, journal) ; `/grades/import`. Pour ⑦ : `reference.md`, `07` § 1, `maquettes/README.md`, aide (2 articles), À valider (case vide ne vide pas la note).
- ⑥ HL.2 : seule l'attribution d'une infraction marche sans réseau (opération `incident.record`, identifiant de l'appareil, aussi accepté par `POST /api/discipline/incidents/` : réponse perdue puis file = un seul incident ; rejouée après l'effacement de sa trace : rien de plus). Classes, infractions, élèves d'une classe et historique d'un élève lus en ligne restent sur l'appareil (`db.reads`, `conduct/offline.ts`) ; une classe jamais ouverte en ligne : « Pas de réseau ». Annuler et corriger une cote restent en ligne (décisions rares, au bureau ; deux appareils se contrediraient) : à valider. `/api/sync/` ouvert à `discipline.record`. Maquette `conduite-hors-ligne`. Pour ⑦ : `reference.md` (opération, `id`), `07` § 1, `maquettes/README.md`, `04`, `03` (journal), aide, À valider.

- 2026-11-06 (méthode) : plus de capture pendant les parties ; toutes les captures du lot (cours communs, fiche commune, charges, remplaçants, import) en une passe à ⑦. Lots suivants : 3 parties au plus.

## Hors périmètre
Notes par élève communes à deux classes, bulletin commun, emploi du temps calculé (lot 9).

## Critères d'acceptation
Un groupe de 3 classes : un enseignant, une fiche, notes au bon élève et au bon cours ; sortir une classe garde ses notes ; remplaçant sans accès aux devoirs ; import refusé en bloc si une ligne est fausse ; conduite saisie hors ligne puis synchronisée sans doublon.

## Tests obligatoires
Isolation entre écoles (groupe, remplaçant, import, conduite) ; permissions (403) ; audit des corrections par un autre ; idempotence de la synchro HL.2.

## Documents à mettre à jour
`05`, `06`, `03` (journal), `04` (CourseGroup, CourseSubstitute), `07`, `reference.md`, `A-FAIRE.md` § 11, `maquettes/README.md`, aide en ligne.

## Risques
`import_cancellation.py` (nouvelle clé vers élèves : aucune ici) ; `courses.set_courses` écrase la grille : il doit garder `course_group`.
