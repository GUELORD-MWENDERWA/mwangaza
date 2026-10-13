# Plan M.3.2 — Rôles entièrement libres (issue #224)

**But** : plus de rôle système ni de code de rôle. Un rôle = un nom (obligatoire, unique dans l'école) et des permissions ; tous se renomment, se modifient et se suppriment (s'ils ne sont donnés à personne).

**Hors périmètre** : écran de la console pour modifier le modèle de départ ; choix des rôles dans le formulaire de création d'une école ; notification quand un compte reçoit `roles.manage` (S.3).

**Décisions (regard senior)**
- Modèle de départ : les 9 rôles actuels, dans le code (`accounts/roles.py`, `STARTER_ROLES`), copiés une fois à la création de l'école comme rôles ordinaires que l'école modifie ensuite. Pas d'éditeur dans la console : neuf lignes qui changent rarement, et l'école les ajuste en deux minutes.
- Nom des rôles copiés : dans la langue par défaut de la plateforme (français), pas celle de celui qui crée l'école (résultat toujours le même).
- La clé du modèle (`head`, `cashier`…) reste dans le code pour que `make demo` et les tests désignent un rôle de départ ; rien en base ni dans l'API.
- Migration : un rôle système sans nom propre reçoit le nom que l'école voyait (« Directeur », « Caissier »…), « (2) » si ce nom est déjà pris.
- Journal : les anciennes entrées notent un rôle par son code, sans nom, et ne se modifient pas ; le serveur donne le nom d'aujourd'hui (par identifiant), « Rôle supprimé » sinon.
- Garde-fou : déjà en place (`_keeping_a_role_manager` : permissions d'un rôle, rôles et désactivation d'une personne) ; la suppression est couverte par « rôle encore donné ». Vérifié par un test, pas de nouveau code.

**Critères d'acceptation** : `Role.code` et `is_system` n'existent plus (modèle, API, front) ; un ancien rôle système se renomme et se supprime ; école neuve = 9 rôles nommés ; rien ne change à l'écran pour une école existante, sauf la mention « prédéfini / personnalisé » retirée.

**Tests obligatoires** : migration (noms, doublon) ; modèle de départ comparé à `04` § 8 et contenant `roles.manage` ; nom obligatoire et unique ; suppression d'un ancien rôle système, refusée s'il est donné ; dernier gestionnaire des rôles gardé ; isolation (existants) ; journal : ancienne entrée lisible ; `make demo` : noms de l'école fictive.

**Documents** : `05`, `06`, `02` (B1), `03` (journal des décisions), `04` (Role, § 8), `07` § 4, `reference.md`, `A-FAIRE.md` § 11, `maquettes/README.md`, skill `backend`, guide de présentation si un nom de rôle y figure.

**Risques** : 46 fichiers de tests passent une clé de rôle à `MembershipFactory` (gardée, résolue par le nom de départ) ; `make api` et `make messages` ; test de `make demo` lent (un seul avec `-k`).
