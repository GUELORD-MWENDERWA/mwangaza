# Lot 2 — Site public refait (SITE.R, SITE.1b, SITE.2, SITE.3, SITE.5)

Issue #411 · branche `lot/2-site` · démarré le 2026-10-30

**But** : un site qui vend en peu de mots (promesse, preuves, modules en bref, démonstration), à la nouvelle marque, montrant **l'application elle-même** ; la communication le tient à jour seule depuis la console (actualités, photos, témoignages, écoles de référence, titres de recherche, réseaux).

**Parties** (une conversation chacune)
- [x] ① Étude (`docs/claude/recherches/2026-10-30-site-refait.md`), photos libres, maquettes du site et de la console
- [x] ② Serveur : `Testimonial`, `ReferenceSchool`, `SitePage` (titres de recherche + photo du haut), `Article`, `SitePhoto` ; API console (droit `platform.site.edit`), journal, cache, `make demo` (4 articles) ; tests
- [x] ③ Console : onglets de l'écran Site (témoignages, écoles, titres de recherche, réseaux), écrans Actualités (`/news`) et Photothèque (`/photos`) ; capture 390 / 1440 px à faire avec la partie 5
- [x] ④ Visuels du produit (demande du 2026-10-30, comme ShuleSystem) : `make captures-site` refait — vrais écrans de la démo posés dans des téléphones, une tablette et un ordinateur dessinés (SVG / CSS, sans dépendance), gros plans inclinés, WebP ; maquettes de l'accueil, des écoles et des parents revues avec ces visuels et leurs animations. **Exigence du 2026-10-30** : cadres d'appareils soignés et professionnels (pas « commodes ») d'après les grands sites ; photos de profil générées et icône de l'application dans les écrans des téléphones et tablettes
- [x] ⑤ Pages du site (gabarits, `site.css`, `site.js`, actualités, redirections, `sitemap.xml`), photos Wikimedia retirées, documents

- [x] ⑤bis Retour au site en ligne avec la marque (fonds clairs, angles droits), appareils noirs, reçu visible, journée en défilement avec fenêtre au clic
- [x] ⑥ **Site complet** (demande du 2026-10-30, tout visible comme si fini ; les « à venir » figurent comme déjà là) : console + site pour **formules et abonnements** (page des prix, 3 formules d'exemple modifiables), **partenaires** (ITIG, DTMS, Afronova, logos qui défilent), **chiffres** (4 écoles d'exemple, sans noms sauf ITIG), **témoignages** qui défilent avec fenêtre au clic (personnes africaines, étiquette « exemple » dans la console, publiables sans accord tant qu'ils sont « exemple »)
- [x] ⑦ **Chat du site** : bulle (nom, téléphone, message) → boîte de réception de la console avec alerte + bouton WhatsApp ; sans service externe
- [x] ⑧ **Articles complets** : 6 à 8 articles longs et sérieux (titre, sous-titre, intertitres, listes, photo à côté du titre, photos dans le texte), mise en page d'article de site pro ; **photos libres de droits** cherchées pour chaque emplacement (plus aucune photo de l'ITIG sur les pages, sauf comme partenaire) ; bulletin à taille normale
- [x] ⑨ Retouches du 2026-10-30 (chat non fixe, pas de bandeau « fictif » sur les images, ITIG retirée de l'accueil, partenaires vides, deux écoles de référence) ; déploiement ; coordonnées à saisir dans la console (identité)

**Hors périmètre** : contrats et factures (lot 3) ; sites des écoles (lot 15).

**Regard senior (à valider)**
- Page Modules fusionnée dans Écoles (301) ; « Questions » quitte le menu (reste sur l'accueil).
- Article programmé : la liste en cache contient aussi les articles à venir, la date est comparée à chaque lecture : il paraît à son heure, **sans tâche de fond ni cache de 5 min**.
- Texte d'article : petit Markdown (paragraphes, intertitres, listes, gras, liens) rendu par le serveur, HTML échappé, sans dépendance.
- Photothèque : WebP 1 600 et 600 px, métadonnées retirées ; servie par Django (`/api/platform/photos/…`, gardée un jour : une photo retirée disparaît vite), pas par Caddy (médias montés dans le seul serveur). **Une photo d'élève reconnaissable n'entre qu'avec son accord** (plus simple que « accord manquant » de la maquette).
- Visuels : écrans de l'application (données fictives) plutôt que photos de banque d'images, trop anciennes ; ils vieillissent avec l'application et se refont d'une commande. La photothèque reste pour les articles et, plus tard, les vraies photos d'écoles avec accord.
- Animations sobres (type Stripe / Linear) : apparition douce au défilement, écrans qui se succèdent dans le téléphone, reçu qui sort de l'imprimante, bulletin qui se remplit ; CSS + petit `site.js`, une fois chacune, coupées si `prefers-reduced-motion`, jamais de défilement détourné.
- Témoignage publié seulement avec l'accord déposé ; écoles de référence avec la date de l'accord ; sections cachées tant qu'elles sont vides. Réseaux (SITE.5) : liens de l'identité, modifiables avec `platform.site.edit`.

**Critères d'acceptation** : accueil de 8 sections au plus, aucune grille de cartes identiques ; aucun nom ni photo de l'ITIG ; premier écran ≤ 150 Ko ; actualités paginées et dans le `sitemap.xml` ; chaque page à 390 et 1440 px ; animations sans saut de mise en page.

**Tests** : droit `platform.site.edit` (403 sinon) ; journal ; témoignage refusé sans accord ; article programmé invisible avant sa date ; Markdown sans injection ; image ré-encodée sans métadonnées.

**Documents** : `reference.md` et `A-FAIRE.md` § 11, `07` § 1 et § 4, `03` (journal), `maquettes/README.md`, skill `design`.

**Risques** : poids des visuels ; cache du site à vider à chaque publication ; anciennes adresses `/modules/` à rediriger.
