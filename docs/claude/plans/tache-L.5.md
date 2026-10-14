# Tâche L.5 — Clôture de la version (lancement)

**But** : déclarer prête la version du lancement : guide de la version et guide de présentation à jour (modules, rôles libres, sécurité S.1 à S.5, versions à venir du plan du 2026-10-13), PDF régénérés par `make guide`, « Le jour du lancement » d'`A-FAIRE.md` relu avec `mwangazaschool.com`.

**Hors périmètre** : L.4 (vrais téléphones, 👤) ; aucun code applicatif ; numéro de version inchangé (1.1, la tâche dit `guide-v1.1.pdf`).

**Critères d'acceptation**
- Guide : modules (console, menus, « Aucun module activé »), rôles = un nom + des permissions (modèle de départ), double authentification déduite des droits, sécurité du lancement (fichiers envoyés, compte super-admin, base), tableau des versions 1.2 à 1.7 et V2 du plan actuel.
- Présentation : comptes d'un espace de la console (bloc `000BB0xxxx`, mot de passe de la fiche d'accès), modules montrés dans la console, versions et réponses à jour.
- Nouvelle capture `console-modules` (carte « Fonctions de l'école ») ; `make guide` vert, deux PDF régénérés.
- `A-FAIRE.md` § 9, § 9 ter, § 9 quater et « Maintenant » : cases faites cochées (L.1, L.2, 4.7.2), ancienne IP remplacée, ordre du jour du lancement juste.

**Tests obligatoires** : aucun test ajouté (documents) ; `make guide` vérifie que chaque capture existe.

**Documents à mettre à jour** : `frontend/guide/*.html`, `captures.spec.ts`, `A-FAIRE.md`, `05`, `06`, `07` § 2 (I5 si cité).

**Risques** : `make guide` relance `make demo` (lourd sur 8 Go : rien d'autre en même temps) ; une capture prise avant la fin du chargement.
