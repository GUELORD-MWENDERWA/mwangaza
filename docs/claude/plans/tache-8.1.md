# Tâche 8.1 — Cours, maxima, domaines, enseignants et charges horaires

**But** : chaque classe a sa grille de cours (branche, domaine, maximum par période, avec ou sans examen, heures par semaine, enseignant), enregistrée d'un seul bloc par un service (`academics/courses.py:set_courses`, que l'IA.5 réutilisera) ; copie vers d'autres classes ; modèles officiels (IGE/P.S/005, /100, /094, Électronique 1re–2e) ; charge horaire de chaque enseignant. Nouvelle app `academics` (cours, puis notes, bulletins, délibération), module `academics`, droit `courses.configure`.

**Hors périmètre** : notes et verrouillage d'un maximum déjà noté (8.2), bulletin et ses regroupements imprimés (8.3), charge maximale et disponibilités des enseignants (EDT.1), proposition depuis un PDF (IA.5).

**Regard senior** : pas de catalogue de matières à part (le nom fait le lien entre classes, la copie garde les noms) ; domaine = simple texte ; examen = 2 × période et T.G. calculé depuis le découpage de l'année, jamais stocké ; pas de regroupement par maximum dans l'éditeur (les lignes sauteraient pendant la saisie) : résumé dans la carte « Contrôle » ; une nouvelle année « avec les classes » reprend aussi leurs cours (sinon 23 grilles à refaire chaque année) ; charges = une requête groupée, tout le personnel actif (sert aussi de liste des enseignants possibles).

**Critères d'acceptation** : `GET/PUT /api/class-groups/<id>/courses/`, `POST …/courses/copy/`, `GET /api/teaching-loads/`, `GET /api/course-templates/` ; écrans `/app/courses` et `/app/teaching-loads` ; `make demo` remplit les grilles ITIG et Volcans avec quelques enseignants ; droit donné au directeur et au directeur des études (et aux rôles existants qui ont `classes.manage`).

**Tests obligatoires** : isolation (classe, copie, enseignant et charges d'une autre école), 403 sans droit et sans module, remplacement d'une grille (ids gardés, doublons refusés, audit seulement si changement), copie, charges, copie des cours à la création d'année ; Vitest : totaux T.G. selon le découpage.

**Documents** : `04` (§ 2 bis Cours, § 8), `03` journal, `05`, `06`, `07` § 1 et § 4, `reference.md`, `A-FAIRE.md` § 11, `CLAUDE.md` (apps), skill `backend`, `maquettes/README.md` (+ maquette « Charges des enseignants »).

**Risques** : migrations des choix (permissions, modules) ; RLS posée seule (`post_migrate`) ; lecture des classes avec `courses.configure` ; durée de `make demo` (écritures groupées par classe).
