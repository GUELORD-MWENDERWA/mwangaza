# Lot 8 — Cours communs et notes

**But** : un cours commun à plusieurs classes (tronc commun) a un seul enseignant et une seule fiche de cotes ; un remplaçant peut saisir quand l'enseignant manque ; l'école importe les points depuis Excel ; la conduite se saisit sans réseau.
Tâches : 8.1.2a (#309), 8.1.2b (#310), 8.2.5 (#311), 8.2.4 (#303), HL.2 (#340).

## Parties (une conversation chacune)
- [x] ① Maquettes du lot (cours communs, remplaçant, import Excel) ; 8.1.2a serveur : `CourseGroup`, `Course.course_group`, un enseignant propagé aux cours du groupe, API, audit, démo, tests (isolation, groupe de classes d'une autre école) — **Opus**
- [ ] ② 8.1.2a écran « Cours communs » (créer pour un niveau, sortir une classe) + fiche de cotes commune (une page, toutes les classes) — Sonnet
- [ ] ③ 8.1.2b charges horaires par groupe, repêchage et délibération inchangés, règle `joint_courses` alimentée par le groupe (un créneau) — **Opus**
- [ ] ④ 8.2.5 serveur : `CourseSubstitute`, accès restreint (total + examen, après envoi), correction avec motif, notification du propriétaire — **Opus**
- [ ] ⑤ 8.2.5 écran « Remplaçant » + 8.2.4 import Excel des points (modèle, erreurs par ligne, confirmation) — Sonnet
- [ ] ⑥ HL.2 conduite et discipline hors ligne (Dexie, file, synchro idempotente, Playwright réseau coupé) — **Opus**
- [ ] ⑦ Fin du lot : définition de « fini », `/verifier`, tous les `.md`, articles d'aide, PR — Sonnet

## Décisions (regard senior)
- Les notes restent par cours de classe (`Grade` → `Evaluation` → `Course`) : les bulletins, le repêchage et la délibération ne changent pas. Le groupe ne stocke que le lien et l'enseignant ; la fiche commune lit et écrit les fiches de chaque classe en une page (un envoi par classe, atomique).
- Évaluations d'un groupe : mêmes noms et mêmes maxima dans chaque classe ; la note de la période est ramenée au maximum de la classe (`period_max`), donc des maxima différents ne gênent pas.
- Un cours n'est que dans un seul groupe ; le groupe porte l'enseignant, les cours le reprennent (une seule source, propagée dans la même transaction).
- Remplaçant : désigné par le directeur des études seul, jamais d'accès aux devoirs ni interrogations (comme NB.1).
- HL.2 réutilise la file et Dexie de 8.2.3 (`grades/offline.ts`) : pas de nouveau mécanisme.

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
