# Tâche EQ.2 — Équipe de la plateforme : écrans de la console

**But** : maquette `console/equipe` puis écran `/team` (membres, rôles, double authentification, dernière connexion ou invitation en attente ; inviter avec mot de passe provisoire montré une fois ; changer les rôles ; retirer) ; carte « Rôles et droits » (lue sur `team/roles/`). Menu de la console réduit aux droits de `me.platform_permissions` (une table entrée → droits, partagée par le menu, la garde des pages et l'accueil : sans `schools.view`, « / » mène à la première page permise) ; page sans droit : message, pas d'erreur 403 brute. Boutons d'une fiche d'école masqués sans le droit (modifier, suspendre, arrêter, supprimer, fonctions). « Arrêter » une école : motif **et** code retapé, vérifié aussi par le serveur (`confirm`, comme `delete/`).

**Hors périmètre** : contenus du site (SITE), abonnements (ABO), journal propre à l'équipe (déjà dans le journal de la plateforme).

**Critères d'acceptation** : chaque rôle ne voit que ses entrées ; « Équipe » au propriétaire seul ; arrêt refusé sans le bon code (400 `wrong_code`) ; écran juste à 390 et 1440 px.

**Tests obligatoires** : serveur — arrêt sans le code ou avec un mauvais code refusé, école intacte ; front — menu selon les droits (commercial, communication), garde d'une page sans droit, invitation (mot de passe montré), retrait confirmé, `last_owner` affiché.

**Documents** : 05, 06, 03 (journal des décisions), `reference.md` et `A-FAIRE.md` § 11 (`/team`, `stop/` + `confirm`), 07 § 1, `maquettes/README.md`, index des maquettes.

**Risques** : tests existants qui appellent `stop/` sans `confirm` ; clés i18n en fr et en en ; menu sur téléphone (défilement horizontal).

**Regard senior** : pas de page de détail d'un membre (tout tient dans la liste et deux fenêtres) ; retrait par une confirmation simple (réinviter le rattrape), le code retapé reste aux actions sans retour (arrêt, suppression, remise à zéro) ; aucune requête de plus : les droits viennent de `me`, déjà chargé.
