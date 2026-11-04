# Lot 6 — Aide, guide et support

**But** : une école se débrouille seule : chaque écran a son article d'aide (fr, en) en un clic, le centre d'aide est sur le site, les guides PDF à donner sont tirés des mêmes textes, et quand ça bloque, l'école écrit à la plateforme, qui suit la demande dans la console. Issue #426 (SUP.1 : #305).

## Parties
- [x] ① Maquettes : centre d'aide (accueil, article, quoi de neuf), panneau « Aide » des trois applications, dialogue « Quoi de neuf », demandes d'aide (Gestion : écrire, mes demandes ; Console : liste, fiche), guide PDF
- [x] ② Moteur : format, lecture, rendu, recherche, site `/aide/` et `/en/help/` (+ sitemap, llms.txt), API `/api/help/`, commande des guides PDF, « Quoi de neuf »
- [x] ③ Articles fr + en des trois applications (un par écran ou tâche), captures (`make captures-aide`), `make guide` → trois PDF par langue
- [ ] ④ Bouton « Aide » et panneau dans les trois applications, table écran → article + test, dialogue « Quoi de neuf », guides de première connexion enseignant, secrétaire, direction
- [ ] ⑤ SUP.1 (modèle, API, Gestion, Console, e-mails, démo) puis fin du lot (docs, vérification, PR)

## Décisions (regard senior)
- **Textes** : Markdown dans `backend/apps/core/help/<lang>/<app>/<slug>.md`, en-tête `clé: valeur` (titre, résumé, rôles, ordre), rendus par `core/markdown.py` (étendu aux captures `![…](capture:<nom>)`), lus une fois par processus : ni table, ni dépendance, ni écriture. Recherche en mémoire, sans accents (site et API : même fonction).
- **Captures** : une par article principal, WebP (`webp.py`, comme `captures-site`), dans `static/core/aide/<lang>/` : peu de poids dans Git.
- **Guides PDF** : WeasyPrint (déjà là) depuis les articles, commande `help_guides` appelée par `make guide` → `docs/guide/guide-<app>-<lang>.pdf` ; `guide.html` retiré, `presentation.html` gardé.
- **Quoi de neuf** : fichiers datés dans le dépôt ; montré une fois par compte et par appareil (localStorage), seulement aux comptes plus anciens que la mise en ligne : aucune écriture serveur.
- **Panneau « Aide »** : lit l'article par l'API publique (contenu déjà public, mis en cache) ; Portail sans demande d'aide (un parent écrit à son école).
- **SUP.1** : `SupportRequest` + `SupportReply` (TenantModel) ; chaque membre écrit et voit **ses** demandes ; console : droit `platform.support.handle` (propriétaire, support), modes réel / démonstration respectés ; e-mail à `support_email` à l'ouverture, notification + e-mail à l'auteur à la réponse ; pas de pièce jointe (écran et version joints d'office) ; 10 demandes par jour et par compte.
- **Console** : ses articles restent dans la console (panneau réservé à l'équipe), ni sur le site ni dans le sitemap : ils ne servent pas au visiteur.
- **Hors ligne** : aide et demandes en ligne (articles déjà ouverts gardés en cache) ; rien dans la file d'opérations.
- Partie ① (2026-11-04) : 12 maquettes (M22) + 3 guides de première connexion ajoutés à `gestion/guide-premiere-connexion` ; « Centre d'aide » au pied du site ; références : `docs/claude/recherches/2026-11-04-centre-d-aide.md`. Partie ② (2026-11-04) : `help_center.py`, `help_views.py`, `help_guides`, mode d'emploi `core/help/README.md`. Écarts : fichier nommé par une **clé anglaise** commune aux deux langues (adresse : `slug:`), liens `aide:<clé>` ; `---` met à part les questions fréquentes ; réglage `SITE_URL` (liens des applications, pied des PDF) ; recherche du site sans limite de débit (même coût qu'une page, `noindex` + `robots.txt`) ; l'API garde la limite `search`. Un seul article réel (`take-payment`) : le reste en ③.

## Hors périmètre
Pièces jointes, discussion en direct, article modifiable depuis la console, aide des modules à venir (chaque lot ajoute ses articles).

## Tests obligatoires
Isolation et propriété des demandes (autre école, collègue) ; console 403 sans droit et mode démo/réel ; limite de demandes ; Markdown : HTML échappé, capture inconnue ignorée ; chaque écran a son article fr + en (Vitest) ; `/aide/` et sitemap.

## Documents à mettre à jour
`reference.md`, `A-FAIRE.md` § 11, `CLAUDE.md` (adresses), `03` (journal), `04` (`SupportRequest`), `07` § 1 et § 4, `maquettes/README.md`, skills `ecran` et `tache` (article par écran), `presentation.html`.

- Partie ③ (2026-11-04) : 24 articles par langue (Gestion 15, Portail 5, Console 3 + `take-payment`) ; captures `make captures-aide` (fr + en, sauf caisse en fr ; pas de capture des notes) ; `make guide` écrit les 6 PDF, `guide.html` retiré.
