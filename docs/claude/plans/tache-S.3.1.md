# Tâche S.3.1 — Comptes à privilèges : journal, session courte, adresses autorisées, alerte de l'école

**But.** Rendre visible et limiter l'usage du compte super-admin, et prévenir une école quand quelqu'un y reçoit un droit sensible.

**Découpage (regard senior).** S.3 demandait aussi une notification *push* au super-admin : la console n'a ni centre de notifications ni service worker. C'est un chantier à part → **S.3.2**. Ici : tout ce qui est serveur.

**Hors périmètre.** Push dans la console (S.3.2). Champ « adresses autorisées » modifiable dans la console (voir Risques). Doublon de l'ouverture « en tant qu'école » dans le journal de la plateforme : elle est déjà au journal de l'école et dans « Sessions support » de la console.

**Critères d'acceptation.**
1. Journal de la plateforme : connexion d'un compte super-admin (`access.login`, avec l'adresse et le second facteur), code de double authentification refusé (`access.code_refused`), tentative depuis une adresse non autorisée (`access.address_refused`).
2. Session d'un super-admin fermée après 2 h sans activité, où qu'il soit connecté ; au plus une écriture toutes les 5 minutes.
3. `DJANGO_CONSOLE_ALLOWED_IPS` (adresses ou réseaux, vide = toutes) : hors liste, connexion refusée comme un mauvais mot de passe et session existante refusée (403).
4. École : notification `sensitive_rights` aux comptes qui ont `roles.manage` (auteur compris : son compte a pu être pris ; sauf l'intéressé) quand un compte reçoit `roles.manage` ou un droit `finance.*` (rôle donné, compte réactivé, rôle élargi) ; elle ne se coupe pas dans les préférences.

**Tests obligatoires.** Journal écrit pour le super-admin et pas pour le personnel d'une école ; session 2 h et prolongation ; liste d'adresses (vide, dedans, dehors, réseau) ; alerte : bonne école seulement (isolation), auteur prévenu, rien sans droit sensible, rôle élargi, support jamais nommé.

**Documents.** `05` (découpage, L.2 barrée dans la file), `06`, `03` (décisions), `04` (sortes de notification), `reference.md`, `A-FAIRE.md` § 9 et § 11, `infra/.env.example`.

**Risques / à vérifier.** Liste d'adresses en réglage du serveur et non dans la console : celui qui a pris la console ne peut pas l'élargir, et une faute de frappe se répare par SSH sans toucher aux écoles (une entrée invalide n'autorise personne). Connexion mobile à adresse changeante : laisser vide. Sessions super-admin ouvertes avant la mise en ligne : raccourcies à la première requête.
