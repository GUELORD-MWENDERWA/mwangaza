# Tâche 4.20.1 — Liste « Mise en route » d'une école neuve (C4)

Issue #163 · branche `tache/4.20.1-mise-en-route`. La 4.20 est découpée : états vides et parcours Playwright « école neuve » → 4.20.2 (#179).

## Serveur (`apps/schools/setup.py`)
- `School.setup_completed_at` (migration : les espaces de démonstration existants sont marqués finis) ; `setup_done` dans `/api/school/` : une école qui a fini ne demande plus jamais la liste.
- `GET /api/school/setup/` (`school.configure`) : 8 étapes, chacune un `exists()` sur l'école — année en cours, classes, barèmes (et taux si deux devises), compte qui peut encaisser, caisse et appareil d'un caissier, élèves inscrits, puis facultatives : reprise, invitation des parents.
- `POST /api/school/setup/finish/` : garde la date ; refusé (409 `setup_incomplete`) tant qu'une étape obligatoire manque ; rejouable sans effet.
- Espaces de démonstration (`make demo`, console) : créés déjà finis.

## Front (`features/dashboard/SetupChecklist.tsx`)
- Carte en haut du tableau de bord si `!school.setup_done` et `school.configure` ; chaque étape mène à son écran ; « Terminer la mise en route » quand l'école peut encaisser. Maquette `gestion/mise-en-route.html` (d'après `tableau-de-bord`).

## Tests
- `schools/tests/test_setup.py` : isolation (les données d'une autre école ne cochent rien), 403 sans `school.configure`, étapes cochées une à une, fin refusée puis gardée, plus aucun calcul ensuite.
- Vitest : la carte, cachée quand c'est fini ou sans la permission.

## Regard senior
- Pas d'écriture pendant une lecture : le directeur termine la liste (une écriture dans la vie de l'école). Reprise et invitations facultatives : sinon la liste d'une école qui démarre à la rentrée ne finirait jamais.
- Pas de journal d'audit : ni argent, ni rôles. Pas de nouveau modèle, rien dans la synchronisation.
