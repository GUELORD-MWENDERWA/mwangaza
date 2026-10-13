# Plan M.3.1 — Rôles : droits déduits des permissions (issue #219)

**But** : plus aucune **décision** prise d'après un code de rôle ; après cette tâche, le code ne sert plus qu'à nommer un rôle système et à empêcher de le supprimer (retirés en M.3.2).

**Hors périmètre (M.3.2)** : champ `Role.code`, `is_system`, contraintes, nom traduit depuis le code (`people.ts`), rôles système remis à zéro par `make demo` (`accounts/demo.py`), modèle de départ modifiable.

**Décisions (regard senior)**
- Premier directeur : reçoit le premier rôle du modèle de départ qui a `roles.manage` (`accounts.first_manager_role`), pas le rôle de code `head`. Ce qui compte : que l'école puisse se régler.
- Guide de première connexion : comptable si le compte règle les frais (`finance.configure_fees`) sans régler l'école (`school.configure` : le directeur a la liste « Mise en route ») ; sinon caisse s'il encaisse (`finance.collect_payment`) ; sinon aucun. Même résultat qu'avant pour chacun des 9 rôles de départ.
- Écran des rôles : la note « parent » devient une note pour tout rôle sans aucune permission cochée.
- Journal : le serveur donne le nom du rôle de l'école quand l'entrée n'en a pas (`entity_label`) ; `role_code` quitte l'API ; une requête pour tous les rôles de la page au lieu d'une par rôle.
- Appareils fictifs (`sync/demo.py`) : portés par le compte fictif (`DemoAccount.device`), plus de requête `roles__code`.

**Critères d'acceptation** : `grep` ne trouve plus de code de rôle dans une décision (serveur et front) hors modèle, services de rôles et `accounts/demo.py` ; rien ne change à l'écran pour les 9 rôles de départ.

**Tests obligatoires** : directeur créé d'après la permission (modèle de départ modifié) ; guide avant / après pour chaque rôle de départ, et pour un rôle propre à l'école ; journal : nom du rôle de l'école, jamais celui d'une autre école.

**Documents** : `05`, `06`, `03` (journal des décisions), `04` § 8, `reference.md`, `maquettes/README.md` (note de l'écran des rôles).

**Risques** : `make api` après le changement du journal ; test de `make demo` lent (un seul avec `-k`).
