# Architecture technique

## 1. Choix des technologies et raisons

| Besoin | Choix | Pourquoi |
|---|---|---|
| Serveur | **Python + Django 5.2 LTS + Django REST Framework** | Tu maîtrises déjà Python et Django. Django apporte admin, migrations, authentification, sécurité, i18n. Version LTS = mises à jour de sécurité longues. |
| Base de données | **PostgreSQL 16+** | Fiable pour l'argent (transactions strictes), JSON, recherche plein texte, sécurité par ligne possible plus tard. |
| Tâches de fond | **Celery + Redis** | PDF lourds, notifications push, relances, imports Excel volumineux. |
| PDF | **WeasyPrint** | Bulletins et reçus A4 en HTML/CSS, faciles à adapter à chaque école. |
| Interface | **React + TypeScript + Vite** | Écosystème le plus riche pour une PWA hors-ligne ; Claude Code y est très efficace ; le typage évite les erreurs sur les montants. |
| Hors-ligne | **vite-plugin-pwa (Workbox) + Dexie.js (IndexedDB)** | Application installable, fichiers en cache, base locale dans le navigateur. |
| Données front | **TanStack Query** | Cache, reprise automatique. |
| Design | **Tailwind CSS + shadcn/ui** | Composants simples et accessibles, thème par école via variables CSS. |
| Formulaires | **react-hook-form + zod** | Validation identique côté formulaire et côté synchronisation. |
| Contrat API | **drf-spectacular → OpenAPI → client TypeScript généré** | Le front et le serveur ne se désynchronisent jamais. |
| Mobile | **PWA d'abord ; Capacitor en V2** pour publier sur Play Store / App Store | Un seul code ; les stores seulement quand ils apportent quelque chose (visibilité, push iPhone plus fiable). |
| Notifications | **Web Push (VAPID) via pywebpush** | Gratuit. Sur iPhone, fonctionne quand la PWA est ajoutée à l'écran d'accueil. |
| Hébergement | **1 VPS + Docker Compose + Caddy + Cloudflare** | Tient dans le budget ; Caddy gère HTTPS ; Cloudflare gère DNS, certificat wildcard et cache. |

Alternatives écartées : Laravel ou Node (tu devrais réapprendre) ; Flutter pour tout (bon en mobile mais web lourd et hors-ligne navigateur moins mûr) ; application de bureau Windows (il faudrait gérer installation et mises à jour dans chaque école, et tu veux aussi Android et iPhone).

## 2. Vue d'ensemble

```
             Cloudflare (DNS, wildcard *.mwangaza.school, cache)
                                  │
                         VPS ─ Caddy (HTTPS)
        ┌─────────────────────────┼─────────────────────────────┐
  {ecole}.mwangaza.school   parents.mwangaza.school     admin.mwangaza.school
   /app  → PWA Gestion      /  → PWA Portail            → super-admin
   /api  → Django           /api/portal → Django        (Django admin + écrans dédiés)
   /v/{id} → vérif reçu
        └─────────────────────────┼─────────────────────────────┘
                       Django (gunicorn) ── Celery ── Redis
                                  │
                             PostgreSQL ──► sauvegardes continues vers stockage objet
```

- L'API de l'application Gestion est servie **sur le même sous-domaine que l'école** : l'école est déduite du nom d'hôte, les cookies restent sur la bonne origine.
- Le portail parents est sur un **domaine unique**, car une famille peut avoir des enfants dans plusieurs écoles.
- Plus tard, la racine `{ecole}.mwangaza.school/` accueillera le site vitrine de l'école.

## 3. Organisation du dépôt

```
mwangaza/
├── CLAUDE.md
├── docs/
├── backend/
│   ├── config/                 # settings (base, dev, prod), urls, celery
│   ├── apps/
│   │   ├── core/               # TenantModel, middleware école, UUID v7, utilitaires argent
│   │   ├── accounts/           # User, Membership, Role, Permission, TOTP, PIN, Device
│   │   ├── schools/            # School, AcademicYear, Term, Level, Track, ClassGroup
│   │   ├── students/           # Student, Family, Guardian, Enrollment, imports
│   │   ├── finance/            # FeeType, FeeRule, InstallmentTemplate, StudentCharge, Discount, Payment (+ reçu imprimable), CashRegister, CashClosing, ExchangeRate
│   │   ├── payroll/            # V1.1
│   │   ├── portal/             # API du portail familles
│   │   ├── notifications/      # annonces, web push
│   │   ├── sync/               # push/pull, change log
│   │   └── audit/              # AuditLog
│   └── tests/
├── frontend/                   # workspace pnpm
│   ├── apps/gestion/           # PWA personnel, hors-ligne
│   ├── apps/portail/           # PWA familles
│   └── packages/
│       ├── api/                # client généré depuis OpenAPI
│       ├── ui/                 # composants partagés
│       ├── i18n/               # traductions fr / en
│       └── money/              # formatage et calculs de montants (entiers)
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── Caddyfile
│   └── backup/
└── firmware/                   # V1.2 : lecteurs RFID ESP32 (PlatformIO)
```

## 4. Multi-écoles

**Choix : une base, un schéma, chaque ligne liée à son école.**

Pourquoi pas un schéma ou une base par école : les parents multi-écoles, les enseignants multi-écoles, les transferts d'élèves et les vues promoteur exigent des requêtes entre écoles. Avec des schémas séparés, elles deviennent compliquées et les migrations se multiplient.

Mise en œuvre :

1. `TenantModel` (abstrait, `apps/core`) : champ `school = ForeignKey(School)`, index composés commençant par `school`. Ses `save()`, `delete()` et `bulk_create()` remplissent l'école depuis l'école courante et refusent (`CrossSchoolError`) d'écrire ou de supprimer une ligne d'une autre école, de changer l'école d'une ligne (un transfert est une copie) et de relier une ligne à une ligne d'une autre école.
2. `TenantMiddleware` : lit le sous-domaine (`SCHOOL_BASE_DOMAINS` : `mwangaza.school` ; `localhost` en développement), charge l'école dans `request.school` et en fait l'école courante (`contextvars`) le temps de la requête. École inconnue : 404 `school_not_found` ; suspendue : 403 `school_suspended`. Le domaine seul et les sous-domaines réservés (`www`, `parents`, `admin`, `api`…) n'ont pas d'école. Le rôle de l'utilisateur dans l'école est vérifié par les permissions de l'API, après l'authentification (1.2, 1.3). Hors requête (tâche Celery, commande, test) : `with use_school(school):`.
3. Manager par défaut `TenantManager` : filtre automatiquement sur l'école courante et **lève une erreur** (`SchoolNotSetError`) si aucune école n'est définie (évite les fuites silencieuses). Un manager `all_schools` explicite existe pour le super-admin et le portail.
4. Tests obligatoires : pour chaque endpoint, un test crée deux écoles et vérifie qu'aucune donnée de l'une n'est visible depuis l'autre.
5. Plus tard (sécurité en profondeur) : Row Level Security PostgreSQL.

Entités **globales** (sans école) : `User`, `School`, `SchoolNetwork`, `Membership` (lien personne ↔ école), `PushSubscription`. Entités **liées à une école** : tout le reste, y compris `Student`, `Family` et `Guardian` — chaque école a sa propre copie de l'élève et de sa famille (décision Q10 du 2026-09-26) — et `Enrollment`.

L'isolation vaut partout : application, API, exports, rapports, recherche, portail parent. Une école ne peut ni lire ni modifier les données d'une autre, et ne voit jamais qu'un élève ou une famille existe aussi ailleurs. Chaque école gère sa propre sécurité : ses comptes, ses rôles, ses permissions.

**Portail parent et plusieurs écoles** (solution retenue pour Q10) : un parent a un seul compte (`User`), relié à une famille dans chaque école (`Family.primary_user`). Il relie chaque école en saisissant le code famille qu'elle lui a remis, jamais automatiquement par numéro de téléphone. L'API du portail passe par le manager `all_schools`, filtré sur les familles de ce compte : elle ne renvoie que ses enfants, chacun avec les données de son école.

## 5. Hors-ligne et synchronisation

### 5.1 Ce qui marche hors-ligne en V1.0

Consultation des élèves et de leur situation financière, encaissement, impression et réimpression des reçus, demande d'annulation (validée en ligne), clôture de caisse (envoyée à la reconnexion).

### 5.2 Principes

1. **Chaque appareil est enregistré** (`Device`) lors de la première connexion en ligne, rattaché à une école et, pour la caisse, à une `CashRegister`. Il reçoit un préfixe court (ex : `C1`).
2. **Identifiants UUID v7** générés sur l'appareil pour tout ce qui est créé hors-ligne.
3. **Numéro de reçu unique sans serveur** : `{CODE_ECOLE}-{PREFIXE_APPAREIL}-{AA}-{séquence locale}`, ex : `ITIG-C1-26-000184`. La séquence est stockée dans IndexedDB et sauvegardée côté serveur à chaque synchronisation pour être restaurée si l'appareil est réinstallé.
4. **Journal d'opérations (outbox)** : chaque action hors-ligne écrit une opération dans une file locale `{op_id, type, payload, created_at, device_id}`. Les opérations sont envoyées dans l'ordre, par lots.
5. **Idempotence** : le serveur garde `op_id` ; une opération reçue deux fois n'est appliquée qu'une fois et renvoie le même résultat.
6. **Pas de conflit sur l'argent** : un paiement est une écriture ajoutée, jamais modifiée. Deux caissiers hors-ligne qui encaissent pour le même élève créent deux paiements valides ; le solde est recalculé à partir de tous les paiements.
7. **Surpaiement** : si, après synchronisation, un élève a payé plus que dû (deux caisses hors-ligne), le surplus devient un **crédit** sur l'élève, signalé au comptable. Jamais de rejet d'un paiement déjà encaissé physiquement.
8. **Données modifiables** (fiche élève) : « dernière écriture gagne » champ par champ, avec historique dans l'audit ; conflit signalé si deux modifications touchent le même champ dans la même fenêtre.
9. **Descente des données (pull)** : le serveur tient un `ChangeLog` par école avec un numéro croissant. L'appareil demande « tout depuis le numéro N » et met à jour sa base locale. Premier chargement : instantané complet de l'école (élèves, classes, frais, échéances, soldes), compressé.
10. **Configuration en ligne seulement** : frais, barèmes, rôles, classes. Hors-ligne, l'appareil utilise la dernière version reçue.

### 5.3 Endpoints

- `POST /api/sync/push` — lot d'opérations ; réponse : statut par `op_id` (appliquée / déjà appliquée / rejetée + raison).
- `GET /api/sync/pull?since={seq}&limit=…` — changements depuis `seq`.
- `GET /api/sync/snapshot` — instantané initial.

### 5.4 Côté navigateur

- Demander le stockage persistant (`navigator.storage.persist()`), afficher un avertissement si refusé.
- Indicateur permanent : en ligne / hors-ligne / opérations en attente / dernière synchronisation.
- Synchronisation au retour du réseau, au démarrage, et toutes les 60 s en ligne.
- Mise à jour de l'application : nouvelle version proposée, jamais forcée pendant qu'il reste des opérations non envoyées.
- Navigateurs recommandés pour la Gestion : Chrome ou Edge récents.

### 5.5 Authentification hors-ligne

- Connexion complète exigée en ligne au moins une fois par appareil, puis au moins une fois tous les 7 jours (configurable).
- Le PIN déverrouille les données locales ; il est vérifié contre une empreinte stockée localement (PBKDF2). Limite connue : un appareil volé déverrouillé expose les données en cache ; d'où l'expiration, la révocation d'appareil par l'admin et l'effacement local à la révocation.

## 6. Argent

- Montants en entiers dans la plus petite unité : `amount_minor` + `currency` (ISO : `USD`, `CDF`).
- Package `money` partagé côté front ; côté Python, une classe `Money` immuable.
- Devise : choisie pour chaque barème (`FeeRule.currency`), USD ou FC.
- Taux : `ExchangeRate(school, academic_year, USD → CDF, rate)`, fixe pour l'année scolaire, saisi par le comptable ; une correction en cours d'année ajoute une ligne (historique : qui, quand, ancien et nouveau taux) et ne change pas les paiements passés.
- Conversion : le paiement enregistre `rate_used` (toujours dans le sens USD → CDF) et le montant dans la devise du frais. FC → USD = division en `Decimal` par le taux ; arrondi demi supérieur à l'unité de la devise (centime, franc).
- Solde d'un élève = somme des montants dus (barèmes − réductions) − somme des paiements non annulés, par devise de frais. Calculé à la demande et mis en cache ; recalculable à tout moment.

## 7. Impression

- **Format du reçu choisi par l'école** (paramètres, `04` § 1) : thermique 58 mm ou 80 mm, ou imprimante ordinaire avec des reçus A6, A5 ou petit format (≈ 10 × 7 cm) sur une feuille A4, avec traits de découpe ; 1 ou 2 exemplaires (souche).
- **Reçu thermique** : page HTML dédiée avec CSS `@page { size: 58mm auto; margin: 0 }` ou `80mm auto`, imprimée par la boîte de dialogue du navigateur (fonctionne hors-ligne). Configurer une fois l'imprimante par défaut sur le poste. Logo : version noir et blanc de l'école, sinon logo en niveaux de gris. Plus tard si besoin : impression directe ESC/POS via Web Serial / WebUSB. Le modèle exact de l'imprimante ne bloque rien : test sur la vraie imprimante à la mise en place (4.8).
- **A4** : même principe hors-ligne ; PDF serveur (WeasyPrint) pour les documents générés en ligne (listes, situations, fiches).
- **QR code** généré dans le navigateur ; il pointe vers `https://{ecole}.mwangaza.school/v/{payment_id}` suivi du contenu signé du reçu (numéro, date, montant, devise).
- **Vérification d'un reçu imprimé hors ligne** : à son enregistrement (3.3), l'appareil crée une paire de clés ECDSA P-256 avec WebCrypto ; la clé privée, non exportable, reste dans le navigateur (IndexedDB) ; la clé publique est enregistrée sur `Device.public_key`. Chaque reçu est signé sur l'appareil. La page `/v/…` affiche le minimum (école, numéro, date, montant, élève en initiales, valide / annulé) : pour un paiement déjà synchronisé, elle lit la base et refuse un QR dont le contenu diffère ; pour un paiement pas encore reçu, elle vérifie la signature et affiche « reçu authentique, émis hors ligne par la caisse C1, en attente de synchronisation ». Un appareil révoqué ne produit plus de reçu valide. La signature n'ajoute aucune dépendance (WebCrypto est dans tous les navigateurs récents) ; le dessin du QR code en demandera une, à valider en 3.2.

## 8. Sécurité

- Sessions Django en cookie `HttpOnly`, `Secure`, `SameSite=Lax`, protection CSRF.
- Mots de passe : Argon2. Limitation des tentatives (django-axes ou équivalent).
- TOTP (django-otp) obligatoire pour les rôles financiers et la direction.
- Permissions vérifiées côté serveur ; les rôles portent des codes de permission (`finance.collect_payment`, `finance.cancel_payment`, `finance.close_register`, `students.import`…).
- `AuditLog` : qui, quoi, quand, école, appareil, adresse IP, avant / après.
- Alertes : plus de N annulations par jour pour un caissier, écart de caisse au-dessus d'un seuil, connexion « en tant qu'école » par le super-admin.
- Secrets dans des variables d'environnement, jamais dans le dépôt.
- Dépendances surveillées (Dependabot).

## 9. Hébergement et exploitation

- **Serveur** : un VPS d'entrée de gamme (2 vCPU, 4 Go de RAM) chez un hébergeur économique (Hetzner, DigitalOcean, OVH…). Vérifier les prix du moment ; l'ensemble doit rester sous 20 $ / mois au départ.
- **Conteneurs** : `caddy`, `django` (gunicorn), `celery`, `redis`, `postgres`.
- **DNS et certificats** : Cloudflare (offre gratuite), certificat wildcard `*.mwangaza.school`.
- **Sauvegardes** : WAL-G ou pgBackRest vers un stockage objet externe (Backblaze B2, Cloudflare R2…) → sauvegarde continue et restauration à une date précise ; plus un `pg_dump` quotidien conservé 30 jours. Test de restauration chaque mois.
- **Fichiers** (photos, documents) : stockage objet externe, pas sur le disque du VPS.
- **Surveillance** : suivi d'erreurs (Sentry offre gratuite ou GlitchTip), sonde de disponibilité externe.
- **Export école** : archive téléchargeable (Excel + PDF) de toutes les données de l'école.
- **CI** : GitHub Actions — lint, tests, build ; déploiement manuel par une commande au début.

## 10. Présences RFID (V1.2) — aperçu

- Lecteur ESP32 + module RFID/NFC (MFRC522 ou PN532) + écran/LED/buzzer, alimenté avec batterie tampon.
- Enregistré comme `Device` de type `reader` avec un jeton propre à l'école.
- Envoie `{card_token, timestamp, reader_id}` en HTTPS vers `/api/attendance/scan` ; stocke les pointages en mémoire flash si le réseau est coupé et les renvoie ensuite (idempotence par identifiant de pointage).
- La carte porte un jeton aléatoire, révocable en cas de perte.

## 11. Journal des décisions

| Date | Décision | Raison |
|---|---|---|
| 2026-09 | Django + React/TS PWA, PostgreSQL | Compétences existantes, hors-ligne navigateur, budget |
| 2026-09 | Multi-écoles par clé étrangère `school` | Fonctions inter-écoles (parents, transferts, réseaux) |
| 2026-09 | Paiements immuables, annulation = nouvel enregistrement | Traçabilité, synchronisation sans conflit |
| 2026-09 | Portail familles sur domaine unique | Enfants dans plusieurs écoles |
| 2026-09 | Pas de SMS en V1 | Budget ; push et annonces gratuits |
| 2026-09-25 | Suivi d'avancement dans `docs/06-suivi.md` ; skills Claude Code dans `.claude/skills/` | Savoir à tout moment où en est le projet ; même méthode à chaque tâche |
| 2026-09-25 | Documents réels de l'ITIG avec données personnelles dans `docs/ecole-pilote/prive/`, hors Git | Confidentialité des élèves et du personnel |
| 2026-09-25 | Dépôt GitHub privé ; un jalon par version, une issue par tâche, PR `Closes #n` | Progression visible par version ; historique relié aux tâches |
| 2026-09-25 | `uv` pour Python, `pnpm` (corepack) pour le front, `make` comme point d'entrée unique | Installations rapides et verrouillées ; mêmes commandes en local, en Docker et en CI |
| 2026-09-25 | Dev : sous-domaines `{code}.localhost`, API derrière le proxy Vite (`changeOrigin: false`) | Même origine que la production (cookies, CSRF) et sous-domaine de l'école transmis à Django |
| 2026-09-25 | API fermée par défaut (`IsAuthenticated`) ; schéma et doc OpenAPI exposés seulement en `DEBUG` | Chaque endpoint ouvre explicitement ce qu'il expose ; pas de carte de l'API publique en production |
| 2026-09-26 | Maquettes manquantes dessinées par Claude dans le système de design (état « à valider ») ; menu de la Gestion : + Crédits d'élèves, Demandes des parents, Paramètres de l'école, Comptes du personnel, Journal d'audit | Chaque écran V1.0 a une référence avant d'être codé ; toutes les fonctions V1.0 ont une entrée de menu |
| 2026-09-26 | Bulletins : format des formulaires officiels IGE/P.S (branches groupées par maximum, examen = 2 × période, pas d'examen pour les cours pratiques) ; maxima stockés par cours et par classe, pas calculés depuis les heures | Conforme aux bulletins réels ; le barème officiel n'est pas proportionnel aux heures |
| 2026-09-26 | Variable d'environnement vide (`NOM=` dans `.env`) = absente : la valeur par défaut s'applique ; la production refuse toujours de démarrer sans `DJANGO_SECRET_KEY` | `cp .env.example .env` suffit en développement, sans rien coller ; une ligne vide ne fait plus planter Django |
| 2026-09-26 | `make dev` : le conteneur du front réutilise le `node_modules` installé sur la machine (`pnpm install` lancé par `make dev` avant Docker) ; aucune installation ni vérification des dépendances dans le conteneur | Une installation dans le conteneur réécrivait le `node_modules` partagé avec un store introuvable hors de Docker et retéléchargeait tout à chaque lancement |
| 2026-09-26 | L'ITIG est l'école d'exemple, pas la seule : rien de propre à une école dans le code (tout dans ses paramètres) ; données de démonstration fictives et réalistes (`itig` ~800 élèves, `volcans` plus petite) ; chaque école saisit ses vraies données | Mwangaza est une plateforme multi-écoles ; on n'attend plus les documents de l'ITIG pour avancer |
| 2026-09-26 | Isolation vérifiée partout (application, API, exports, rapports, recherche, portail) : pour chaque modèle, écran ou point d'API, un test prouve qu'une école ne peut ni lire ni modifier les données d'une autre | Chaque école a ses données, sa sécurité et une visibilité limitée à elle-même |
| 2026-09-26 | Q10 : `Student`, `Family`, `Guardian` liés à l'école (une copie par école) ; portail : un compte parent relié à une famille par école, avec le code famille de chaque école (code unique sur la plateforme), jamais par numéro de téléphone | Une correction d'une école ne touche pas les autres ; aucune fuite entre écoles ; un numéro mal saisi ne donne accès à rien |
| 2026-09-26 | Argent : devise choisie pour chaque barème (`FeeRule.currency`) ; taux USD → CDF fixe pour l'année, saisi par le comptable, corrigeable avec historique (nouvelle ligne) ; Q4 : taux toujours USD → CDF, FC → USD par division en `Decimal`, arrondi demi supérieur | Pratique des écoles (taux annuel) ; les paiements passés gardent leur taux ; pas d'erreur d'arrondi par l'inverse du taux |
| 2026-09-26 | Q1 : pas de modèle `PaymentSchedule` (échéancier particulier = `StudentCharge` `source=custom`) ; Q2 : pas de modèle `Receipt` (reçu = vue imprimable du paiement) | Suivre `04` ; un reçu n'a pas de vie propre en dehors du paiement |
| 2026-09-26 | Reçu : format choisi par l'école (thermique 58 / 80 mm, ou A6 / A5 / petit format sur A4 avec traits de découpe), 1 ou 2 exemplaires ; affiche reste à payer, taux utilisé, caissier, zone signature / cachet ; montant en lettres « Cent cinquante dollars américains et vingt-cinq centimes » (Q5, à ajuster sur le reçu actuel de l'ITIG) ; QR code dès la V1.0, signé par l'appareil (ECDSA P-256) pour vérifier un reçu imprimé hors ligne | Écoles équipées différemment ; reçu collé dans le cahier de l'élève ; lutte contre les faux reçus même avant la synchronisation |
| 2026-09-26 | Q3 : 9 rôles système (`head`, `study_director`, `discipline_master`, `accountant`, `cashier`, `secretary`, `promoter`, `teacher`, `parent`) ; nouvelle permission `classes.manage` ; Q7 : chef d'atelier = rôle personnalisé de l'école | Organigramme de l'ITIG (2 directeurs des études, 1 directeur de discipline) ; le directeur des études gère classes et inscriptions sans toucher à l'argent |
| 2026-09-26 | Q9 : nom Mwangaza, domaine `mwangaza.school` ; Q8 : couleur choisie par l'école (défaut `#0E5C6B`, contraste du texte vérifié ; `#003C6C` pour l'ITIG de démonstration) | `.cd`, `.com`, `.app` indisponibles ; aucune couleur d'école en dur |
| 2026-09-26 | Q6 : caisse (V1.0) d'abord, P1 2026 sur papier, bulletins avec Mwangaza à partir de la P2 / 1er semestre, ordre V1.1 puis V1.2 inchangé ; Q11 : deux modes d'impression du bulletin (complet, ou notes seules sur le formulaire pré-imprimé) | La P1 tombe avant la V1.2 ; les écoles utilisent parfois des bulletins officiels achetés |
| 2026-09-26 | Documents imprimables (reçus, listes, rapports, bulletins) : Claude propose le design dans le système de design, état « à valider », validé par la fusion de la PR | Même règle que les maquettes d'écrans ; pas d'attente des modèles de l'ITIG |
| 2026-09-26 | Qualité : mêmes commandes `make` en local, avant chaque commit (pre-commit, hooks locaux aux versions verrouillées, rien de téléchargé en plus) et en CI (GitHub Actions : PostgreSQL 16, schéma OpenAPI commité vérifié) | Un seul jeu d'outils et de versions ; une PR qui casse le lint, les tests ou le contrat d'API se voit tout de suite |
| 2026-09-26 | ESLint lit le TypeScript avec `typescript` 6.0 (racine du front) ; les applications gardent TypeScript 7 pour `tsc` | `typescript-eslint` 8.70 n'accepte pas TypeScript 7 (réécrit en Go, sans l'API JavaScript) ; à retirer dès qu'il la gère |
| 2026-09-26 | Prettier seulement sur le code du front (ni Markdown, ni lockfile, ni `openapi.yaml` généré) ; ruff seulement sur `backend/` | Les documents gardent leur mise en forme ; les fichiers générés restent identiques à leur générateur ; les outils des maquettes gardent le leur |
| 2026-09-26 | Une seule PR par tâche, toujours `base: main`, jamais empilée ; PR séparée seulement pour une décision à valider avant de continuer ou une réparation urgente ; contrôles GitHub verts avant de la donner ; description terminée par « À valider », « À tester toi-même », « Après la fusion » (`CLAUDE.md` « Travail avec GitHub ») | L'utilisateur relit et fusionne seul : une PR par tâche à relire, compréhensible sans lire le code ; les PR empilées (#78 puis #79) imposaient un ordre de fusion |
| 2026-09-26 | `School` créé dès 1.1 dans l'app `schools`, réduit à `code` (sous-domaine, contrôlé aussi par la base), `name`, `status` ; les autres champs de `04` § 1 arrivent avec leur tâche | Le middleware et `TenantModel` en ont besoin ; pas de champ sans usage ni test |
| 2026-09-26 | `TenantModel` refuse aussi, en écriture : une ligne d'une autre école, un changement d'école (transfert = copie), une clé étrangère vers une ligne d'une autre école, y compris par `bulk_create` | Défense en profondeur : une erreur de code ne peut pas mêler les données de deux écoles |
| 2026-09-26 | Middleware : écoles sous `SCHOOL_BASE_DOMAINS` (`mwangaza.school`, `localhost` en dev) ; domaine seul et sous-domaines réservés (`www`, `parents`, `admin`, `api`…) sans école ; école inconnue 404, suspendue 403 ; le rôle de l'utilisateur est vérifié par les permissions de l'API (1.2, 1.3) | DRF authentifie dans la vue, pas dans le middleware ; santé, portail et super-admin n'ont pas d'école |
| 2026-09-26 | UUID v7 écrit dans `apps/core/ids.py` (algorithme de `uuid.uuid7()` de Python 3.14 : compteur de 42 bits, 32 bits aléatoires) | Python 3.12 ne l'a pas ; pas de dépendance ; ordre croissant et identifiant non devinable |
| 2026-09-26 | Erreurs de l'API : `{"code", "detail"}` ; l'interface traduit à partir du `code` ; `detail` en `gettext` (texte source anglais), fichiers de traduction du serveur à la première tâche qui montre un texte du serveur tel quel | Même traduction côté interface (i18next) ; outils `gettext` pas encore installés |
| 2026-09-26 | `make demo` avancé en 1.1 (écoles `itig` et `volcans`) ; `GET /api/school/` public (code et nom) | L'utilisateur peut essayer le middleware tout de suite ; l'écran de connexion (1.6) affiche le nom de l'école |
| 2026-09-26 | ruff : règle RUF012 désactivée | Faux positifs sur les listes de configuration de Django (`Meta`, admin, serializers) |
| 2026-09-26 | `make` : les commandes qui ont besoin de la base démarrent PostgreSQL et Redis (cible `db-up`, sauf en CI) ; `make dev-local` en bash, Vite lancé app par app | Essai de l'utilisateur : `make migrate` échouait après `make stop`, Ctrl+C faisait planter `make dev-local` |
