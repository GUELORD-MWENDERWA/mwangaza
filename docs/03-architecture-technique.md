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
           Cloudflare (DNS, wildcard *.mwangaza.cd, cache)
                              │
                     VPS ─ Caddy (HTTPS)
        ┌─────────────────────┼─────────────────────────┐
  {ecole}.mwangaza.cd   parents.mwangaza.cd     admin.mwangaza.cd
   /app  → PWA Gestion   /  → PWA Portail        → super-admin
   /api  → Django        /api/portal → Django    (Django admin + écrans dédiés)
   /v/{id} → vérif reçu
        └─────────────────────┼─────────────────────────┘
                   Django (gunicorn) ── Celery ── Redis
                              │
                         PostgreSQL ──► sauvegardes continues vers stockage objet
```

- L'API de l'application Gestion est servie **sur le même sous-domaine que l'école** : l'école est déduite du nom d'hôte, les cookies restent sur la bonne origine.
- Le portail parents est sur un **domaine unique**, car une famille peut avoir des enfants dans plusieurs écoles.
- Plus tard, la racine `{ecole}.mwangaza.cd/` accueillera le site vitrine de l'école.

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
│   │   ├── finance/            # FeeType, FeeRule, Installment, Discount, Payment, Receipt, CashRegister, CashClosing, ExchangeRate
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

1. `TenantModel` (abstrait) : champ `school = ForeignKey(School)`, index composés commençant par `school`.
2. `TenantMiddleware` : lit le sous-domaine, charge l'école, la place dans un contexte de requête (`contextvars`). Refuse la requête si l'école est suspendue ou si l'utilisateur n'y a pas de rôle.
3. Manager par défaut `TenantManager` : filtre automatiquement sur l'école courante et **lève une erreur** si aucune école n'est définie (évite les fuites silencieuses). Un manager `all_schools` explicite existe pour le super-admin et le portail.
4. Tests obligatoires : pour chaque endpoint, un test crée deux écoles et vérifie qu'aucune donnée de l'une n'est visible depuis l'autre.
5. Plus tard (sécurité en profondeur) : Row Level Security PostgreSQL.

Entités **globales** (sans école) : `User`, `Family`, `Student` (identité), `School`. Entités **liées à une école** : tout le reste, dont `Enrollment` qui relie un élève à une école pour une année.

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
- Conversion : `ExchangeRate(school, date, from, to, rate)` ; le paiement enregistre `rate_used` et le montant dans la devise du frais. Arrondi documenté (demi supérieur à l'unité de la devise).
- Solde d'un élève = somme des montants dus (barèmes − réductions) − somme des paiements non annulés, par devise de frais. Calculé à la demande et mis en cache ; recalculable à tout moment.

## 7. Impression

- **Reçu thermique 80 mm** : page HTML dédiée avec CSS `@page { size: 80mm auto; margin: 0 }`, imprimée par la boîte de dialogue du navigateur (fonctionne hors-ligne). Configurer une fois l'imprimante par défaut sur le poste. Plus tard éventuellement : impression directe ESC/POS via Web Serial / WebUSB.
- **A4** : même principe hors-ligne ; PDF serveur (WeasyPrint) pour les documents générés en ligne (listes, situations, fiches).
- **QR code** généré dans le navigateur ; il pointe vers `https://{ecole}.mwangaza.cd/v/{receipt_uuid}`.

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
- **DNS et certificats** : Cloudflare (offre gratuite), certificat wildcard `*.mwangaza.cd`.
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
