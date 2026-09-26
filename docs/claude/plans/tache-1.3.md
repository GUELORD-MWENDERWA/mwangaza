# Plan — Tâche 1.3 : connexion, double authentification, limitation des tentatives

Issue #9 · branche `tache/1.3-connexion` · date : 2026-09-26.

Références : B4 (`02`), `01` § 8.2 et § 9.3, `03` § 8, `04` § 1, maquettes `connexion` et
`connexion-double-authentification` (fournies), M1 `double-authentification-activation`, M3
`personnel-comptes`, M4 `mon-compte` (à valider). Skill : `backend`.

## Dépendances (validées par l'utilisateur le 2026-09-26)

- `argon2-cffi` : hachage Argon2 (`03` § 8) ; les anciens mots de passe sont convertis à la
  connexion suivante.
- `cryptography` : clé TOTP chiffrée en base (M1), clé dérivée de `DJANGO_SECRET_KEY` (et de
  `SECRET_KEY_FALLBACKS` pour une rotation).
- TOTP et limitation des tentatives écrits dans le projet (pas de `django-otp` ni de
  `django-axes`).

## Ce qui est construit (API seulement ; les écrans arrivent en 1.6 et 1.7)

### Connexion en plusieurs étapes

Django ne connecte le compte (`login()`) qu'après **toutes** les étapes : avant, la session ne
porte qu'une connexion « en cours » (10 minutes au plus). Aucun point d'API, présent ou futur, ne
peut donc être atteint avec le mot de passe seul.

| Étape | Quand | Point d'API |
|---|---|---|
| `password` | rien en cours | `POST /api/auth/login/` {phone, password} |
| `totp` | double authentification activée (sauf appareil de confiance) | `POST /api/auth/login/totp/` {code, trust_device} ; code à 6 chiffres ou code de secours |
| `new_password` | mot de passe provisoire (`must_change_password`) | `POST /api/auth/password/` {new_password} |
| `totp_setup` | double authentification exigée et pas encore activée | `POST /api/auth/totp/setup/` puis `POST /api/auth/totp/activate/` {code} → 8 codes de secours |
| `done` | connecté | — |

Ordre : `totp` (si activée) → `new_password` → `totp_setup` → `done` (un mot de passe provisoire
ne suffit pas à prendre un compte protégé). `GET /api/auth/login/` rend l'étape en cours
(rechargement de la page). `GET /api/auth/csrf/` donne le cookie CSRF à l'application ;
`POST /api/auth/logout/`. CSRF vérifié aussi sur les étapes sans compte connecté.

« Ne plus demander sur cet appareil pendant 7 jours » (maquette fournie) : cookie signé,
`HttpOnly`, lié au compte, à son mot de passe et à sa clé TOTP (un changement l'annule).

### Qui doit activer la double authentification (B4)

Exigée pour un compte qui a, dans une appartenance active, un rôle portant l'un de ces codes :
`school.configure`, `roles.manage`, `audit.view`, tout `finance.*` (`roles.py`,
`TOTP_PERMISSIONS`). Par défaut : directeur, comptable, caissier, promoteur, exactement la liste
de B4 (test). Un rôle créé par l'école avec un droit sur l'argent l'exige aussi : rien n'est lié
au nom des rôles. Vérifié aussi à chaque requête : `HasSchoolPermission` refuse
(`totp_required`) si les droits dans l'école de l'adresse l'exigent et que la session n'est pas
passée par la double authentification (rôle donné pendant la session).

### Limitation des tentatives

Table `LoginFailure` [G] (numéro tapé, adresse IP, date). 5 échecs pour un numéro en 15 minutes
→ numéro bloqué 15 minutes (maquette de connexion) ; 30 échecs d'une même adresse IP → adresse
bloquée 15 minutes (essais sur beaucoup de numéros). Comptent : mot de passe, code TOTP ou de
secours, mot de passe actuel. Même réponse pour un numéro inconnu (on ne devine pas qui a un
compte). `429 too_many_attempts` + `Retry-After`. Vérifié dans le moteur d'authentification :
la connexion de l'administration Django est protégée aussi. Effacé à la connexion réussie ;
lignes de plus d'un jour purgées.

### Mon compte (M4) : la personne elle-même

- `GET/PATCH /api/me/` : + `totp_enabled`, `totp_enabled_at`, `totp_required`,
  `recovery_codes_left` ; langue modifiable.
- `POST /api/auth/password/` {current_password, new_password} : les autres sessions sont
  déconnectées (Django), celle-ci reste.
- `POST /api/auth/totp/setup/` (code actuel ou de secours exigé si déjà activée : « changer de
  téléphone »), `…/activate/`, `…/recovery-codes/` {code} (8 nouveaux codes),
  `…/disable/` {code} (refusé si un rôle l'exige).

### Comptes du personnel (M3) : l'école (`roles.manage`)

- `POST /api/staff/{id}/new-password/` → mot de passe provisoire affiché une fois.
- `POST /api/staff/{id}/reset-totp/` → la personne la réactive à sa prochaine connexion.
- `PATCH /api/staff/{id}/` : + `last_name`, `middle_name`, `first_name`, `phone`.
- **Seulement pour un compte utilisé dans cette seule école** (et pas super-admin) ; sinon
  `409 account_used_elsewhere` : c'est le support de la plateforme (super-admin) qui le fait.
  Raison : `03` § 4 (une école ne prend jamais la main sur un compte qui sert ailleurs) ;
  l'existence d'un compte ailleurs est déjà connue de l'école (`existing_account`, 1.2), aucune
  école n'est nommée.
- Liste : + `totp` (`enabled`, `required` = à activer, `not_required`, selon les rôles dans
  **cette** école), `last_login_at` (dernière connexion **à cette école** :
  `Membership.last_login_at`), `account_managed_here`.

### Modèles et réglages

- `User` : `totp_secret` (chiffré), `totp_enabled_at` (`totp_enabled` = propriété),
  `totp_last_step` (un code déjà utilisé est refusé). `RecoveryCode` [G] : empreinte HMAC (clé
  du serveur), `used_at`. `Membership.last_login_at`. `LoginFailure` [G].
- `apps/core/crypto.py` (chiffrement), `apps/accounts/totp.py` (RFC 6238),
  `apps/accounts/attempts.py`, `apps/accounts/login.py` (étapes de la session),
  `apps/accounts/backends.py` (téléphone + blocage).
- Argon2 en premier dans `PASSWORD_HASHERS` ; mot de passe d'au moins 10 caractères (M4),
  proche du numéro ou des noms refusé.
- « Log in » de l'API navigable de DRF retiré : la vraie connexion (`/api/auth/login/`)
  s'utilise dans l'API navigable.
- Administration Django : double authentification visible, action « Réinitialiser la double
  authentification » (support).
- `make demo` : double authentification activée pour les comptes qui l'exigent avec une clé de
  démonstration (sauf le promoteur de l'ITIG, pour essayer l'activation) ; `make totp` affiche le
  code du moment (développement seulement).

## Tests prévus

TOTP (vecteurs de la RFC 6238, fenêtre ±30 s, rejeu refusé), chiffrement (aller-retour, rotation
de clé, falsification), blocage (seuils, numéro inconnu, IP, expiration, purge), étapes de
connexion (chaque ordre, expiration, CSRF, appareil de confiance, code de secours à usage unique,
Argon2 et conversion d'un ancien hachage, administration bloquée), Mon compte, comptes du
personnel (règle « une seule école », isolation, 403), permission `totp_required`, rôles par
défaut qui exigent la double authentification = B4, `make demo`.

## Hors tâche

PIN et appareils (3.3, 3.7 ; « Se souvenir de cet appareil » de la maquette de connexion),
e-mail (avec son usage), double authentification du super-admin dans l'administration Django
(1.5), audit (1.4 : les services seront branchés), écrans (1.6 : connexion, double
authentification, activation M1, Mon compte M4 — ajouté à 1.6 ; 1.7 : M3), adresse IP réelle
derrière Caddy et Cloudflare (4.6).

## Risques

- Blocage par adresse IP : une école entière derrière une même connexion ; seuil haut (30).
- Perte de `DJANGO_SECRET_KEY` = clés TOTP illisibles : chacun réactive sa double
  authentification (à noter pour 4.6).
- Tests existants connectés par `force_login` : la fixture `api` marque la session comme passée
  par la double authentification.
