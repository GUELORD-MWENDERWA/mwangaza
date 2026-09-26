# Plan — Tâche 1.5 : super-admin (écoles, session support, double authentification)

Issue #11 · branche `tache/1.5-super-admin` · date : 2026-09-26.

Références : A1–A3 (`02`), `01` § 5 (super-administrateur), `03` § 2, § 4 et § 8, `04` § 1
(`School`, `AuditLog.impersonated_by`), Q8 (couleur), maquettes `gestion/superadmin-ecoles`
(fournie) et `gestion/parametres-ecole` (M5, à valider). Skill : `backend`. Aucune nouvelle
dépendance (pas de Pillow : le logo est vérifié par ses premiers octets).

## Où travaille le super-admin

Dans **l'administration Django** (`admin.mwangaza.school/admin/`, en développement
`localhost:8000/admin/`) : c'est déjà son outil depuis la 1.2 (`is_platform_admin`). Le front
n'existe pas encore (squelette en 1.6). L'écran dédié de la maquette (cartes de statistiques,
abonnements) n'apporte rien de plus pour un seul super-admin et quelques écoles : proposé avec
la tâche 7.2 (V2 : abonnements, statistiques globales). À valider.

## Ce qui est construit

### 1. Double authentification du super-admin

- `totp_required(user)` vrai pour un super-admin : la connexion (API ou administration) exige le
  code, et l'active à la première connexion ; il ne peut pas la désactiver.
- Administration Django : site `PlatformAdminSite` (remplace le site par défaut). Accès = compte
  actif, super-admin **et session passée par la double authentification**. Connexion en étapes
  avec les mêmes fonctions que l'API (`login.py`) : numéro et mot de passe → code (ou code de
  secours ; jamais d'« appareil de confiance » ici) → nouveau mot de passe si provisoire →
  activation (clé à saisir dans l'application, 8 codes de secours affichés une fois). Un compte
  qui n'est pas super-admin est refusé dès le mot de passe. Même limitation des tentatives.
- `make demo` : double authentification du super-admin de démonstration (même clé, `make totp`).

### 2. Écoles (A1, A2) — administration Django

- `School` : + `official_name`, `logo`, `primary_color`, `timezone`, `enabled_currencies`,
  `default_currency`, `plan`, `trial_ends_on`, `paid_until` (abonnement saisi à la main, A2).
  `logo_monochrome`, `settings`, `matricule_format`, `network` : avec leur tâche (3.2, 1.7…).
- **Créer une école** : identité, abonnement **et premier directeur** (numéro, noms). Numéro
  inconnu → compte créé avec un mot de passe provisoire affiché une seule fois au super-admin
  (pas de SMS en V1 : la maquette parle d'un « lien d'activation », impossible sans SMS ni
  e-mail) ; numéro connu → ajouté sans nouveau mot de passe. Rôles système copiés (déjà).
- **Liste** : nom et adresse, statut et abonnement, **dernière activité** (dernière entrée du
  journal de l'école qui n'est pas du support), lien « Ouvrir en tant qu'école ». Nombre
  d'élèves → 2.1 (pas encore d'élèves) ; paiements du jour → avec l'écran dédié.
- **Suspendre / réactiver** (actions de la liste, ou le statut dans la fiche). Suspendue :
  l'adresse de l'école répond `school_suspended` à tous (déjà), pas de session support ; rien
  n'est supprimé ; elle reste visible, grisée, dans le choix de l'école (`/api/me/` donne son
  statut ; note de la maquette M2, vue pendant la tâche). Portail
  (« service temporairement indisponible ») : 4.4.
- On ne supprime pas une école (bouton retiré).

### 3. Paramètres de l'école (Q8, M5) — API

- `GET` / `PATCH /api/school/settings/` (`school.configure`) : nom, nom officiel, couleur,
  fuseau horaire, devises (au moins une, devise principale parmi elles) ; code en lecture seule
  (le super-admin seul le change). Logo : `POST` / `DELETE /api/school/settings/logo/`.
- `GET /api/school/` (public, écran de connexion) : + couleur, couleur du texte, adresse du logo.
  `GET /api/school/logo/` (public) sert le logo de l'école de l'adresse.
- **Couleur** (Q8) : texte blanc ou encre `#1A2233`, celui qui contraste le plus, s'il atteint
  4,5 : 1 (WCAG) ; sinon couleur refusée, avec une teinte voisine proposée (même teinte,
  luminosité changée au minimum). Calcul dans `apps/schools/colors.py`, sans dépendance.
- **Logo** : PNG, JPEG ou SVG, 1 Mo au plus, reconnu à ses premiers octets (pas à son nom) ; SVG
  sans script ni entité ; servi avec `nosniff` et une politique qui empêche tout script.
  Stocké dans `MEDIA_ROOT` jusqu'au stockage objet (4.7).
- **Fuseau horaire** de l'école appliqué à chaque requête sur son adresse (dates, filtres du
  journal) ; défaut `Africa/Lubumbashi`.
- Écran M5 → 1.7 (avec les autres écrans des paramètres) ; reçus → 3.2 ; alertes → 4.2.

### 4. Session support « en tant qu'école » (A3)

- Le super-admin se connecte **à l'adresse de l'école** (mot de passe + code, comme tout le
  monde), puis ouvre la session support avec un **motif** : `POST /api/support/`. Le lien de la
  liste des écoles y mène. `GET` : la session en cours ; `DELETE` : la fermer.
- Pendant la session (**1 heure au plus**), il a les droits de l'école **sauf la caisse**
  (`finance.collect_payment`, `request_cancellation`, `approve_cancellation`,
  `close_register`) : le support ne touche pas à l'argent.
- `/api/me/` : `support` (motif, début, fin) pour le bandeau rouge (écran en 1.6).
- **Journal de l'école** : ouverture (motif, heure de fin), fermeture (bouton ou déconnexion),
  et chaque action faite pendant la session avec `impersonated_by` (le super-admin, aussi
  `actor`) ; l'école voit « Support Mwangaza ».
- Refusée : compte pas super-admin, session sans double authentification, école suspendue ; une
  session ouverte dans une école ne donne rien dans une autre.

### 5. Comptes modifiés par le support (administration Django)

- Noms, téléphone → `account.changed` (avant / après) ; désactivation / réactivation du compte →
  `account.deactivated` / `account.reactivated` ; dans le journal de chaque école où la personne
  est active.
- **Mot de passe** : l'administration ne laisse plus choisir le mot de passe de quelqu'un ; elle
  donne un **mot de passe provisoire** (comme M3), affiché une fois, à changer à la connexion →
  `account.password_reset`.
- Création d'une école, changements de son identité, suspension, logo : dans son journal
  (`school.*`). Abonnement : pas dans le journal de l'école (historique de l'administration).

### Nouvelles actions du journal

`school.created`, `school.updated`, `school.logo_changed`, `school.suspended`,
`school.reactivated`, `support.started`, `support.ended`, `account.changed`,
`account.deactivated`, `account.reactivated`, `account.password_reset`.

## Tests prévus

- Couleurs : contrastes connus (blanc / noir = 21), couleurs de la démo, rouge pur refusé avec
  une teinte proposée lisible et proche, formats refusés.
- Modèle et services des écoles : valeurs par défaut, devises, fuseau, logo (type, taille, SVG
  dangereux), création avec directeur (nouveau / connu), journal de la nouvelle école seulement,
  changements notés champ par champ, rien de changé → rien, suspension / réactivation, ancien
  logo effacé.
- API des paramètres : directeur oui ; autres rôles, anonyme, directeur d'une autre école à
  cette adresse → refusé ; une école ne change que ses propres paramètres ; couleur illisible,
  devise principale absente, fuseau inconnu → 400 ; logo servi par chaque adresse pour sa seule
  école.
- Fuseau : activé par requête, rétabli après.
- Session support : ouverture, droits sans la caisse, `/api/me/`, action notée avec
  `impersonated_by`, 1 h au plus, fermeture et déconnexion notées, refus (pas super-admin, sans
  double authentification, école suspendue, autre école).
- Administration : connexion en étapes (code, activation, nouveau mot de passe, compte refusé,
  blocage), accès refusé sans double authentification, création d'une école avec directeur,
  liste, suspension, compte modifié par le support noté dans chaque école, mot de passe
  provisoire.
- `/api/me/` : école suspendue toujours listée avec son statut ; `make demo` (couleurs, abonnement,
  logo public de l'ITIG remis à chaque fois).

## Risques

- Remplacer le site d'administration : toutes les pages de l'administration passent par la
  nouvelle connexion (tests de l'administration à reprendre avec une session à double
  authentification).
- Le lien « Ouvrir en tant qu'école » mène à l'API navigable jusqu'à la 1.6.
