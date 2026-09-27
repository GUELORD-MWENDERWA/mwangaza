# Tâche 2.1 — App `students`

1. Modèles [T] dans `apps/students` : `Family` (code 8 caractères sans ambiguïté, unique sur la plateforme), `Guardian`, `Student` (identité V1.0, **matricule sur l'élève**, unique dans l'école, gardé toute la scolarité — décision de l'utilisateur du 2026-09-27), `Enrollment` (une par élève et par année, classe `PROTECT`, statut), `MatriculeSequence` (compteur par école et par année, verrouillé `select_for_update`).
2. Services `apps/students/services.py` : créer / modifier famille (tuteurs remplacés d'un envoi), élève, inscription (matricule donné à la première inscription : `{AAAA}` = année scolaire, `{OPT}` = option de la classe) ; audit domaine `students` ; doublon potentiel = avertissement.
3. API : `/api/students/` (liste paginée, recherche nom / matricule, filtres année / classe ; création avec `id` client idempotente ; fiche ; modification), `/api/families/` (recherche code / tuteur, création, fiche, modification), `/api/enrollments/` (création, changement de classe ou de statut). `students.view` en lecture, `students.edit` en écriture.
4. `schools` : « Prochain matricule » réel ; `student_count` (inscriptions actives) dans les classes et dans la liste des écoles de l'administration (A2) ; classe avec élèves protégée (409 `class_in_use` déjà en place).
5. Front : colonne « Effectif / capacité » (Organisation scolaire), colonne « Élèves » (liste des écoles), traductions des nouvelles actions du journal.
6. `make demo` : ~800 élèves ITIG avec familles et fratries, ~120 aux Volcans, inscrits dans les classes de 2026-2027.

Tests : isolation (liste, fiche, modification, recherche, famille d'une autre école), 403 sans droit, audit, matricule (séquence, format, gardé à la réinscription, concurrence simple), code famille unique, classe protégée.
Risque : taille (un module serveur complet) ; les écrans élèves restent en 2.2.
