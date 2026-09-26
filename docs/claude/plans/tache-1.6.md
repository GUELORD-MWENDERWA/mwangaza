# Plan — Tâche 1.6 : front `gestion` (squelette, connexion, menu, Mon compte, session support)

Issue #12 · branche `tache/1.6-front-gestion` · date : 2026-09-26.

Références : B3–B5, I2 (`02`), A3 (session support), cahier § 9.4 ; `03` § 1, § 3, § 5.4, § 8 ;
`04` § 8 (permissions). Maquettes : `gestion/connexion`, `connexion-double-authentification`,
`double-authentification-activation` (M1), `choix-ecole` (M2), `mon-compte` (M4),
`tableau-de-bord` (coquille), `menu-mobile` (M7), `pages-etat` (M8), et `session-support`
(nouvelle, dessinée pour cette tâche, **à valider**). Skills : `ecran`, `design`, `backend`.

## Dépendances (règle 8) — toutes acceptées par l'utilisateur le 2026-09-26

Réponses : stack front et client généré oui ; Testing Library et Playwright maintenant ; `qrcode-generator` oui ; maquette `session-support` validée telle quelle.

Prévues par la stack (`CLAUDE.md`, `03` § 1) mais jamais installées :

| Paquet | Pourquoi |
|---|---|
| `react-router` | adresses des écrans (`/app/login`, `/app/account`…) |
| `@tanstack/react-query` | appels à l'API, cache, nouvel essai |
| `i18next`, `react-i18next` | textes en français et en anglais |
| `tailwindcss`, `@tailwindcss/vite` | styles avec les jetons des maquettes |
| `radix-ui`, `class-variance-authority`, `clsx`, `tailwind-merge` | ce sur quoi reposent les composants shadcn/ui (copiés dans `packages/ui`, pas un paquet) : menu tiroir, menus déroulants, cases à cocher accessibles au clavier |
| `react-hook-form`, `zod`, `@hookform/resolvers` | formulaires et leurs vérifications |
| `vite-plugin-pwa` | application installable, fichiers gardés pour le hors-ligne, nouvelle version proposée |

Hors de la liste de la stack :

| Paquet | Pourquoi | Sans lui |
|---|---|---|
| `openapi-typescript` (développement), `openapi-fetch` | client typé généré depuis `openapi.yaml` (`03` § 1 « client TypeScript généré ») : une API changée casse la compilation du front | types écrits à la main |
| `qrcode-generator` (aucune dépendance) | QR code à scanner pour activer la double authentification (M1) ; resservira pour le QR des reçus (3.2) | seulement la clé à recopier |
| `@testing-library/react`, `@testing-library/user-event`, `jsdom` (développement) | tests des écrans dans Vitest (navigateur simulé) | pas de test d'écran |
| `@playwright/test` (développement) + Chromium téléchargé une fois (~170 Mo) | parcours réel dans un navigateur, front + Django (connexion avec code, activation, session support) ; exigé plus tard pour la caisse hors-ligne (3.5) | reporté à 3.4 |

Icônes : celles des maquettes (`maquettes/outils/maquettes.py`, `ICONS`), recopiées en composant
React, sans `lucide-react`. Police Atkinson Hyperlegible : fichiers des maquettes embarqués.

## Ce qui est construit

### 1. Socle du front (`frontend/packages`)

- `packages/ui` : thème Tailwind v4 (jetons de la skill `design`, variables shadcn), police
  embarquée, composants (`Button`, `Input`, `PasswordInput`, `CodeInput` à 6 cases, `Label`,
  `FormField`, `Checkbox`, `Card`, `Banner`, `StatusPill`, `Tag`, `Steps`, `CodeBlock`,
  `SegmentedControl`, `Sheet`, `DropdownMenu`, `Avatar`, `Toast`), icônes.
- `packages/i18n` : i18next, `fr` (libellés des maquettes mot pour mot) et `en` ; formats de
  date et d'heure dans le fuseau de l'école ; langue : celle du compte une fois connecté, sinon
  celle choisie sur l'écran de connexion (gardée dans le navigateur), sinon français.
- `packages/api` : types générés (`make api` les régénère avec le schéma), client `openapi-fetch`
  (jeton CSRF relu à chaque requête : Django le change à la connexion), erreurs `{code, detail}`
  traduites par leur code.

### 2. Application `gestion`

- **PWA** : manifeste (nom, icônes, `/app/`), fichiers de l'application gardés par le service
  worker, nouvelle version proposée (« Nouvelle version prête — Mettre à jour », M8), jamais
  imposée. Pas de service worker en développement.
- **Connexion en étapes** sur l'API de la 1.3 : `/app/login` (numéro, mot de passe, « Mot de
  passe oublié ? » → demander un mot de passe provisoire au directeur), `/app/login/code` (6
  cases, « Ne plus demander sur cet appareil pendant 7 jours », code de secours),
  `/app/login/new-password`, `/app/login/two-factor` (M1 : application, QR code et clé, code,
  puis 8 codes de secours à imprimer ou télécharger ; « Terminer » bloqué tant que la case n'est
  pas cochée). Rechargement de la page : l'étape en cours est redemandée au serveur. Blocage
  (429) : message avec le temps d'attente.
- **Identité de l'école** sur les écrans de connexion : nom, logo (ou code sur la couleur de
  l'école, texte blanc ou encre), `{code}.mwangaza.school`, « Français | English ».
- **Coquille** (maquette `tableau-de-bord`) : barre latérale basalte (école, menu, pied), barre
  du haut (état du réseau, nom et rôle → Mon compte), menu tiroir sous 900 px (M7). **Menu selon
  les permissions** (`04` § 8) : tout le menu V1.0 filtré par les droits du compte dans l'école ;
  entrées V1.1 / V1.2 masquées ; écran pas encore construit → page « bientôt disponible ». La
  recherche (`Ctrl K`) arrive avec les élèves (2.2) ; l'état de synchronisation avec la 3.4
  (en 1.6 : en ligne / hors ligne).
- **Changer d'école** (M2) : le nom de l'école en haut du menu ouvre la liste des écoles du
  compte (seulement s'il en a plusieurs) ; `/app/schools` = « Choisir l'école » (écoles avec
  rôles, dernière visite, suspendue grisée). Ouvrir une école = aller à son adresse ; on s'y
  connecte (session propre à chaque adresse).
- **Mon compte** (M4) : identité (lecture seule, « adressez-vous au directeur »), langue,
  mot de passe (les autres appareils sont déconnectés), double authentification (activée
  depuis, codes de secours restants, alerte à 2 ou moins, nouveaux codes, changer de téléphone,
  désactiver si aucun rôle ne l'exige), mes écoles, se déconnecter. PIN (3.7) et appareils
  connectés (3.3) : avec leur tâche. E-mail : pas de champ tant qu'il n'a pas d'usage (`04`).
- **Session support** (maquette `session-support`) : `/app/support` ; le super-admin connecté à
  l'adresse de l'école ouvre la session avec un motif ; bandeau rouge sur tous les écrans (école,
  heure de fin, motif, « Quitter ») ; fermée à l'heure de fin. Le lien « Ouvrir en tant qu'école »
  de l'administration Django y mène (au lieu de l'API).
- **Pages d'état** (M8) : accès refusé (403), page introuvable (404), erreur (500, « Réessayer »),
  école suspendue, adresse sans école, session expirée, aucun rôle dans cette école. Stockage
  refusé : 3.4 ; portail : 4.4.

### 3. Serveur (petits ajouts pour les écrans)

- Erreurs de saisie avec un code par champ (décision de la 1.2 « à revoir avec les formulaires
  (1.6) ») : `{"code": "invalid", "detail": …, "fields": {"new_password": [{"code":
  "password_too_short", "detail": …}]}}` ; l'interface traduit chaque code.
- `/api/me/` : `is_platform_admin` ; pour chaque école : adresse, couleur, couleur du texte,
  logo, rôles, dernière visite.
- `/api/school/` : + fuseau horaire (dates affichées à l'heure de l'école).
- Administration : « Ouvrir en tant qu'école » → `{adresse}/app/support`.

## Tests prévus

- Vitest + Testing Library : thème et composants (code à 6 cases : collage, retour arrière),
  menu filtré par permissions (chaque rôle de `04` § 8), étapes de connexion (chaque `step`,
  erreurs traduites, 429), activation (Terminer bloqué), Mon compte (alerte codes de secours,
  désactivation impossible si exigée, langue), bandeau support (fin, Quitter), pages d'état,
  traductions `fr` / `en` complètes (mêmes clés), aucune chaîne en dur.
- Playwright (front + Django + données de `make demo`) : directeur (mot de passe + code) → menu
  complet ; caissière → menu de la caisse seulement, page d'un écran interdit → 403 ;
  promoteur → activation de la double authentification ; mot de passe provisoire → nouveau
  mot de passe ; super-admin → session support, bandeau, Quitter ; école suspendue ; téléphone
  390 px → menu tiroir. En CI : un job de plus.
- pytest : format des erreurs de saisie, `/api/me/` (écoles, rôles, `is_platform_admin`, rien
  d'une autre personne), `/api/school/` (fuseau), lien de l'administration.

## Risques

- Beaucoup de nouveautés d'un coup : versions récentes (Vite 8, TypeScript 7 dans les
  applications, Tailwind 4, React Router 8) ; `openapi-typescript` attend TypeScript 5 (à
  essayer avec la 6 de la racine, sinon types générés autrement).
- Session propre à chaque adresse : changer d'école demande de se reconnecter (voulu :
  isolation, `03` § 2).
- Tests Playwright plus lents et dépendants de `make demo` (remis à zéro au début).
