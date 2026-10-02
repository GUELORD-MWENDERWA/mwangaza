# Suivi du projet

Ce fichier dit **où en est le projet**. Il est mis à jour à chaque étape (début et fin de tâche, décision, document reçu, blocage). Les cases à cocher restent dans `05-plan-de-travail.md` ; ici on garde l'état, l'avancement et le journal.

## État actuel

| | |
|---|---|
| Phase | V1.1 — plateforme, notifications, communication |
| Lot | V1.1 |
| Tâche en cours | aucune — 5.2.2 terminée (PR à fusionner) |
| Prochaine tâche | 5.3 ; mise en ligne (4.6.2, 4.7) quand l'utilisateur le décide |
| Issue GitHub | #133 |
| Branche | `tache/5.2.2-identite-console` ; dossier local : `~/Projets/mwangaza` |
| Dernière mise à jour | 2026-10-02 |

## Avancement

| Bloc | Fait | Total |
|---|:-:|:-:|
| Avant de coder (toi) | 2 | 4 |
| Semaine 1 — Socle | 9 | 9 |
| Semaine 2 — Élèves et frais | 9 | 9 |
| Semaine 3 — Caisse et hors-ligne | 17 | 17 |
| Semaine 4 — Rapports, portail, production | 14 | 16 |
| **V1.0** | **48** | **50** |
| V1.1 — plateforme, notifications, communication | 3 | 8 |
| V1.2 — carte unique et présences | 0 | 6 |
| V1.3 — personnel, paie, dépenses | 0 | 6 |
| V1.4 — notes, bulletins, vie scolaire | 0 | 9 |
| V2 | 0 | 15 |

Sur GitHub : onglet *Milestones* — un jalon par version (V1.0 à V1.4, V2), une issue par tâche (renumérotées le 2026-10-02).

## Bloquants et en attente

Liste complète et détaillée (maquettes M1–M20, informations I1–I18, décisions T1–T6) : `07-a-fournir.md` — plus rien n'y bloque le travail. Ce que l'utilisateur doit faire et comment : `../A-FAIRE.md`. Ici, seulement ce qui bloque bientôt.

| Sujet | Attendu de | Bloque |
|---|---|---|
| Mise en ligne : hébergement, domaine, stockage objet — **quand tu le décides** | toi | 4.6.2, 4.7 seulement ; rien d'autre n'en dépend |

## Questions ouvertes

À trancher au plus tard pendant la tâche indiquée. Une fois tranchée : déplacer dans le journal.

| # | Question | Pour | En attendant |
|---|---|---|---|
| Q12 | Découpage officiel de l'année au **primaire** (trimestres ? périodes et examens par trimestre ?) : pour proposer un modèle « primaire » à la création d'une année (C1) | avant la première école primaire (aucune en V1.0 : l'ITIG n'a pas de primaire) | pas de modèle « primaire » : une école du primaire part du modèle « 3 trimestres, 6 périodes, 3 examens » ou d'un découpage vide, et l'ajuste |

Q1 à Q11 tranchées le 2026-09-26 (voir le journal). Prochain numéro : Q13.

## Journal

Entrée la plus récente en haut. Format : date — titre, puis fait / tests / décisions / suite.

### 2026-10-02 — Tâche 5.2.2 : identité de la plateforme dans la console

- Fait : écran « Identité de la plateforme » de la console (`/identity` : nom, nom court, logo, icône, couleurs avec aperçu en direct, support, mentions légales, 5 dernières modifications), maquette `console/identite-plateforme` dessinée par Claude ; API `/api/console/platform/` (+ `logo/`, `icon/`) réservée au super-admin ; administration Django en lecture seule pour l'identité.
- Décision : journal de la plateforme à part (`PlatformAuditLog`, sans école, immuable jusque dans la base) ; il servira aux actions de 5.3–5.4 (`03`, journal des décisions).
- Tests : accès (403 / 404 hors console), journal (seulement ce qui change), couleur et fichiers refusés, remplacement des fichiers, immuabilité ; écran (enregistrement, refus sous le champ). 5.2 terminée.
- Suite : 5.3 (console — écoles).

### 2026-10-02 — Tâche 5.2.1 : console de la plateforme (socle)
- Fait : 5.2 découpée (5.2.1 ici, 5.2.2 identité ensuite). Troisième application `frontend/apps/console` (`admin.<domaine>`, port 5175, sans service worker) avec son propre design (maquette `console/tableau-de-bord` dessinée par Claude) : connexion du super-admin, tableau de bord de toutes les écoles (`GET /api/console/dashboard/` : écoles par statut, élèves, paiements du jour par devise, écoles les plus actives, santé du serveur) ; Caddy, Dockerfile, `make dev` / `dev-local`.
- Tests : `schools/tests/test_console.py` (refus hors super-admin, sans double authentification, ailleurs qu'à l'adresse de la console ; chiffres de deux écoles, annulé exclu ; connexion refusée à un comptable, jamais d'appareil de confiance ; Redis en panne), Vitest de l'écran, Playwright `console.spec.ts`, `textes.test.ts` étendu à la console.
- Décisions : `03` « Journal des décisions » (connexion à l'adresse de la console = celle de l'administration ; première connexion terminée dans l'administration ; jour du fuseau de la plateforme).
- Suite : 5.2.2 (écran « Identité de la plateforme »).

### 2026-10-02 — Tâche 5.1 : identité de la plateforme
- Fait : `PlatformSettings` (nom, nom court, logo, icône, couleurs, support, mentions légales), modifiable dans l'administration Django ; API publique `/api/platform/` (+ logo, icône, manifestes) ; lue par la Gestion, le Portail, les PDF, la vérification d'un reçu, l'administration, le TOTP et le guide ; `{{platform}}` dans toutes les traductions ; couleurs appliquées au thème ; contact du support sur « École suspendue » ; lien « Mentions légales » sous les connexions ; `make demo` remet l'identité de départ.
- Tests : `core/tests/test_platform.py` (publique même pour une école suspendue, nouveau nom partout, couleurs illisibles et icône refusées, édition par le super-admin, nom refusé dans les textes du serveur), `textes.test.ts` (nom refusé dans les textes du front), i18n (`setPlatformName`).
- Décisions : `03` « Journal des décisions » (pas de Pillow : icône PNG carrée ≥ 512 px ; le domaine reste dans `.env`).
- Suite : 5.2 (console de la plateforme, dont l'écran « Identité de la plateforme »).

### 2026-10-02 — Tâche 4.10 : guide de la V1.0 en PDF
- Fait : `docs/guide/guide-v1.0.pdf` (16 pages) : la version en bref, se connecter, rôle par rôle (directeur, promoteur, comptable, caissier, secrétaire, études, discipline, enseignant, parent, super-admin) avec captures sur `make demo`, hors ligne et contrôle de l'argent, ce qui manque et V1.1 → V2. `make guide` : `frontend/guide/` (config Playwright à part, `captures.spec.ts`, `guide.html`). Trouvé en chemin : l'écran d'activation de la double authentification débordait de 32 px à 390 px (grilles sans colonne bornée dans `AuthFrame` et `TwoFactorSetup`), corrigé.
- Tests : aucun test automatique (document) ; le script échoue si un écran ou une capture manque ; `make lint`.
- Décisions : PDF par Chromium de Playwright, sans dépendance ; PDF dans Git, captures hors Git ; pas dans la CI ; guide en français ; régénéré à la fin de chaque version (`05`).
- Suite : fusion, puis 5.1 (V1.1).

### 2026-10-02 — Tâche 4.9 : invitation des familles au portail
- Fait : écran « Invitations au portail » (`/app/students/invitations`) : familles activées par classe et pour l'école, familles de la classe avec l'état de leur portail (pas encore activé, activé, numéro manquant, code expiré, suspendu) ; lettres de la classe en PDF (deux par A4) ; lettre et message WhatsApp / SMS par famille, aussi depuis la fiche famille ; le Portail préremplit le code venu du QR (`/activate#…`). Maquettes `invitations-portail` et `lettre-invitation` dessinées. Démo : ~1 famille sur 3 activée.
- Avant : GitHub réaligné sur le nouveau découpage (jalons V1.3, V1.4 ; 35 issues renumérotées, 10 créées dont #130 ; #36, 4.8 retirée, fermée).
- Tests : `test_invitations.py` (états, compte par classe, lettres et message réservés à `students.edit`, journal, autre école) ; Vitest (message et liens, boutons masqués au caissier ; code prérempli). Décisions : `03` (journal du 2026-10-02).
- Suite : fusion, puis 4.10.

### 2026-10-02 — Découpage des versions revu
- Demande de l'utilisateur : la V1.0 est mise de côté (mise en ligne quand il le décide) ; **on n'attend rien de l'ITIG** (4.8 retirée) ; la V1.0 se clôt avec l'invitation des familles au portail (4.9, H7) et un guide PDF de la version, rôle par rôle, avec ses limites (4.10, I5).
- Nouvelles versions : V1.1 plateforme (identité configurable, console avec son propre design au lieu de l'administration Django), notifications sur l'écran même application fermée, communication ; V1.2 carte unique (puce NFC + QR + photo, liaison en une seconde) et présences (téléphone Android enregistré, ESP32, caméra QR) ; V1.3 personnel, paie, dépenses ; V1.4 notes et bulletins ; V2 renumérotée 9.x.
- Recherches : Web NFC seulement dans Chrome Android (numéro de série, lecture, écriture ; pas sur iPhone, d'où le QR sur la même carte) ; cartes NTAG215 / 216 ; offre gratuite d'Oracle réduite à 2 cœurs et 12 Go depuis juin 2026, reprise des serveurs peu utilisés.
- Mis à jour : `01`, `02`, `03` (§ 2, 3, 10, journal des décisions), `04`, `05`, `07`, `A-FAIRE.md`, `CLAUDE.md` (règle 9 étendue à la plateforme), skills, `maquettes/README.md`, `firmware/README.md`. Suite : fusion, jalons et issues GitHub, puis `/tache 4.9`.

### 2026-10-02 — Tâche 4.6.1 : production prête, essayée sur la machine
- 4.6 découpée avec l'accord de l'utilisateur, car le domaine, Cloudflare et le VPS ne sont pas encore achetés. Fait : `infra/Dockerfile` (front construit, Django + gunicorn, Caddy), `infra/docker-compose.yml`, `infra/Caddyfile` (sous-domaines, `/v/*`, compression, cache des PWA), `infra/.env.example`, `make prod-local` ; la vraie adresse du visiteur (Cloudflare → `X-Real-IP` → `CLIENT_IP_HEADER`) est utilisée par la limitation des tentatives. Dépendance acceptée : gunicorn.
- Tests : adresse du proxy prise en production, ignorée sinon, valeur invalide ignorée ; blocage par adresse derrière le proxy. Essai réel `make prod-local` : 5 conteneurs en bonne santé ; routes, cache, compression et HTTPS vérifiés par `curl` ; en-têtes d'adresse inventés ignorés. La première construction a échoué sur la connexion lente (téléchargement Python expiré) : caches de téléchargement et délais longs ajoutés à l'image.
- Décisions (`03`) : certificat d'origine Cloudflare au lieu d'un plugin Caddy, images construites sur le VPS, domaine nu → portail, fichiers des écoles sur un volume jusqu'à la 4.7.
- Suite : 4.6.2 (mise en ligne) dès que le domaine, Cloudflare et le VPS existent (`A-FAIRE.md` n° 17).

### 2026-10-02 — Tâche 4.5.2 : traductions
- Serveur en français : 550 textes traduits (administration, messages d'erreur, journal, PDF, Excel), 19 traductions devinées par gettext corrigées ; champs communs (créé le, modifié le, créé par, école) traduisibles (migrations sans SQL). La langue du serveur suit celle choisie dans l'application (cookie `django_language` posé par la Gestion et le Portail) et non plus celle du navigateur.
- Anglais des deux applications relu : vocabulaire harmonisé (log in, installment, student number, track) ; corrigé au passage : l'action « Paiement annulé » du journal affichait un message d'erreur (fr et en).
- Tests : catalogue français complet et compilé, serveur dans la langue de l'interface (2 cas), cookie posé par le front ; 6 tests du serveur attendaient un texte anglais : texte attendu en français. Tests du serveur lancés en local (le changement touche tous les modules) : verts.
- Suite : 4.6 (production : VPS, Caddy, Cloudflare ; attend le domaine et les comptes, `A-FAIRE.md` n° 17).

### 2026-10-02 — Tâche 4.5.1 : guides de première connexion
- 4.5 découpée : 4.5.1 guides, 4.5.2 traductions (≈ 520 textes du serveur à traduire en français, relecture de l'anglais).
- Gestion : guide du caissier (5 étapes, caisse) et du comptable (6 étapes : taux, frais, élèves, annulations, clôtures, impayés), choisi par le rôle système, étapes selon les droits ; vrai élément entouré, reste assombri, page utilisable ; progression par utilisateur et par appareil ; « Aide et guide » en bas du menu. Portail : `/guide` après l'activation (puis « Installer »), « Revoir le guide » du profil.
- Corrigé au passage : après l'activation, le portail allait à l'accueil au lieu d'« Installer » (redirection de la page de connexion trop rapide).
- Tests : 2 Vitest Gestion (démarrage, reprise, passer, relance ; étapes selon les droits), 1 Portail ; Playwright : la caissière passe le guide après la connexion. Suite : 4.5.2.

### 2026-10-02 — Façon de travailler : tous les `.md` à jour à chaque tâche
- Demande de l'utilisateur : à la fin de chaque tâche, mettre à jour **tous** les `.md` que la tâche rend faux, pas seulement le suivi ; les skills suivent. Règle et liste des fichiers dans `CLAUDE.md` (« Suivi du projet », fin d'une tâche), skill `tache` étape 5.3, contrôle n° 15 de `verifier`, rappels dans `backend` et `ecran`.
- Rattrapage (en retard depuis la semaine 2) : `A-FAIRE.md` § 11 (écrans des semaines 2 à 4, portail, `make demo`, `make test-e2e`) et nouvelle action n° 17 (domaine, Cloudflare, VPS : la 4.6 vient après la 4.5) ; `CLAUDE.md` (`make demo`, API et écrans du portail) ; `07` § 4 (élèves, frais, caisse, annonces, portail) ; `maquettes/README.md` (écarts des écrans 4.2 et 4.4.5) ; skill `ecran` et `07` § 1 alignées sur la décision du 2026-09-29 (maquette dessinée → coder sans attendre l'accord).
- Correction trouvée par la CI de cette PR (parcours Playwright de la caisse, 3 échecs de suite) : deux F9 avant le réaffichage lançaient deux fois l'enregistrement — un seul paiement (même identifiant), mais **deux reçus imprimés**. Verrou immédiat dans `CollectPanel.tsx` ; test d'écran : deux F9 → un seul envoi (échoue sans la correction).
- Suite : fusionner la PR, puis 4.5.

### 2026-10-02 — Tâche 4.4.5 : coordonnées des parents
- Fait : `ContactChange` (une demande par école reliée, seulement ce qui diffère de sa fiche, une seule en attente par famille) ; portail `GET/POST /api/portal/profile/` et écran « Mon profil » (adresse, e-mail, contact d'urgence, langue, déconnexion, entrée Profil de la barre) ; Gestion `/api/contact-changes/` (+ `apply/`, `dismiss/`, droit `students.edit`) et écran « Demandes des parents » ; `make demo` : 3 demandes à l'ITIG. La 4.4 (Portail) est finie ; tous les écrans du menu V1.0 sont construits.
- Tests : 3 tests serveur (une demande par école, remplacée au nouvel envoi, rien pour un accès suspendu ; appliquer : fiche de cette école seulement, autre école 404, enseignant 403, journal, déjà traitée 409, requêtes en nombre fixe ; ne pas appliquer : fiche gardée, journal) ; 2 tests d'écran. Test « bientôt disponible » retiré (plus d'écran V1.0 à venir).
- Décisions : `02` H5 et `04` priment sur la note de la maquette M18 — le secrétariat **applique** la demande (rien ne change sans lui) au lieu de « déjà enregistré, marquer comme vu » ; « Téléphone secondaire » remplacé par le contact d'urgence (pas de champ au modèle) ; aucune école ne voit les autres écoles de la famille.
- Suite : 4.5 (guides de première connexion, traductions).

### 2026-10-02 — Tâche 4.4.4 : annonces dans le portail
- Fait : `AnnouncementRead` (annonce lue par une famille, une fois) ; portail `GET /api/portal/announcements/` (écoles reliées, `?family=` pour une seule), `POST …/read/`, `GET …/{id}/attachment/` ; écran « Annonces » du Portail (puces par école, « Nouvelle », pièce jointe, entrée de la barre du bas, 1re page gardée hors connexion) ; « lue par N familles » dans la liste de la Gestion ; `make demo` : une famille sur deux a lu les annonces, jamais celle du compte du portail.
- Tests : 2 tests serveur (classes visées, archivée, année passée, autre école, accès ou école suspendus ; marquage une fois par famille et compté dans la bonne école ; PDF refusé hors destinataires ; requêtes en nombre fixe) ; 1 test d'écran. Corrigé au passage : l'ordre de la liste de la Gestion (le comptage le faisait perdre).
- Décisions : une annonce s'affiche si elle a été publiée après la fin de l'année scolaire précédente (celles de la rentrée, publiées pendant les vacances, restent) ; elle est marquée lue dès qu'elle s'affiche (le message entier est sur la carte).
- Suite : 4.4.5 (coordonnées, « Demandes des parents »).

### 2026-10-02 — Façon de travailler : plus d'attente à vide
- Mesuré sur 4.4.3 : suite complète en local ≈ 9 min, puis la CI refait les mêmes tests en ≈ 5 min. Décidé à ta demande : plus de `make test` en local (lint + tests des modules touchés seulement, suite complète par la CI) ; un seul push à la fin ; la PR est donnée tout de suite, contrôles en cours, et Claude confirme « ✅ » ensuite (`CLAUDE.md`, skill `tache`, `A-FAIRE.md` § 10). Commencer la tâche suivante pendant la CI : non (mêmes fichiers, PR empilée interdite, une conversation par tâche).

### 2026-10-02 — Tâche 4.4.3 : paiements et reçus (Portail)
- Fait : `GET /api/portal/children/{id}/` (frais dus de l'année avec leur état — payé, payé d'avance, partiel, en retard, à venir —, solde par devise, paiements, annulés marqués), `…/photo/` (seulement avec le consentement du parent, aussi sur les cartes de l'accueil), `GET /api/portal/payments/{id}/receipt/` (reçu PDF A5 par le serveur, même contenu que celui de la caisse, mention « Copie téléchargée sur le portail », QR de vérification). Portail : écran des paiements d'un enfant, barre de navigation en bas (Accueil, Paiements), page gardée hors connexion. Montant en lettres porté en Python (`core/money.py`, mêmes règles que la caisse).
- Tests : 3 tests serveur (compte d'une autre famille ou d'une autre école : ni enfant, ni photo, ni reçu ; états et montants par devise ; reçu d'un paiement annulé ou d'une famille suspendue refusé ; photo sans consentement refusée) + montant en lettres ; 1 test d'écran.
- Décisions (`03`) : reçu du portail produit par le serveur, marqué « Copie », jamais pour un paiement annulé, téléchargement non noté au journal.
- Suite : 4.4.4 (annonces dans le portail, « lue par N familles »).

### 2026-10-02 — Tâche 4.4.2 : enfants et installable (Portail)
- Fait : 4.4 redécoupée en 5 (paiements et reçus à part : 4.4.3). Serveur : `GET /api/portal/families/` (familles reliées au compte, une par école, enfants inscrits avec la situation par devise, premier frais en retard, dernier paiement), `POST /api/portal/families/link/` (« Ajouter un enfant d'une autre école »), « Suspendre l'accès » (`Family.portal_suspended_at`, `POST /api/families/{id}/portal-access/`). Portail : accueil, ajout d'une école, écran « Installer » et bandeau, PWA (cache des données vidé à la déconnexion). Gestion : bouton sur la fiche famille. `make demo` : compte du portail `0002000001`, code des Volcans affiché.
- Tests : 4 tests serveur (familles du compte seulement, montants par devise, ajout refusé sans le bon numéro, suspension 403 / autre école 404 / audit, école ou famille suspendue sans données) ; 2 tests d'écrans.
- Décisions (`03`) : ajout d'une école = code + numéro du compte égal au contact principal de cette école ; famille suspendue : rien affiché, code refusé (activation, ajout, mot de passe oublié).
- Suite : 4.4.3 (paiements d'un enfant, reçus PDF, photo).

### 2026-10-02 — Tâche 4.4.1 : accès au portail des familles
- Fait : 4.4 découpée en 4 sous-tâches (accès, enfants et paiements, annonces, coordonnées). App `portal` (`/api/portal/auth/activate/`, `login/`, `reset/`, `me/`, refusés à l'adresse d'une école) ; « Nouveau code » et état du portail sur la fiche famille (`Family.code_expires_at`) ; Portail : coquille (Tailwind, `ui`, `i18n`, client API), écrans connexion, activation, mot de passe oublié, accueil provisoire. Traduction des erreurs de l'API déplacée dans `@mwangaza/i18n` (partagée).
- Tests : 8 tests serveur (même erreur pour un mauvais numéro ou code, blocage après 5 essais, code consommé, autres sessions fermées, compte du personnel refusé, école suspendue, 403 sans `students.edit`, 404 depuis une autre école, audit) ; 2 tests d'écrans. `make test` : 908 + 216 verts.
- Décisions : portail sans double authentification, « Rester connecté » 30 jours, nouveau code à usage unique valable 30 jours, mot de passe oublié refusé pour un compte du personnel (`03`).
- Suite : 4.4.2 (enfants, paiements, installable, « Suspendre l'accès »).

### 2026-10-01 — Tâche 4.3 : annonces côté école
- Fait : app `notifications`, `Announcement` et `/api/announcements/` (`announcements.publish`) : publication à toutes les familles ou à certaines classes de l'année, PDF joint (jamais public), nombre de familles touchées (« Publier pour 156 familles »), archivage ; écran « Annonces » (formulaire, aperçu, liste Publiées / Archivées) ; 3 annonces fictives par école dans `make demo`.
- Tests : isolation (école beta : ni liste, ni archivage, ni PDF, ni classes de l'autre école), 403 caissier, familles touchées (fratrie une fois, élève qui a abandonné exclu), PDF refusé, audit de la publication et de l'archivage ; écran : classe exigée, classes envoyées.
- Décisions : plusieurs classes par annonce (comme la maquette, `04` mis à jour) ; jamais modifiée après publication, seulement archivée ; destinataire « Personnel » reporté à 5.8 et « lue par N familles » à 4.4 (`05`).
- Suite : 4.4 (portail des familles).

### 2026-10-01 — Tâche 4.2 : tableau de bord directeur et seuils d'alerte
- Fait : `GET /api/dashboard/` (`finance.view_reports` : directeur, comptable, promoteur) et écran « Tableau de bord » : encaissé aujourd'hui et ce mois (comparé à la même période du mois d'avant), 21 derniers jours, impayés échus, taux de recouvrement, effectifs par classe, option et sexe, recouvrement par classe (→ impayés filtrés), 5 derniers paiements ; alertes : annulations à valider, caisses pas clôturées, écarts et annulations au-delà des seuils. Seuils de l'école dans les paramètres (carte « Alertes au directeur », M5).
- Tests : isolation (école beta), 403 caissier, montants par devise sans paiement annulé, recouvrement à 37 % avec deux devises, alertes au seuil, seuils fusionnés et notés au journal ; écran : alertes, liens selon les droits (promoteur). 15 requêtes fixes, 0,8 s sur 800 élèves.
- Décisions : recouvrement avec l'autre devise au taux de l'année (pourcentage seulement) ; alertes sur 7 jours (`03`). Écarts à la maquette : ni sélecteur de période ni export (hors G3).
- Suite : 4.3 (annonces côté école).

### 2026-09-30 — Tâche 4.1.2 : situation financière imprimable
- Fait : situation financière A4 (PDF + aperçu) depuis l'onglet Finances et groupée depuis les Impayés (cases à cocher, une page par élève) ; QR de vérification publique `/v/s/<jeton>` ; colonnes « Échu non payé », « Paiements » et filtre « Paiement » de la liste des élèves (droit de lecture des frais).
- Tests : 888 serveur, 211 front ; lint vert. Isolation (400 / 404), 403 secrétaire, montants par devise, audit du PDF.
- Décisions (`03`) : jeton signé par le serveur, sel propre à l'école, sans table ; PDF noté au journal ; pied « Signature et cachet de l'école ».
- Suite : 4.2 (tableau de bord directeur, seuils d'alerte).

### 2026-09-30 — Tâche 4.1.1 : impayés
- Fait : 4.1 découpée (situation financière et colonnes de la liste des élèves → 4.1.2). Écran « Impayés » (maquette `impayes`) : chiffres clés, filtres classe / frais / tranche / retard / devise / tri dans l'adresse, ligne → fiche élève (Finances) ; écran « Exporter » (maquette `impayes-export`) : aperçu, PDF A4 à l'italienne par classe ou liste unique, Excel une ligne par frais en retard ; `/api/unpaid/` (liste paginée, `summary/`, `export/`), exports Excel et PDF notés au journal d'audit.
- Décisions (`03`) : même calcul que le solde de la fiche ; élèves actifs seulement ; filtre « retard de plus de N jours » appliqué à chaque frais ; JIT de PostgreSQL coupé (0,75 s perdues sur les rapports).
- Tests : 884 serveur, 210 front ; lint vert. ~0,7 s par appel sur les 800 élèves de la démo.
- Suite : 4.1.2 (situation financière imprimable, colonnes de la liste des élèves).

### 2026-09-30 — Tâche 3.8.3 : clôtures de caisse vues par le comptable
- Fait : écran « Clôtures de caisse » (M16) en lecture seule (`finance.view_reports`) : par mois et par caisse, attendu / compté / écart par devise, sessions pas clôturées (bandeau), paiements arrivés après la clôture, détail, bordereau du caissier, paiements de la session, export Excel ; `/api/cash-closings/` (liste, `summary/`, détail, `export/`). Duplicata sur l'appareil : crédits utilisés avant le paiement comptés (`credit_uses`). Démo : l'écart de 5,00 $ passe sur la session la plus récente (après `make reset-db`).
- Décisions (`03`) : le bordereau et l'attendu d'une session close ne comptent que les paiements reçus avant la clôture ; « non clôturée » = ouverte avant aujourd'hui.
- Tests : 880 serveur, 208 front, Playwright ; lint vert. Semaine 3 terminée.
- Suite : 4.1 (impayés).

### 2026-09-30 — Tâche 3.8.2 : clôture de caisse par le caissier
- Fait : 3.8 découpée à nouveau (écran du comptable → 3.8.3). `CashClosing` immuable par devise (attendu, compté, écart, explication), `GET/POST /api/cash-sessions/{id}/closing|close/`, opération hors ligne `cash_session.close` ; écran « Clôturer » (maquette `caisse-cloture`) en ligne et sur l'appareil, bordereau imprimé ; démo : clôtures des sessions passées (une avec − 5,00 $ expliqué).
- Décision (`03`) : hors ligne, l'argent est déjà reçu → ouverture hors ligne jamais refusée (caisse prise…), paiement hors ligne d'une session close gardé hors de l'attendu figé.
- Tests : 879 serveur, 206 front, 14 Playwright (clôture sans réseau reçue une fois) ; lint vert.
- Suite : 3.8.3 (clôtures vues par le comptable, M16).

### 2026-09-29 — Tâche 3.8.1 : annulation d'un paiement

- **Fait** : la 3.8 est découpée (3.8.1 annulation, 3.8.2 clôture). Demande d'annulation avec motif depuis la caisse (« Annuler… », par la file sur un appareil mémorisé, avec ou sans réseau) ou depuis « Crédits d'élèves » ; écran « Annulations » (en attente / validées / refusées) ; validation par un autre compte → reçu d'annulation `ITIG-AN-26-…` imprimé, crédits nés du paiement annulés ; refus. Maquette `demande-annulation` dessinée par Claude. Démo : demandes en attente, validée, refusée.
- **Tests** : 874 serveur (isolation, 403, sa propre demande, numéro de série, crédits de réduction et surplus hors ligne annulés, opération hors ligne une seule fois, audit), 203 front (dialogue, validation et impression, duplicata exact), lint vert, capture à 390 px.
- **Décisions** : journal des décisions de `03` (2026-09-29, « Annulation d'un paiement »).
- **Suite** : 3.8.2 (clôture de caisse).

### 2026-09-29 — Tâche 3.7.2 : appareils de l'école

- **Fait** : écran « Appareils et synchro » (maquette `appareils-synchro`) : appareils mémorisés de l'école (préfixe, compte, en ligne ou non, dernier contact) et « Révoquer » pour un responsable (`roles.manage`) ; carte « Cet appareil » (dernière synchro, file, données locales, stockage, dernier reçu, version) et file d'attente pour tout compte qui se synchronise. Un appareil révoqué efface aussi sa base locale quand il se reconnecte.
- **Tests** : 868 serveur (isolation, 403, audit de la révocation, dernier contact), 200 front (effacement à la reconnexion, révocation, caissier sans la liste de l'école), lint vert, capture à 390 px.
- **Décisions** (`03`) : entrée du menu visible de qui se synchronise ; pas de colonne « En attente » ni de bouton « Autoriser un appareil » ; avertissement de perte de la file à la révocation.
- **Suite** : 3.8 (annulations et clôture de caisse).

### 2026-09-29 — Tâche 3.7.1 : PIN de déverrouillage et démarrage sans réseau

- **Fait** : 3.7 découpée (3.7.1 PIN, 3.7.2 appareils de l'école). Carte « Code PIN de déverrouillage » dans Mon compte (4 chiffres, propre à l'appareil mémorisé, empreinte PBKDF2 sur l'appareil) ; sans réponse du serveur au démarrage, écran de déverrouillage (maquette `deverrouillage-pin`) au lieu de « Hors ligne », puis l'application rouvre avec le compte et l'école gardés sur l'appareil.
- **Tests** : 866 serveur, 198 front (dont `lib/pin.test.ts` : 5 codes faux, 7 jours, déconnexion, codes faibles), nouveau parcours Playwright (PIN défini, serveur coupé, code faux puis juste, caisse ouverte et paiement hors ligne, synchronisés au retour), lint vert.
- **Décisions** (`03`) : PIN jamais envoyé au serveur ni audité ; « Se déconnecter » exige le mot de passe avant le prochain déverrouillage ; 7 jours fixes pour toute la plateforme.
- **Suite** : 3.7.2 (appareils de l'école, écran « Appareils et synchro »).

### 2026-09-29 — Tâche 3.6.2 : crédit à la caisse

- **Fait** : à la caisse, bandeau « Crédit de … à utiliser » (origine, ce qu'il paiera) et « Utiliser le crédit », en ligne et hors ligne (opération `credit.use`, crédits envoyés à l'appareil avec l'inscription) ; carte du crédit sur la fiche élève (Finances), lien « Traiter le crédit » vers Crédits d'élèves.
- **Tests** : 866 serveur, 192 front, 13 parcours Playwright, lint vert ; isolation, 403, `credit.use` rejoué une fois, audit du caissier, pas de double comptage sur l'appareil.
- **Décisions** : le caissier peut utiliser un crédit (répartition automatique seulement, `03`) ; duplicata hors ligne sans les crédits utilisés → noté en 3.8.
- **Suite** : 3.7 (PIN hors ligne, appareils et synchro).

### 2026-09-29 — Tâche 3.6.1 : crédits d'élèves

- **Fait** : 3.6 découpée (3.6.1 / 3.6.2, validé). `StudentCredit` et `CreditAllocation` [I] ; crédit créé par un paiement hors ligne en trop ou par une réduction sur une tranche payée (seulement l'écart), annulé si la réduction est retirée ; « Utiliser le crédit » (comptable) sur les échéances les plus anciennes de sa devise ; API `/api/student-credits/` ; écran « Crédits d'élèves » (M14) avec justificatif imprimable ; colonnes « Déjà payé » / « Effet » du dialogue de réduction ; `make demo` : deux crédits par école.
- **Tests** : 865 serveur, 190 front, 13 parcours Playwright, lint vert ; isolation, 403, argent (payé + crédit = argent reçu), audit, immuabilité.
- **Décisions** : utiliser un crédit ne crée pas de paiement (validé) ; payé d'un frais plafonné à ce qu'il doit (`03`).
- **Suite** : 3.6.2 (crédit à la caisse, en ligne et hors ligne ; crédit sur la fiche élève).

### 2026-09-29 — Tâche 3.5.2 : ouverture et réimpression hors ligne, QR signé
- Fait : sur un appareil mémorisé, la caisse s'ouvre aussi sans réseau (opération `cash_session.open`, refus affiché sur l'écran d'ouverture) ; duplicata fait sur l'appareil et noté au journal par la file (`payment.reprint`) ; chaque reçu imprimé sur l'appareil porte un QR code signé ; `/v/…` : « en attente de synchronisation », « falsifié ». 3.5 terminée.
- Tests : 4 pytest (ouverture + encaissement + duplicata envoyés deux fois, caisse prise, isolation, page signée / falsifiée / appareil déconnecté / refusé), 2 Vitest (solde du duplicata, signature), Playwright caisse refait : ouverture sans réseau, deux encaissements, duplicata, page `/v/` vérifiée avant la synchro, aucun doublon.
- Décisions (`03`) : ouverture par la file ; duplicata sur l'appareil ; signature à l'impression, sans `Payment.receipt_signature` (`04` corrigé) ; ajout à la 3.8 : ouverture hors ligne refusée et ses encaissements.
- Suite : PR #108 à fusionner, puis 3.6.

### 2026-09-29 — Tâche 3.5.1 : encaisser hors ligne
- Fait : 3.5 découpée (3.5.1 encaisser ; 3.5.2 ouverture et réimpression hors ligne, QR signé). Sur un appareil mémorisé, la caisse lit la base de l'appareil (recherche, frais dus, solde, paiements de la session) et encaisse **toujours par la file**, avec ou sans réseau : reçu imprimé aussitôt avec le numéro de l'appareil (`ITIG-P1-26-000001`), envoyé dans la seconde s'il y a du réseau ; « en attente » / « refusé » dans la liste ; page « stockage refusé » avec « Continuer en ligne seulement » ; `Payment.cash_session` exposé.
- Tests : 4 Vitest (reçu et solde après paiement, paiement compté une seule fois, refusé jamais, numéros), moteur (envoyées gardées jusqu'à la descente), Playwright : un encaissement en ligne, deux sans réseau, numéros consécutifs, aucun doublon, 20 $ payés côté serveur.
- Décisions (`03`) : toujours par la file sur un appareil mémorisé (accord de l'utilisateur) ; opération appliquée gardée (`sent`) jusqu'à la fin de la descente ; séquence des reçus jamais reculée ; tuteur absent de l'encaissement sur l'appareil.
- Suite : PR #107 à fusionner, puis 3.5.2.

### 2026-09-29 — Tâche 3.4 : synchronisation dans le navigateur
- Fait : base Dexie par appareil mémorisé (inscriptions, configuration, file d'opérations) ; synchronisation à l'ouverture, au retour du réseau, toutes les 60 s et « Synchroniser maintenant » (envoi, puis instantané ou changements) ; indicateur complet avec détail ; bandeau « stockage refusé » ; mise à jour installée seulement file vide ; appareil déconnecté → données effacées.
- Tests : 6 du moteur (instantané repris après coupure, changements, envoi par 100, refus gardés, réseau coupé, appareil déconnecté), 1 de la mise à jour, 1 Playwright (800 inscriptions sur l'appareil, hors ligne puis retour).
- Décisions (`03`) : état du serveur jamais modifié sur l'appareil, opérations superposées (3.5) ; bandeau en 3.4, page bloquante sur la caisse hors ligne en 3.5 ; écran « Appareils et synchro » et démarrage sans réseau → 3.7.
- Suite : PR #106 à fusionner, puis 3.5 — caisse hors-ligne complète.

### 2026-09-29 — Tâche 3.3.2 : synchronisation serveur
- Fait : `SyncOperation`, `ChangeLog` ; `/api/sync/snapshot/` (pages d'inscriptions + configuration), `/pull/` (changements depuis un numéro), `/push/` (opérations appliquées une fois) ; opération `payment.create` (numéro de reçu de l'appareil, heure de l'appareil) ; `Payment.device` et `synced_at`. Rien de visible : l'écran vient en 3.4.
- Tests : 8 nouveaux (isolation snapshot / pull / push, droits, même lot deux fois → un paiement, deux caisses hors ligne → deux paiements gardés, refus gardé, changement validé après une lecture jamais perdu).
- Décisions (`03`) : une ligne de `ChangeLog` par entité, numéro donné à la lecture sous verrou ; entités `enrollment` et `config` ; surplus hors ligne jamais refusé (crédit en 3.6) ; ajouts au plan : 3.6 (crédit du surplus), 3.8 (opérations d'annulation et de clôture).
- Suite : PR #105 à fusionner, puis 3.4 — front hors ligne (Dexie, file d'opérations).

### 2026-09-28 — Tâche 3.3.1 : appareils
- Fait : 3.3 découpée (3.3.1 appareils, 3.3.2 synchronisation serveur ; signature vérifiée sur `/v/` en 3.5). App `sync` : `Device` (préfixe `P1`, `P2`…, clé publique ECDSA créée par le navigateur, session fermée à la révocation) ; case « Se souvenir de cet appareil » (cochée) ; carte « Appareils connectés » de Mon compte avec « Déconnecter » ; appareil et heure de l'appareil dans le journal d'audit (écran et export Excel) ; démo : un poste par caissier et secrétaire.
- Tests : autre école ou autre compte → 404 ; sans appartenance → 403 ; préfixes jamais redonnés ni égaux à un code de caisse ; révocation (session fermée, audit) ; signature WebCrypto réelle vérifiée par le serveur ; Playwright : « cet appareil » après la connexion.
- Décisions (`03`) : préfixe `P{n}` ; clé privée dans une base IndexedDB à part, un appareil par compte ; tout membre actif gère ses propres appareils (pas de code de permission).
- Suite : PR #104 à fusionner, puis 3.3.2 — synchronisation serveur.

### 2026-09-28 — Tâche 3.2.3 : vérification publique d'un reçu
- Fait : page `/v/{id}` ouverte par le QR code du reçu (sans connexion, sans JavaScript) : reçu authentique, annulé le …, ou inconnu ; école, numéro, date, élève en initiales et classe, montant ; jamais en cache ni indexée ; QR code de l'adresse du portail sur la fiche d'inscription (cadre du code famille).
- Tests : reçu valide sans nom ni matricule, puis annulé ; reçu d'une autre école ou inconnu = « inconnu » (404) ; QR code de la fiche seulement avec le code famille, dessiné dans le PDF.
- Décisions (`03`) : page rendue par Django (le Portail React vient en 4.4) ; `segno` ajouté avec l'accord de l'utilisateur ; « falsifié » et « émis hors ligne » en 3.3 (signature) ; Caddy `/v/*` → Django en 4.6.
- Suite : 3.3 — app `sync`.

### 2026-09-28 — Tâche 3.2.2 : reçu dans le navigateur
- Fait : reçu imprimé au format de l'école (thermique 80 / 58 mm ; A6, A5 ou petit format sur A4 avec traits de découpe ; 1 ou 2 exemplaires), montant en lettres, solde juste après le paiement, QR code vers `/v/{id}` ; « Encaisser et imprimer » (F9), « Réimprimer » (DUPLICATA, noté au journal), « Test » de l'imprimante à l'ouverture de caisse ; `POST /api/payments/{id}/reprint/`.
- Tests : solde du reçu (paiement suivant et annulation plus tardive ignorés), réimpression auditée et refusée pour un paiement annulé, isolation et droits de `reprint` ; montant en lettres (13 cas) ; écran encaisser → reçu → duplicata ; Playwright caisse : un reçu imprimé.
- Décisions (`03`) : pas de `uqr` (`qrcode-generator` déjà installé) ; montant en lettres toujours en français ; réglages du reçu publics dans `/api/school/`.
- Suite : 3.2.3 (page publique de vérification `/v/{id}`).

### 2026-09-28 — Tâche 3.1.2 : écrans de caisse en ligne
- Fait : page « Caisse » : ouverture (caisse libre ou occupée, par qui, depuis quand), accueil (recherche de l'élève, totaux par devise, paiements de la session, récents), encaissement (frais à payer cochables, montant, « Tout le retard » / « Toute l'année », conversion, répartition, surplus refusé, F9) ; carte « Caisses » des paramètres ; `open_session` sur `/api/cash-registers/`.
- Tests : `convert` identique au serveur (7 cas d'arrondi), répartition (3), écrans (ouverture ; répartition envoyée, même `id` après une coupure, surplus bloqué), Playwright caissière (ouvre, encaisse avec double F9, un seul paiement).
- Décisions : répartition calculée dans le navigateur et envoyée telle quelle (`03`) ; bouton « Encaisser » (impression du reçu : 3.2) ; pas de montants rapides fixes (20 $, 50 $) : en dur pour une école.
- Suite : 3.2 (reçu).

### 2026-09-28 — Tâche 3.2.1 : paramètres des reçus
- Fait : 3.2 découpée en trois avec l'accord de l'utilisateur (3.2.1 paramètres, 3.2.2 reçu dans le navigateur, 3.2.3 vérification publique) ; `School.settings.receipt` (imprimante, taille sur A4, exemplaires, en-tête, mention) et `School.logo_monochrome` ; carte « Reçus » et logo noir et blanc dans les paramètres ; `make demo` : réglages fictifs.
- Tests : réglages fusionnés et journalisés, valeurs refusées, 403, logo noir et blanc isolé par école ; écran : envoi des réglages. `make test` : 835 + 169.
- Décisions : bibliothèque `uqr` acceptée pour le QR code (installée en 3.2.2) ; adresse, téléphone, e-mail dans les lignes d'en-tête (pas de champs séparés, à valider dans la PR) ; `03`.
- Suite : 3.2.2 — reçu dans le navigateur.

### 2026-09-28 — Tâche 3.1.1 : encaissement côté serveur
- Fait : 3.1 découpée (3.1.1 serveur, 3.1.2 écrans ; réduction sur échéance payée → 3.6) ; caisses, sessions (une par caisse et par caissier), paiements immuables avec répartition par défaut ou ajustée, conversion, taux de l'année ou dernier connu, reçu `ITIG-C1-26-000001` ; `/api/cash-registers/`, `/api/cash-sessions/` (+ `current/`), `/api/payments/` ; le solde compte les paiements non annulés ; `make demo` : caisses et paiements depuis la rentrée.
- Tests : 12 (isolation, 403, répartition, conversion dans les deux sens, surplus refusé, double envoi, immuabilité ORM + base, audit, annulation, frais payés) ; écran échéancier sans les échéances payées.
- Décisions : une tranche payée tient la place de celle de même rang et même devise au changement de classe (choix de l'utilisateur) ; `03` et `04` mis à jour.
- Suite : 3.1.2 — écrans de caisse et carte « Caisses ».

### 2026-09-28 — Tâche 2.7 : solde et retards d'un élève
- Fait : solde par devise (dû après réductions, payé, reste, en retard, prochaine échéance) et état de chaque échéance (soldée, en retard, à venir) ; `GET /api/student-charges/balance/` ; onglet Finances : 4 chiffres clés, colonnes Payé / Reste / État ; fiche d'inscription : frais de l'année après réductions, par devise ; liste de classe : colonne « Situation des paiements » (PDF, Excel).
- Tests : réductions (%, montant, retirée, exonération totale), deux devises, retard le lendemain de l'échéance, frais retirés ignorés ; 403 (secrétaire, caissier) et isolation ; `format_amount`.
- Décisions : `03` (calcul à la demande, droits des documents) ; annulation de paiement testée avec la 3.1 ; colonnes « Échu non payé » de la liste des élèves → 4.1.
- Suite : 3.1 — caisses et paiements.

### 2026-09-28 — Tâche 2.5.2 : réductions
- Fait : `Discount` (% sur un frais ou tous, ou montant dans la devise d'un frais ; motif ; retrait noté, jamais effacé) ; `GET/POST /api/discounts/`, `…/revoke/` (droit `finance.grant_discount`, audit dans l'historique de l'élève) ; part des réductions sur chaque frais dû ; onglet Finances : réductions actives, « Ajouter une réduction » (dialogue avec l'effet sur ce que doit l'élève), « Retirer » ; `make demo` : enfants du personnel, fratries, bourses.
- Tests : répartition au centime (%, montant, cumul plafonné, tous les frais en deux devises), suit un échéancier, refus, retrait, audit, isolation et 403 ; `prorate` / `percentOf` identiques serveur et navigateur ; dialogue : effet, envoi en entiers, rien sans motif ; 813 tests serveur, 157 front, lint vert.
- Décisions : `03` (effet calculé, pas stocké ; modèles sans valeur par défaut en attendant I6) ; « Déjà payé » et crédit → 3.1.
- Suite : 2.7 — solde et retards d'un élève.

### 2026-09-28 — Tâche 2.6.2 : échéancier particulier
- Fait : `StudentCharge` « remplacé » ; `reschedule_charges` + `POST /api/student-charges/reschedule/` (droit `finance.grant_discount`, motif obligatoire, engagement signé, audit `finance.charges_rescheduled` visible dans l'historique de l'élève) ; onglet Finances de la fiche : « Ce qui est dû » ; écran « Échéancier particulier » (mensuel ou dates libres).
- Tests : total au centime près, motif, remplacés gardés, nouvel arrangement sur un ancien, barème modifié sans effet, élève parti refusé, isolation et 403 ; écran : proposition mensuelle, envoi en entiers, rien d'envoyé si somme ou motif manque.
- Décisions : `03` (un frais sous échéancier ne suit plus les barèmes ni le changement de classe ; liste des frais dus non paginée).
- Suite : 2.5.2 — réductions.

### 2026-09-27 — Tâche 2.6.1 : frais dus des élèves
- Fait : 2.6 découpée (2.6.1, 2.6.2) ; `StudentCharge` (une ligne par tranche du barème le plus précis), générés à l'inscription et à l'import, recalculés au changement de classe, au retour d'un élève et quand un barème change ; jamais effacés (« retiré ») ; `GET /api/student-charges/?enrollment=` ; fiche élève : changer de classe, enregistrer / annuler un départ, inscrire pour l'année ; `make demo` : ~17 frais dus par élève.
- Tests : barème le plus précis, changement de classe, barème modifié puis supprimé, élève parti intact, import de 800 élèves en moins de 40 requêtes, isolation et 403 ; départ depuis la fiche.
- Décisions : `03` (frais dus retirés et non effacés, pas d'entrée d'audit par frais).
- Suite : 2.6.2 — échéancier particulier, puis 2.5.2.

### 2026-09-27 — Tâche 2.5.1 : frais, barèmes, taux de l'année

- Fait : 2.5 découpée (2.5.1 ; 2.5.2 réductions après la 2.6). App `finance` : types de frais, barèmes (portée, devise, tranches / mensuel / unique, somme = total), taux de l'année immuable avec correction motivée ; écran « Frais et barèmes » ; devise d'un barème non retirable (M5) ; barèmes repris à la création d'une année (C1) ; grille fictive dans `make demo` (I5 en attendant). Corrigé en passant : `make dev` utilisait une autre clé secrète que `.env`, d'où des codes de double authentification refusés après `make demo`.
- Tests : isolation, 403 (dont un rôle limité au taux), somme des tranches, montant à virgule refusé, audit, taux immuable (code et base), M5, reprise d'année ; 793 tests serveur, 151 front, lint vert.
- Décisions : barème le plus précis ; lectures de l'organisation ouvertes aux droits des frais ; devises dans `/api/school/` ; paquet `@mwangaza/money` (`03` § 11).
- Suite : 2.6 (dus des élèves), puis 2.5.2.

### 2026-09-27 — Tâche 2.4 : impressions

- Fait : fiche d'inscription (A4 / A5, code famille au choix, aperçu + PDF) depuis la fiche élève et le bandeau « inscrit » ; écran « Liste de classe » (élèves actifs, colonnes au choix, colonnes vides, ordre, PDF et Excel) ; bouton « Exporter (Excel) » du journal d'audit (période d'un an au plus).
- Tests : isolation (inscription, classe et journal d'une autre école), 403, audit du code imprimé et de l'export, élèves partis absents, PDF réel ; 776 tests serveur, 143 front, lint vert.
- Décisions : WeasyPrint ajouté (stack décidée) avec ses bibliothèques dans Docker et la CI ; frais sur la fiche et « situation des paiements » reportés en 2.7, QR code en 3.2 ; sélection multiple non planifiée.
- Suite : 2.5 — finance, configuration.

### 2026-09-27 — Tâche 2.3 : import Excel des élèves
- **Fait** : import .xlsx / .csv en 4 étapes (fichier, colonnes devinées, vérification ligne par ligne, import Celery groupé) ; classes rapprochées ou associées à la main, fratries par tuteur, matricules, journal par élève ; modèle et rapport Excel ; `make demo-excel`, `make messages` (premières traductions du serveur).
- **Tests** : 772 backend (+6 : isolation, droit, règles, re-import sans doublon, 800 élèves en < 40 requêtes), 140 front ; essai réel : 796 élèves importés.
- **Décisions** : openpyxl ; fratries regroupées dans le fichier seulement ; élève déjà dans l'école = erreur ; fichier pas gardé ; gettext installé, `.po` / `.mo` dans Git.
- **Suite** : 2.4 (impressions) ; revoir l'import avec le vrai fichier de l'ITIG (I7 : feuille par classe ? noms dans une colonne ?).

### 2026-09-27 — Tâche 2.2.2 : fiche élève, fiche famille, recherche `Ctrl K`
- **Fait** : fiche élève (Identité avec photo, Famille, Finances vide, Historique lu dans le journal + parcours), « Modifier l'élève », fiche famille (tuteurs modifiables), liaison à une autre famille (famille vidée supprimée), recherche `Ctrl K` ; doublon → lien vers la fiche ; photo réduite dans le navigateur, servie par l'API, un dossier par école.
- **Tests** : 766 backend, 138 front, 11 e2e ; délais des tests d'écrans relevés (lancement en parallèle). Réparé : recherche des familles par téléphone sur un code contenant un chiffre ; `make test-e2e` remet la démo après les parcours.
- **Décisions** : consentement photo = usage sur la carte et le portail (maquette, H3), pas la prise ; changer de classe, départ, inscrire depuis la fiche → 2.6.
- **Suite** : 2.3 (import Excel).

### 2026-09-27 — Tâche 2.2.1 : liste des élèves et inscription
- **Fait** : tâche 2.2 découpée (accord de l'utilisateur) en 2.2.1 et 2.2.2 (#88). Liste des élèves (recherche sans accents, filtres année / classe / option / statut, tuteur principal) ; écran « Inscrire un nouvel élève » (famille existante ou nouvelle, doublon confirmé, UUID v7 donnés par l'appareil) ; années, options et classes lisibles avec `students.view`.
- **Tests** : 762 backend, 135 front ; tests `enrolled` remplacés par le filtre `status`.
- **Décisions** : extension PostgreSQL `unaccent` pour la recherche ; « Échu non payé », import, export, frais et photo attendent leurs tâches (2.7, 2.3, 2.4, 2.6, 2.2.2).
- **Suite** : 2.2.2 (fiche élève, fiche famille, `Ctrl K`).

### 2026-09-27 — Tâche 2.1 : app `students`
- **Fait** : élèves, familles (code à 8 caractères), tuteurs, inscriptions ; matricule au format de l'école, séquence par année, **gardé toute la scolarité** (décision de l'utilisateur) ; API `/api/students/`, `/api/families/`, `/api/enrollments/` ; effectif des classes (écran Organisation) ; colonne « Élèves » de l'administration ; « Prochain matricule » réel ; démo : 800 élèves ITIG, 150 Volcans. Règle « Économie de tokens » écrite (CLAUDE.md, skills).
- **Tests** : 764 backend, 130 front ; un test de mise en page de l'administration supprimé.
- **Suite** : 2.2 (écrans élèves ; traductions des codes d'erreur `possible_duplicate`, `already_enrolled`… avec eux).

### 2026-09-27 — Tâche 1.7 : organisation scolaire, paramètres, personnel, rôles, journal

- **Fait** : PR #85 (1.6) fusionnée par l'utilisateur. **Serveur** (app `schools`) : `AcademicYear`, `Term`, `Level`, `Track`, `ClassGroup` [T] et `School.matricule_format` (migration 0004, format rempli pour les écoles existantes) ; services `organisation.py` : année depuis un modèle (secondaire RDC, 3 trimestres, vide) avec en option les classes d'une autre année (sans titulaires), année en cours unique, découpage remplacé d'un seul envoi (dates dans l'année, période dans son semestre), niveaux ordonnés, options avec code, classes (unique par année même sans option, section en majuscules, titulaire = personnel actif de l'école), suppression seulement de ce qui ne sert plus, format du matricule vérifié et aperçu « Prochain matricule » ; 16 actions `organisation.*` au journal. API `classes.manage` : `/api/academic-years/` (+ `make-current`, `terms`), `/api/levels/` (+ `reorder`), `/api/tracks/`, `/api/class-groups/` (+ `homeroom-candidates`), `/api/matricule-format/` (+ `preview`). Aussi : filtres de `/api/staff/` (nom ou téléphone, rôle, état), `/api/audit/actors/`, `role_code` des entrées du journal, erreurs de saisie levées par un service au format de l'API. **Gestion** : écrans « Paramètres de l'école » (M5 : identité, logo aussitôt enregistré, couleur avec aperçu lisible et teinte voisine, fuseau, devises), « Organisation scolaire » (année, découpage aux noms traduits et « Modifier les dates », niveaux et options, classes groupées par option et niveau, matricule avec aperçu), « Comptes du personnel » (M3), « Rôles et permissions », « Journal d'audit » (M6 : filtres, pages, détail avant / après traduit) ; composants `Tabs`, `Switch`, `Select`, `Table`, `ConfirmDialog`. `make demo` : ITIG 2026-2027 (découpage daté comme la maquette, 6 niveaux, 4 options, 23 classes, l'enseignant de démonstration titulaire de la 3e Électricité A, `ITIG-{AAAA}-{0000}`), Volcans (dates à saisir, 4 niveaux, 2 options, 4 classes, `LV/{AA}/{0000}`). Écrans comparés aux captures des maquettes à 1440 et 390 px.
- **Tests** : 745 pytest passés (86 nouveaux : 25 formats de matricule, 26 services de l'organisation, 28 API avec droits et isolation entre deux écoles, 3 `make demo`, 2 filtres du personnel, 3 journal, 1 erreurs) ; 130 Vitest (45 nouveaux : 5 écrans, couleur, noms des périodes, date sans heure) ; 11 parcours Playwright (3 nouveaux : directeur des études, directeur, isolation Volcans) ; lint et build OK. 7 erreurs volontaires, toutes détectées (une ne l'était pas : assertions ajoutées). Revue : `docs/claude/revues/tache-1.7.md`.
- **Décisions** (`03` § 11) : modèles d'année et pas de modèle « primaire » (Q12, nouvelle question) ; noms des périodes traduits ; règles du matricule ; erreurs de saisie des services ; titulaire, filtres du personnel et personnes du journal ; aperçu de la couleur dans le navigateur ; écarts aux maquettes ; composants. Informations de l'ITIG utilisées « en attendant » (`07` § 2) : I1 (classes), I2 (matricule), I3 (calendrier).
- **PR** : #86, contrôles GitHub verts au premier passage (backend, frontend, parcours Playwright).
- **Reste / suite** : ajouts au plan : 2.1 (matricule généré, effectifs, classe protégée par ses élèves), 2.2 (années et classes lisibles avec `students.view`), 2.5 (reprendre les barèmes d'une autre année), 3.2 (carte « Reçus » de M5), 6.3 (régime et code EPST). L'utilisateur relit la PR, fusionne, lance `git switch main && git pull && make migrate && make demo` ; puis `/tache 2.1`.

### 2026-09-26 — Tâche 1.6 : front `gestion` (connexion, menu, Mon compte, session support)

- **Fait** : PR #84 (1.5) fusionnée par l'utilisateur. **Socle du front** : `packages/ui` (thème Tailwind 4 aux jetons des maquettes, police embarquée, icônes des maquettes, composants façon shadcn/ui sur `radix-ui` : bouton, champs, code à 6 cases, cases à cocher, cartes, bandeaux, pastilles, étapes, menu tiroir, fenêtres, menus déroulants, pages d'état…), `packages/i18n` (i18next, `fr` et `en` aux mêmes clés, dates dans le fuseau de l'école), `packages/api` (types générés depuis l'OpenAPI par `make api`, client `openapi-fetch`, jeton CSRF relu à chaque envoi, erreurs traduites par leur code). **Gestion** (`/app/`) : PWA installable (manifeste, icônes, service worker après `make build`, nouvelle version proposée jamais imposée) ; connexion en étapes (numéro et mot de passe, code ou code de secours, mot de passe provisoire, activation M1 avec QR code, clé, 8 codes à imprimer ou télécharger, « Terminer » bloqué tant que la case n'est pas cochée) avec le nom, la couleur et le logo de l'école ; coquille (menu latéral basalte, barre du haut avec l'état du réseau et le compte, menu tiroir sous 900 px) et **menu selon les permissions** (tout le menu V1.0, « bientôt disponible » pour les écrans des tâches suivantes, 403 pour une adresse interdite) ; **Mon compte** (M4 : identité en lecture seule, langue enregistrée sur le compte, mot de passe, double authentification : depuis, codes restants avec alerte à 2, nouveaux codes, changer de téléphone, désactiver si aucun rôle ne l'exige ; mes écoles ; se déconnecter) ; **changer d'école** (M2 : liste dans le menu, page « Choisir l'école ») ; **session support** (`/app/support` : motif, bandeau rouge sur tous les écrans avec l'école, l'heure de fin et « Quitter », fin automatique à l'heure) ; pages d'état (M8 : 403, 404, erreur, pas de réseau, école suspendue, adresse sans école, session expirée). **Serveur** : erreurs de saisie avec un code par champ (`fields`), `/api/me/` (écoles du compte avec adresse, couleur, logo, rôles, dernière visite ; `is_platform_admin`), fuseau dans `/api/school/`, schéma OpenAPI aux réponses complètes ; lien « Ouvrir en tant qu'école » de l'administration → `{adresse}/app/support`. Maquette `session-support` dessinée et validée par l'utilisateur. `make api` régénère aussi les types ; `make test-e2e` (nouveau) ; CI : types de l'API vérifiés, job Playwright.
- **Tests** : 659 pytest passés (9 nouveaux : format des erreurs, schéma, `/api/me/`) ; 85 Vitest (77 nouveaux : menu par rôle, étapes de connexion, activation, Mon compte, session support, pages d'état, traductions complètes, formats de date, client de l'API, code à 6 cases, aucun texte en dur) ; 8 parcours Playwright (directeur, caissière et 403, activation du promoteur, mot de passe provisoire, enseignant dans deux écoles, session support, école suspendue, adresse sans école ; isolation : la session d'une école ne vaut pas à l'adresse d'une autre) ; `make lint` et `make build` propres. Erreurs volontaires détectées : heure de l'appareil au lieu de celle de l'école, texte en dur, droit du menu, clé anglaise manquante, « Terminer » jamais bloqué. Les tests ont trouvé un vrai défaut : un code collé avec une espace (« 876 157 ») était coupé. Revue : `docs/claude/revues/tache-1.6.md`.
- **Décisions** (`03` § 11) : dépendances du front (acceptées : stack, client généré, `qrcode-generator`, Testing Library, Playwright), service worker sans `workbox-window` ; format des erreurs de saisie ; menu complet filtré par droits avec « bientôt disponible » ; changer d'école = aller à son adresse ; écarts aux maquettes (case « 7 jours » décochée, pas de `+243`, école sur une ligne sur téléphone, page d'école suspendue sans bouton, erreur 500 sans référence) ; reportés : « Se souvenir de cet appareil » et appareils connectés (3.3), PIN (3.7), e-mail, parcours hors-ligne (3.5).
- **PR** : #85, contrôles GitHub verts (backend, frontend, parcours Playwright ; le premier passage des parcours en CI a échoué : Vite écoutait en IPv6, corrigé en le lançant sur `127.0.0.1`).
- **Reste / suite** : fusion de la PR par l'utilisateur, puis `make install` (nouvelles dépendances du front) et, pour `make test-e2e`, `cd frontend && pnpm exec playwright install chromium` une fois ; tâche 1.7 (organisation scolaire, écrans des paramètres, du personnel, des rôles et du journal).

### 2026-09-26 — Tâche 1.5 : super-admin, session support, paramètres de l'école

- **Fait** : PR #83 fusionnée par l'utilisateur. **Double authentification du super-admin** : toujours exigée ; l'administration Django (`PlatformAdminSite`, `apps/accounts/admin_site.py`) a sa connexion en étapes (numéro et mot de passe, code ou code de secours, nouveau mot de passe provisoire, activation avec la clé et 8 codes de secours), même limitation des tentatives, jamais d'appareil de confiance ; un compte qui n'est pas super-admin reçoit la même réponse qu'un mauvais mot de passe. **Écoles** (administration) : créer avec le premier directeur (nouveau numéro → mot de passe provisoire affiché une fois), liste avec statut, abonnement saisi à la main, dernière activité (dernière entrée du journal hors support) et lien « Ouvrir en tant qu'école », suspendre / réactiver, jamais supprimer. `School` : + nom officiel, logo, couleur, fuseau horaire, devises, offre, fin d'essai, payé jusqu'au. **Paramètres de l'école** (API, `school.configure`) : `/api/school/settings/` (noms, couleur, fuseau, devises ; code réservé au super-admin) et `…/logo/` ; `GET /api/school/` donne couleur, couleur du texte et logo ; `GET /api/school/logo/` public. **Couleur** (Q8) : blanc ou encre, contraste 4,5 : 1, sinon refusée avec une teinte voisine. **Logo** : PNG, JPEG, SVG sans script, 1 Mo, reconnu au contenu, servi avec une politique `sandbox`. **Fuseau** de l'école appliqué à chaque requête. **Session support** (`/api/support/`) : connexion normale à l'adresse de l'école, motif, 1 heure au plus, droits de l'école sauf la caisse, `/api/me/` la donne (bandeau), fermée par le bouton ou la déconnexion. **Journal** : `impersonated_by` sur chaque action de la session ; nouvelles actions `school.*`, `support.*`, `account.changed`, `account.deactivated` / `reactivated`, `account.password_reset` ; changements d'un compte par le support (noms, téléphone, désactivation) dans le journal de chaque école de la personne ; le support donne un mot de passe provisoire, ne le choisit plus. `make demo` : double authentification du super-admin, couleurs, abonnements, logo public de l'ITIG. `03`, `04`, `05`, `07`, `CLAUDE.md`, `A-FAIRE.md`, `maquettes/README.md`, skills `backend` et `ecran` à jour.
- **Tests** : 650 pytest passés (134 nouveaux : 21 couleurs, 14 services des écoles, 37 API des paramètres et du logo, 18 administration des écoles, 19 session support, 14 connexion à l'administration, 11 ailleurs : comptes changés par le support, fuseau, `make demo`, journal, `/api/me/`, droits dans une école suspendue ; 2 anciens tests de connexion à l'administration remplacés) ; types et 8 Vitest OK ; lint OK ; schéma OpenAPI régénéré sans avertissement ; aucune dépendance ajoutée. 28 erreurs volontaires, toutes détectées. Essai réel, conteneurs arrêtés au départ (`make migrate` → `Applying schools.0003_identite_abonnement... OK`, puis `No migrations to apply` ; `make demo`), `make dev-local` : administration (mot de passe puis code de `make totp`, liste des écoles, création de l'école fictive « Institut Bahati » avec logo et directeur → mot de passe provisoire affiché une fois) ; à l'adresse de l'ITIG à travers Vite : super-admin connecté sans droit, session support ouverte (droits sans la caisse), rôle renommé, session fermée → plus de droit ; le directeur lit « Support Mwangaza » avec le motif dans son journal ; couleur `#FF0000` refusée (`#ED0000` proposée), `#F2C94C` acceptée (texte encre), logo envoyé et servi. « À tester toi-même » rejoué ensuite dans l'ordre, conteneurs arrêtés (`make migrate` → `No migrations to apply`, `make demo`, `make test`, administration en français, suspension et réactivation, session support, mot de passe provisoire du support, journal du directeur, paramètres, logo de l'ITIG) ; il a montré une date « il y a » à moitié en anglais et un libellé sans majuscule dans l'administration : corrigés (date et heure de la dernière activité). GitHub Actions sur la PR #84 : les 2 jobs verts au premier passage et après la correction (650 pytest contre PostgreSQL 16, schéma OpenAPI à jour). Revue : `docs/claude/revues/tache-1.5.md`.
- **Décisions** : voir le journal des décisions de `03` (super-admin dans l'administration, écran dédié en 7.2 ; double authentification du super-admin ; session support ; création d'école et suspension ; ce qui va dans le journal de l'école ; Q8 ; paramètres et fuseau ; logo sans dépendance ; textes du serveur en anglais jusqu'en 4.5). Ajouts au plan : 1.6 (écran de la session support, bandeau, nom, couleur et logo à la connexion), 1.7 (écran M5), 2.1 (nombre d'élèves des écoles), 2.5 (devise utilisée non retirable), 4.2 (seuils d'alerte), 4.4 (portail d'une école suspendue), 4.5 (traduction française du serveur), 7.2 (écran dédié du super-admin).
- **Reste / suite** : l'école fictive « Institut Bahati » (`bahati`) créée pendant l'essai reste dans la base de développement (une école ne se supprime pas ; `make reset-db` repart de zéro). L'utilisateur relit la PR #84, fusionne, lance `git switch main && git pull && make migrate && make demo` ; puis `/tache 1.6`.

### 2026-09-26 — Tâche 1.4 : journal d'audit

- **Fait** : PR #82 fusionnée par l'utilisateur. App `audit` : `AuditLog` [T] [I] (action, acteur, objet et son nom au moment de l'action, avant / après des seuls champs changés, adresse IP, navigateur ; `impersonated_by` pour la 1.5) ; **ni modifiable ni effaçable**, refusé par le modèle et par un déclencheur PostgreSQL ; **jamais de secret** (`record()` refuse les clés de mot de passe, de clé, de codes). Utilitaire `apps.audit.services.record()` (dans la transaction de l'action) et `changes()` ; adresse et navigateur lus par `AuditMiddleware` ; liste des actions `apps/audit/actions.py` ; `client_ip()` partagé (`apps/core/http.py`). **Branché** sur les rôles (créé, changé, supprimé), les comptes du personnel (ajouté, rôles, désactivé / réactivé, noms et téléphone, mot de passe provisoire, double authentification réinitialisée), Mon compte (mot de passe, double authentification activée, nouveau téléphone, désactivée, codes de secours), le support (réinitialisation dans l'administration Django) et la connexion (avec la méthode : code, code de secours, appareil de confiance). Un changement de compte va dans le journal de chaque école où la personne est active ; la connexion, dans celui de l'école de l'adresse. **API** `GET /api/audit/` (`audit.view` : directeur, promoteur ; double authentification) : liste paginée, la plus récente d'abord, filtres personne, action, domaine, objet, dates (heure de Goma), recherche ; détail ; support Mwangaza non nommé. Administration Django : journal de toutes les écoles en lecture seule. `03`, `04`, `05`, `07`, `CLAUDE.md`, `A-FAIRE.md`, skill `backend` à jour.
- **Tests** : 516 pytest passés (77 nouveaux : 8 modèle, 17 utilitaire, 24 API, 1 administration, 27 audit des comptes et de la connexion) ; types et 8 Vitest OK ; lint OK ; schéma OpenAPI régénéré. 20 erreurs volontaires, toutes détectées (un test ajouté pour la seule qui passait). Essai réel avec `make dev-local` à travers Vite, conteneurs arrêtés au départ (`make migrate` → `Applying audit.0001_journal... OK`, `make demo`, `make test`) : connexion du directeur avec code → entrée `auth.login` (`second_factor: totp`) ; rôle « Chef d'atelier » renommé et permissions changées → avant / après ; mot de passe provisoire de la secrétaire → entrée sans valeur ; filtres `domain`, `search`, `since` ; DELETE → 405 ; caissière → 403 ; l'enseignant des deux écoles change son mot de passe à l'ITIG → le directeur de Volcans le voit, rien d'autre de l'ITIG ; page HTML de l'API navigable et administration Django. GitHub Actions sur la PR #83 : les 2 jobs verts au premier passage (516 pytest contre PostgreSQL 16, schéma OpenAPI à jour). Revue : `docs/claude/revues/tache-1.4.md`.
- **Décisions** : voir le journal des décisions de `03` (journal immuable jusque dans la base, forme des entrées, où va une entrée, lecture et support non nommé). Écran M6 ajouté à la 1.7 ; export Excel du journal à la 2.4 ; appareil et heure hors ligne à la 3.3 ; « en tant qu'école » et modifications d'un compte par le support dans l'administration à la 1.5.
- **Reste / suite** : chaque tâche qui touche finances, élèves, notes ou paie ajoute ses actions (`apps/audit/actions.py`) et teste son audit. L'utilisateur relit la PR, fusionne, lance `git switch main && git pull && make migrate` ; puis `/tache 1.5`.

### 2026-09-26 — Tâche 1.3 : connexion, double authentification, limitation des tentatives

- **Fait** : PR #81 fusionnée par l'utilisateur (`make reset-db` fait). Dépendances demandées et acceptées : `argon2-cffi`, `cryptography` ; TOTP et limitation des tentatives écrits dans le projet. **Connexion en étapes** (`login.py`) : mot de passe → code (TOTP ou code de secours, « ne plus demander pendant 7 jours ») → nouveau mot de passe si provisoire → activation de la double authentification si un rôle l'exige (clé + 8 codes de secours) ; le compte n'est connecté qu'à la fin ; CSRF vérifié à chaque étape. **Double authentification** exigée pour les droits sur l'argent, les réglages, les comptes et l'audit (par défaut : directeur, comptable, caissier, promoteur), vérifiée aussi à chaque requête (`totp_required`) ; clé chiffrée en base, code à usage unique, codes de secours en empreinte. **Blocage** : 5 essais ratés par numéro en 15 minutes, 30 par adresse IP (API et administration Django). **Argon2** (anciens mots de passe convertis), 10 caractères au moins. **Mon compte** (API) : langue, mot de passe (autres sessions fermées), changer de téléphone, nouveaux codes de secours, désactivation si aucun rôle ne l'exige. **Comptes du personnel** : nouveau mot de passe, réinitialisation de la double authentification, noms et téléphone, seulement pour un compte qui ne sert que dans l'école ; liste avec état de la double authentification et dernière connexion à l'école. Administration : réinitialisation par le support. `make demo` : double authentification des comptes qui l'exigent (clé commune), promoteur de l'ITIG à activer, essais ratés effacés ; `make totp`. « Log in » de DRF remplacé par la vraie connexion. Notes des maquettes M1, M3, M4 et captures ; `03`, `04`, `05`, `07`, `CLAUDE.md`, `A-FAIRE.md`, `.env.example`, skill `backend` à jour.
- **Tests** : 439 pytest passés (134 nouveaux : 33 TOTP dont les vecteurs des RFC 4226 et 6238, 5 chiffrement, 9 blocage, 33 étapes de connexion, 13 Mon compte, 17 comptes du personnel, 4 permission `totp_required`, 3 administration, 5 `/api/me/`, 3 modèles, 2 rôles (B4), 6 `make demo` et `make totp`, 3 réglages ; 2 anciens tests remplacés : `must_change_password` de `/api/me/` et « Log in » de DRF) ; types et 8 Vitest OK ; lint OK ; schéma OpenAPI régénéré. 16 erreurs volontaires toutes détectées. Essai réel avec `make dev-local` à travers Vite (connexion avec code, code réutilisé refusé, activation, blocage 429, nouveau mot de passe provisoire, formulaire de l'API navigable), puis « À tester toi-même » rejoué conteneurs arrêtés, par les formulaires HTML. GitHub Actions sur la PR #82 : les 2 jobs verts au premier passage (439 pytest contre PostgreSQL 16, schéma OpenAPI à jour). Revue : `docs/claude/revues/tache-1.3.md`.
- **Décisions** : voir le journal des décisions de `03` (connexion en étapes, double authentification d'après les droits, dépendances, limitation des tentatives, compte modifiable par l'école seulement s'il ne sert que chez elle, `make totp`). Écrans de la connexion en étapes et « Mon compte » (M4) ajoutés à la 1.6 ; double authentification du super-admin à la 1.5 ; adresse IP réelle derrière le proxy à la 4.6.
- **Reste / suite** : audit de ces actions en 1.4 ; PIN et appareils en 3.3 et 3.7. L'utilisateur relit la PR, fusionne, lance `make install && make migrate && make demo` ; puis `/tache 1.4`.

### 2026-09-26 — Tâche 1.2 : app `accounts` (comptes, rôles, permissions)

- **Fait** : PR #80 fusionnée par l'utilisateur (sa commande « Après la fusion » était partie avant la fusion : relancée par Claude, OK). App `accounts` : `User` remplace l'utilisateur de Django (identifiant = téléphone E.164, forme nationale `0971234567` acceptée, longueur vérifiée pour la RDC et ses voisins ; `last_name`, `middle_name`, `first_name`, `language`, `is_platform_admin` = administration Django seulement, `must_change_password`) ; `created_by` sur tous les modèles ; 16 codes de permissions et 9 rôles système (`roles.py`, tableau de `04` § 8) copiés à la création de chaque école ; `Role` [T] (rôle système : code, nom vide traduit par l'interface, renommable ; rôle de l'école : nom) ; `Membership` [G] (rôles de la même école seulement, refusé jusque dans la base de code) ; `HasSchoolPermission` (appartenance active dans l'école de l'adresse + code). API : `GET /api/me/` (compte, écoles, rôles et permissions dans l'école de l'adresse), `/api/roles/` et `/api/staff/` (`roles.manage`) : rôles de l'école, ajout d'une personne par téléphone (nouveau numéro → mot de passe provisoire affiché une fois ; numéro connu → ajouté sans rien révéler de ses autres écoles), rôles, désactivation ; aucune modification ne laisse l'école sans gestionnaire des rôles. Erreurs de l'API au format `{code, detail}` partout (hors erreurs de saisie). « Log in » de l'API navigable en développement. Admin : comptes ; rôles et appartenances en lecture seule. `make demo` : un compte par rôle à l'ITIG, 3 à Volcans, un enseignant dans les deux, super-admin, rôle « Chef d'atelier » ; mot de passe `mwangaza-demo`. `make reset-db`. Maquette M3 corrigée (plus d'« Autres écoles »). `03`, `04`, `05`, `07`, `CLAUDE.md`, `A-FAIRE.md`, skill `backend` à jour.
- **Tests** : 305 pytest passés (145 nouveaux : 29 numéros, 19 modèles, 9 rôles système dont le tableau de `04` § 8 recopié, 12 permissions, 6 `/api/me/`, 26 `/api/roles/`, 26 `/api/staff/`, 7 admin, 7 erreurs, 4 de plus pour `make demo`) ; types et 8 Vitest OK ; lint OK ; schéma OpenAPI régénéré. 12 erreurs volontaires toutes détectées. Essai réel avec `make dev-local` à travers Vite. GitHub Actions sur la PR #81 : les 2 jobs verts au premier passage (305 pytest contre PostgreSQL 16, schéma OpenAPI à jour). Revue : `docs/claude/revues/tache-1.2.md`.
- **Décisions** : voir le journal des décisions de `03` (modèle de compte, rôles système sans nom en base, permission serveur, comptes du personnel isolés, dernier gestionnaire des rôles, format des erreurs, « Log in » en développement, comptes de démonstration). Écrans « Comptes du personnel » et « Rôles et permissions » ajoutés à la 1.7 (aucune tâche ne les prévoyait).
- **Reste / suite** : audit des changements de rôles et de comptes branché en 1.4 ; mot de passe provisoire imposé à la connexion, « Nouveau mot de passe », double authentification, Argon2 (nouvelle dépendance à demander) en 1.3 ; noms et téléphone d'un compte (M4) en 1.3. L'utilisateur relit la PR #81, fusionne, lance `make reset-db` une fois ; puis `/tache 1.3`.

### 2026-09-26 — Essai de la PR #80 par l'utilisateur : corrections dans la même PR

- **Constaté** : (1) Ctrl+C sur `make dev-local` → `Traceback`, `SystemExit`, « Failed » de pnpm et `Erreur de segmentation (core dump créé)` ; (2) après `make stop`, `make migrate` → `connection refused` (port 5433) : « Après la fusion » ne relançait pas la base ; (3) « Not Found » écrit deux fois par requête ; (4) `make migrate` → « No migrations to apply » et non « Applying … » annoncé (migration déjà appliquée par l'essai de Claude) ; (5) « Après la fusion » lancé avant la fusion (`git pull` → « Déjà à jour »).
- **Causes et corrections** : (1) `trap 'kill 0'` se renvoyait le signal sans fin (plantage de `sh`) et Django recevait des arrêts en rafale ; `sh` faisait aussi ignorer Ctrl+C à Django → recette en bash, chaque serveur reçoit le Ctrl+C et le shell attend leur arrêt ; Vite lancé app par app (`pnpm dev` compte l'arrêt comme un échec). (2) Cible cachée `db-up` : PostgreSQL et Redis démarrés et prêts avant `dev-local`, `migrate`, `makemigrations`, `demo`, `superuser`, `shell`, `test-back` (rien s'ils tournent, rien en CI). (3) Logger `django` sans console propre : ses messages passent par la console racine. (4, 5) PR et skill `tache` : résultat attendu valable si l'étape est déjà faite, commandes rejouées par Claude conteneurs arrêtés, « Après la fusion » commence par la fusion sur GitHub ; `A-FAIRE.md` § 10 le rappelle.
- **Tests** : rejoué dans un pseudo-terminal avec un vrai Ctrl+C : avant → plantage reproduit ; après → seul `^C` s'affiche, les trois serveurs arrêtés. `make stop` puis `make migrate && make demo` → OK sans `make services`. `CI=true make -n test-back` → pas de Docker. `make lint`, `make test` : voir la PR #80.
- **Suite** : l'utilisateur refait « À tester toi-même », fusionne la PR #80, puis `/tache 1.2`.

### 2026-09-26 — Tâche 1.1 : app `core` (isolation des écoles, UUID v7, `Money`)

- **Fait** : app `core` : `uuid7()` et `is_uuid7()` ; `BaseModel` (UUID v7, dates) ; `TenantModel` et `TenantManager` (lecture limitée à l'école courante, erreur sans école ; écriture, suppression, déplacement ou lien vers une autre école refusés, `bulk_create` compris) ; école courante (`use_school`) ; `TenantMiddleware` (sous-domaine → école, 404 si inconnue, 403 si suspendue, pas d'école pour `localhost`, `parents.`, `admin.`…) ; `Money` et `Currency` (entiers, conversion Q4) ; format des erreurs de l'API `{code, detail}`. App `schools` : `School` minimal (code = sous-domaine, nom, statut), admin, `GET /api/school/` (public : code et nom, pour l'écran de connexion). `make demo` : écoles `itig` « ITIG Don Bosco Goma (démo) » et `volcans` « Complexe scolaire Les Volcans (fictif) ». Skills `backend` et `argent`, `03` § 4, `07` § 4, `CLAUDE.md`, `A-FAIRE.md` à jour.
- **Tests** : 160 pytest passés (153 nouveaux : 25 d'isolation des modèles, 10 du middleware, 17 de lecture du sous-domaine, 14 UUID v7, 58 `Money`, `School`, `/api/school/`, `make demo`) ; types et 8 Vitest OK ; lint OK ; build OK. 10 erreurs volontaires toutes détectées. GitHub Actions sur la PR #80 : les 2 jobs verts au premier passage (160 pytest contre PostgreSQL 16). Essai réel avec `make dev-local` : `http://itig.localhost:5173/api/school/` → itig, `volcans…` → volcans, `inconnue…` → 404, école suspendue → 403. Revue : `docs/claude/revues/tache-1.1.md`.
- **Décisions** : voir le journal des décisions de `03` (garde-fous de `TenantModel`, sous-domaines réservés, rôle vérifié par les permissions de l'API, UUID v7 écrit sans dépendance, format des erreurs, `make demo` avancé en 1.1, ruff RUF012 désactivé).
- **Reste / suite** : fichiers de traduction du serveur quand un texte du serveur sera montré tel quel (2.4) ; en 1.2, nouveau modèle d'utilisateur → base de développement à recréer (annoncé dans `A-FAIRE.md` à ce moment-là). Prochaine tâche : 1.2.

### 2026-09-26 — Règles de travail avec GitHub

- **Fait** : l'utilisateur a fusionné #78 (décisions) puis #79 (tâche 0.2) ; `make install` relancé par Claude sur sa machine (les outils de la 0.2 manquaient). À sa demande : section « Travail avec GitHub » dans `CLAUDE.md`, skills `tache` (branche partie de `main`, une seule PR, contrôles verts, modèle de description) et `noter` (dans quelle PR va une note), `A-FAIRE.md` § 10 « Comment relire et fusionner une PR » (remplace la routine).
- **Décisions** : Claude est le développeur ; l'utilisateur, chef de projet et relecteur, valide, teste et fusionne. Une seule PR par tâche (corrections et documents compris), toujours `base: main`, jamais empilée ; PR séparée seulement pour une décision à valider avant de continuer ou une réparation urgente, en disant pourquoi. GitHub Actions vert avant de donner la PR. Chaque PR et chaque message de fin se terminent par « À valider », « À tester toi-même », « Après la fusion ».
- **Suite** : ces changements partent dans la PR de la tâche 1.1 (pas de PR séparée, à la demande de l'utilisateur).

### 2026-09-26 — Tâche 0.2 : qualité (ruff, ESLint, Prettier, Vitest, pre-commit, GitHub Actions)

- **Fait** : ruff configuré dans `backend/pyproject.toml` (100 colonnes, règles E, W, F, I, UP, B, DJ, SIM, RUF ; une ligne raccourcie) ; ESLint 10 (`typescript-eslint`, règles des hooks React, `eslint-config-prettier`), Prettier 3.9 (le code existant était déjà conforme), Vitest 5 avec les premiers tests (proxy de développement des deux applications) ; pre-commit avec des hooks locaux (ruff, ESLint, Prettier, refus d'un `.env` ou d'une clé privée) ; GitHub Actions (`.github/workflows/ci.yml`, 2 jobs : backend avec PostgreSQL 16 et vérification du schéma OpenAPI commité, frontend avec lint, types, Vitest, build). `Makefile` : `lint` (= `lint-back` + `lint-front`, sans rien modifier), `format`, `hooks` (lancé aussi par `install`), `test-front` = types + Vitest ; `make help` réparé (depuis l'`include .env`, `grep` préfixait chaque ligne par le nom du fichier). `CLAUDE.md` et `A-FAIRE.md` : commandes, routine (contrôles GitHub verts), dépannage, étape 8 (`make install` après la fusion).
- **Tests** : `make lint` OK ; `make test` : 7 pytest passés, types OK, 8 tests Vitest passés ; `make build` OK ; `make api` ne change pas le schéma commité. Fautes volontaires détectées : variable inutilisée et hook React conditionnel (ESLint), import inutilisé (ruff), `changeOrigin: true` (2 tests Vitest échouent) ; pre-commit refuse un `.env` et une clé privée ; hooks sur tout le dépôt : aucun fichier modifié. GitHub Actions sur la PR #79 : les 2 jobs verts au premier passage (7 pytest contre PostgreSQL 16, schéma OpenAPI à jour, 8 Vitest, build). Revue : `docs/claude/revues/tache-0.2.md`.
- **Décisions** : ESLint lit le code avec TypeScript 6.0, les applications gardent TypeScript 7 (`typescript-eslint` n'accepte pas encore la 7) ; mêmes commandes `make` en local, en pre-commit et en CI ; Prettier seulement sur le code du front (ni Markdown, ni lockfile, ni `openapi.yaml`), ruff seulement sur `backend/` ; actions GitHub à version fixée.
- **Dépendances ajoutées** (outils de développement seulement) : `ruff`, `pre-commit` ; `eslint`, `@eslint/js`, `typescript-eslint`, `typescript@~6.0`, `eslint-plugin-react-hooks`, `globals`, `eslint-config-prettier`, `prettier`, `vitest`. Raisons : `docs/claude/plans/tache-0.2.md`.
- **Suite** : l'utilisateur fusionne #78 puis #79, lance `make install` ; puis `/tache 1.1`.

### 2026-09-26 — Décisions de l'utilisateur : Q1 à Q11, l'ITIG école d'exemple

- **Fait** : l'utilisateur a fusionné #77 ; `make dev` marche chez lui. Ses réponses sont reportées dans `01`, `02`, `03` (§ 4, 6, 7 et journal des décisions), `04`, `05`, `07`, `CLAUDE.md` (principe, règles 1 et 9, glossaire), `A-FAIRE.md`, les skills `argent`, `backend`, `verifier`, `design`, `document-ecole`. Maquettes corrigées pour Q10 : fiche famille, fiche élève (Identité, Famille, Historique), accueil du portail (ajouter un enfant d'une autre école), vérification d'un reçu (reçu hors ligne signé). Logo noir et blanc de l'ITIG préparé (`ecole-pilote/documents/2026-09-26-logo-itig-noir-et-blanc.png`). Domaine `mwangaza.school` dans les documents ; les maquettes HTML affichent encore `mwangaza.cd`.
- **Principe** : l'ITIG est l'école d'exemple, pas la seule. Rien de propre à une école dans le code (nom, logo, couleur, options, frais, formats de reçu, rôles personnalisés : paramètres de l'école). Données manquantes inventées de façon réaliste ; les vraies données, chaque école les saisit. Isolation : chaque modèle, écran ou point d'API a un test qui prouve qu'une école ne peut ni lire ni modifier les données d'une autre (application, API, exports, rapports, recherche, portail).
- **Décisions** :
  - Q1 : pas de `PaymentSchedule` ; échéancier particulier = `StudentCharge` `source=custom`. Q2 : pas de modèle `Receipt` ; le reçu est une vue imprimable du paiement. Glossaire corrigé.
  - Q3 : 9 rôles système, dont `study_director` (directeur des études) et `discipline_master` (directeur de discipline / surveillant) ; plusieurs personnes par rôle. Q7 : chef d'atelier = rôle personnalisé de l'école.
  - Q4 : taux toujours USD → CDF ; FC → USD par division en `Decimal`, arrondi demi supérieur. Devise au choix pour chaque barème (`FeeRule.currency`). Taux fixe pour l'année, saisi par le comptable, corrigeable avec historique ; les paiements gardent leur taux.
  - Q5 : montant en lettres proposé par Claude (« Cent cinquante dollars américains et vingt-cinq centimes »), ajusté quand le reçu de l'ITIG arrivera.
  - Reçu : format au choix de l'école (thermique 58 / 80 mm, ou A6, A5, petit format sur A4 avec traits de découpe), 1 ou 2 exemplaires ; reste à payer, taux utilisé, caissier, zone signature / cachet ; QR code dès la V1.0, page publique minimale, signé par l'appareil pour rester vérifiable hors ligne.
  - Q6 : caisse d'abord ; P1 2026 sur papier ; bulletins avec Mwangaza à partir de la P2 / 1er semestre ; ordre V1.1 / V1.2 inchangé. Q11 : deux modes d'impression du bulletin ; en attendant, formulaires officiels IGE/P.S et données fictives.
  - Q8 : couleur choisie par l'école (défaut `#0E5C6B`, contraste vérifié) ; `#003C6C` pour l'ITIG de démonstration. Q9 : Mwangaza, `mwangaza.school`.
  - Q10 : chaque école a sa propre copie de l'élève et de sa famille (`Student`, `Family`, `Guardian` liés à l'école).
  - Designs des documents imprimables proposés par Claude, validés par la fusion de la PR. Données de démonstration : `itig` ~800 élèves (familles, fratries, paiements sur plusieurs mois), `volcans` plus petite.
- **Plus bloquant** : documents de l'ITIG (2.3, 2.5, 3.2, 4.8), modèle de l'imprimante thermique, logo noir et blanc, date de la P1. Cases « avant de coder » A.1 et A.4 sans objet (issues #1 et #4 fermées par la PR).
- **Propositions de Claude à valider** (fusion de la PR = accord) : permissions des deux nouveaux rôles et nouvelle permission `classes.manage` (`04` § 8) ; portail multi-écoles : un compte parent relié à une famille par école avec le code famille de chaque école, jamais par téléphone (`03` § 4, `04` § 3) ; QR signé ECDSA P-256 par l'appareil (`03` § 7) ; couleur refusée si le texte n'y est pas lisible (`04` § 1).
- **Reste à l'utilisateur** (non bloquant pour 0.2) : acheter `mwangaza.school` et ouvrir VPS et Cloudflare avant 4.6, stockage objet avant 4.7 ; demander à l'ITIG la date de la P1 2026, qui est le promoteur, le reçu actuel, des bulletins vierges et remplis, le code de l'école (I18) ; transmettre les documents dès qu'il les a.
- **Suite** : `/tache 0.2`.

### 2026-09-26 — `make dev` réparé : tout Mwangaza tourne dans Docker

- **Fait** : l'utilisateur a fusionné #76, s'est reconnecté (`docker run hello-world` OK). Premier `make dev` complet : Django, Celery, PostgreSQL, Redis démarrent, mais le conteneur du front s'arrêtait (`pnpm: not found`, code 127 : le script `pnpm dev` rappelle `pnpm`, absent du `PATH` de `node:22-slim`). De plus, `pnpm install` dans le conteneur réécrivait le `node_modules` de la machine (partagé par le volume) avec un store `/app/node_modules/.pnpm-store` inexistant hors de Docker, et pnpm 12 (vérification des dépendances avant `run`) réinstallait tout à chaque lancement (≈ 40 s avec la connexion de Goma). Correctif (branche `fix/docker-front`) : `corepack enable` dans le conteneur (pnpm dans le `PATH`, `COREPACK_HOME` dans `node_modules` pour ne télécharger pnpm qu'une fois) ; plus d'installation dans le conteneur ; `pnpm_config_verify_deps_before_run=false` ; `make dev` lance `pnpm install --frozen-lockfile` sur la machine avant Docker. `A-FAIRE.md` : 3 bis et 5 bis cochées, 5 ter (fusionner ce correctif), dépannage `ERR_PNPM_UNEXPECTED_STORE`. `CLAUDE.md` : ligne `make dev`.
- **Tests** : `make dev` : prêt en 25 s, `/api/health/` → `ok` (direct et via le proxy de la Gestion), Gestion et Portail → 200, `node_modules` de la machine inchangé ; `make test` : 7 passés, types OK.
- **Décision** : le conteneur du front utilise le `node_modules` installé sur la machine (même Linux x64) au lieu d'installer lui-même.
- **Constat** : pnpm 12 ne lit plus les variables `npm_config_*`, seulement `pnpm_config_*`.
- **Suite** : l'utilisateur fusionne la PR, refait `A-FAIRE.md` § 5 lui-même, tranche Q1–Q11 ; puis `/tache 0.2`.

### 2026-09-26 — Docker installé, `.env` réparé, base de développement en marche

- **Fait** : l'utilisateur a fusionné #75 et installé Docker (29.8, Compose 5.5). Son `.env` (copie de `.env.example`) avait `DJANGO_SECRET_KEY=` vide : l'ancienne consigne demandait de coller à la main la clé affichée par `python3 …`. Une valeur vide exportée par le `Makefile` passait avant la valeur par défaut de `dev.py`, et Django refusait la clé vide (`The SECRET_KEY setting must not be empty`). Correctif (branche `fix/env-valeurs-vides`) : `env()`, `env_bool()`, `env_list()` traitent une variable vide comme absente ; `.env.example` explique la clé ; `A-FAIRE.md` mis à jour (étapes 1 à 4 cochées, 3 bis « se reconnecter », 5 bis « fusionner le correctif », tableau des valeurs du `.env`, ligne de dépannage). Clé écrite dans le `.env` de l'utilisateur par script, jamais affichée. L'utilisateur est dans le groupe `docker` mais sa session ne le voit pas encore (reconnexion nécessaire) ; Claude a lancé les commandes via `sg docker`.
- **Tests** : `make services` (PostgreSQL 16 sur 5433, Redis) ; `make test` : 7 passés (3 + 4 nouveaux dans `tests/test_settings.py`), types du front OK ; `make migrate` ; `make dev-local` : `/api/health/` → `ok` (direct et via le proxy de la Gestion), Gestion et Portail → 200. Production : refuse toujours de démarrer sans `DJANGO_SECRET_KEY`.
- **Décision** : une variable d'environnement vide vaut « absente » (valeur par défaut).
- **Suite** : l'utilisateur se reconnecte, fusionne le correctif, refait `A-FAIRE.md` § 5 lui-même, tranche Q1–Q11 ; puis `/tache 0.2`.

### 2026-09-26 — `A-FAIRE.md`, dossier renommé, PR de rattrapage

- **Fait** : `A-FAIRE.md` à la racine, à la demande de l'utilisateur : ce que lui seul peut faire avant que Claude continue (fusionner #75, rouvrir le dossier, installer Docker, créer `.env`, vérifier, trancher Q1–Q11), comment le faire (commandes pas à pas pour Ubuntu 24.04), quoi demander à l'ITIG et quand (avec un message prêt à envoyer), comptes à créer avant 4.6, routine de chaque tâche, toutes les commandes du projet (actuelles et prévues), dépannage. Relié depuis `CLAUDE.md`, `README.md`, `07`, et les skills `tache` et `noter` (tenu à jour à chaque nouvelle commande ou action). Dossier local renommé de `~/Projets/saas` en `~/Projets/mwangaza` (nom du dépôt GitHub) ; mémoire de Claude Code copiée vers le nouveau chemin ; `backend/.venv` recréé.
- **Constat** : la PR #73 a été fermée sans fusion et la PR #74 fusionnée dans `docs/inventaire-manques` au lieu de `main` : `07-a-fournir.md` et les 61 maquettes n'étaient pas sur `main`. La PR #75 (`docs/a-faire`, partie de `docs/inventaire-manques`) les ramène. `make test-back` échoue sur la machine (2 erreurs) faute de base PostgreSQL accessible : bloquant pour 0.2.
- **Décisions** : `A-FAIRE.md` = liste d'actions de l'utilisateur et référence commentée des commandes ; `07` reste l'inventaire de ce qui manque. Règle : vérifier `base: main` avant de fusionner une PR ; plus de PR empilées.
- **Suite** : l'utilisateur fait les étapes 1 à 6 de `A-FAIRE.md`, puis `/tache 0.2`.

### 2026-09-26 — Maquettes manquantes dessinées ; bulletins officiels de la RDC

- **Fait** : T3 tranchée (Claude dessine). 32 maquettes dessinées dans le système de design, à partir des maquettes existantes et des documents : les 20 manquantes de la V1.0 (M1–M20 = 25 écrans Gestion et 4 Portail), cours et maxima (6.1), bulletin 7e–8e, et le bulletin des humanités techniques qui remplace le « gabarit provisoire ». Total : 61 maquettes, 67 captures refaites (50 bureau, 17 mobile). Menu de la Gestion : 5 entrées ajoutées (Crédits d'élèves, Demandes des parents, Paramètres de l'école, Comptes du personnel, Journal d'audit), identique sur toutes les maquettes ; liens entre écrans complétés. Outils sans dépendance dans `maquettes/outils/` (menu, galerie, captures). Recherche web sur les bulletins : formulaires officiels IGE/P.S/100 (Électricité), /094 (Mécanique générale), /005 (1re–2e secondaire = 7e–8e), barème officiel des maxima de l'option Électronique, heures de l'option Électricité, régime pédagogique du cycle terminal de l'éducation de base — `docs/claude/recherches/2026-09-26-bulletins-rdc.md`.
- **Décisions** : fusionner la PR des maquettes = les valider ; une remarque sur un écran se fait en commentaire de PR. Maquettes dessinées : état « à valider » dans `maquettes/README.md` et `index.html`. Bulletin : branches groupées par maximum, examen = 2 × période, pas d'examen pour les cours pratiques (règles lues sur les formulaires).
- **Nouvelles questions** : Q10 (identité et famille partagées entre écoles), Q11 (numérotation et bulletin pré-imprimé). Nouvelle information à demander : I18 (code de l'école, N° ID et N° permanent).
- **Suite** : l'utilisateur fusionne #72, #73 puis #74 ; ensuite tâche 0.2.

### 2026-09-26 — Inventaire de ce qui manque ; nom du projet

- **Fait** : `docs/07-a-fournir.md` — 20 maquettes V1.0 manquantes (M1–M20) + liste V1.1 / V1.2, 17 informations à obtenir de l'ITIG (I1–I17, avec la tâche et la semaine où elles deviennent nécessaires et ce qu'on utilise en attendant), 6 décisions ou comptes (T1–T6), plan des données de démonstration (`make demo`, écoles `itig` et `volcans`). Vérification des noms : `mwangaza.cd`, `.com`, `.app` pris ; `mwangaza.africa` et `mwangaza.school` semblent libres ; « Shule Yetu » déjà utilisé par une plateforme scolaire.
- **Décisions** : on continue avec des données fictives ; une maquette non fournie est dessinée par Claude dans le système de design et validée avant de coder l'écran.
- **Nouvelle question** : Q9 (nom et domaine).
- **Suite** : réponses de l'utilisateur (voir `07-a-fournir.md` — « à faire maintenant »), puis 0.2.

### 2026-09-25 — Tâche 0.1 : monorepo, Docker Compose de développement, commandes

- **Fait** : `backend/` (Django 5.2.17 LTS, DRF, drf-spectacular, Celery, psycopg ; réglages `dev` / `test` / `prod` ; `/api/health/` ; schéma et doc de l'API en dev) ; `frontend/` (workspace pnpm : `apps/gestion` sur `/app/` port 5173, `apps/portail` port 5174, proxy `/api` vers Django en gardant le sous-domaine ; `packages/api|ui|i18n|money` vides) ; `infra/docker-compose.dev.yml` (PostgreSQL 16 sur 5433, Redis 7, Django, Celery, Vite) ; `Makefile` (16 commandes) ; `.env.example`, `.editorconfig`, `firmware/README.md` ; section « Commandes » de `CLAUDE.md`. Outils installés : `uv` 0.12 (`~/.local/bin`), `pnpm` 12.6 (corepack).
- **Tests** : `make test-back` 3 passés (santé, panne de base → 503, schéma OpenAPI valide) ; types et build des deux applications OK ; parcours vérifié à la main sur `itig.localhost:5173/app/` et `localhost:5174` via le proxy ; `check --deploy` : seul W021 (préchargement HSTS, reporté à 4.6). Revue : `docs/claude/revues/tache-0.1.md`.
- **Décisions** : uv ; `make` pour toutes les commandes ; PostgreSQL de Docker exposé sur 5433 ; sous-domaines `{code}.localhost` en dev ; API fermée par défaut (`IsAuthenticated`) ; schéma et doc de l'API seulement en `DEBUG` ; schéma OpenAPI commité dans `packages/api`.
- **Reste** : lancer `make dev` quand Docker sera installé ; ta base locale n'a pas de rôle PostgreSQL pour ton utilisateur → utiliser `make services` (Docker) ou créer le rôle (`sudo -u postgres createuser --createdb --pwprompt mwangaza`) ; en 1.2 (modèle `User` personnalisé), la base de dev sera recréée.
- **Suite** : 0.2 — qualité (ruff, ESLint, Prettier, Vitest, pre-commit, GitHub Actions).

### 2026-09-25 — GitHub, découpage par versions, dossier ITIG, espace de travail de Claude

- **Fait** : premier commit et dépôt GitHub privé `GUELORD-MWENDERWA/mwangaza` ; jalons V1.0, V1.1, V1.2, V2 et 71 issues (une par tâche, #1 à #4 = « avant de coder », #5 = tâche 0.1) ; plan de travail complété jusqu'à la fin : 4 tâches ajoutées pour couvrir tout le cahier des charges (5.8, 5.9, 6.10, 6.11) et section V2 (7.1 à 7.15, ordre à valider) ; dossier ITIG réorganisé (`depot/`, `documents/`, `prive/`, `fiche-itig.md`) ; recherche web sur l'ITIG (logo, adresse, contacts, 4 options, niveaux 7e–8e EB + 1re–4e, organigramme, date de la P1 2025, dégâts de janvier 2025) ; espace de travail `docs/claude/` (plans, recherches, revues) ; skills `tache`, `etat`, `noter`, `document-ecole` reliées à GitHub et à ces dossiers ; plan de la tâche 0.1 écrit.
- **Décisions** : un jalon GitHub par version, une issue par tâche, PR avec `Closes #n` ; `depot/` et `prive/` hors Git ; noms de personnes seulement dans `prive/`.
- **Nouvelles questions** : Q6 (date des bulletins P1), Q7 (rôles réels de l'ITIG), Q8 (couleur de l'école).
- **Suite** : validation du plan 0.1 (Docker, gestionnaire Python, autorisation de commit), puis tâche 0.1.

### 2026-09-25 — Organisation du dossier avant de coder

- **Fait** : dossier réorganisé selon `03-architecture-technique.md` § 3 — `docs/` et `maquettes/` à la racine ; doublons supprimés (anciennes copies des documents, 4 captures identiques, ancien `CLAUDE.md`) ; `CLAUDE.md` fusionné (lien vers les maquettes, règles de suivi, liste des skills) ; `README.md` du projet ; `.gitignore` ; `docs/ecole-pilote/` ; ce fichier de suivi ; 10 skills Claude Code dans `.claude/skills/` ; dépôt Git initialisé sur `main`.
- **Tests** : sans objet (aucun code).
- **Décisions** : suivi dans `docs/06-suivi.md` ; données personnelles réelles de l'ITIG dans `docs/ecole-pilote/prive/`, hors Git.
- **Suite** : premier commit, puis plan de la tâche 0.1.
