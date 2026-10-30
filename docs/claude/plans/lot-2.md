# Lot 2 — Site public refait (SITE.R, SITE.1b, SITE.2, SITE.3, SITE.5)

Issue #411 · branche `lot/2-site` · démarré le 2026-10-30

**But** : un site qui vend en peu de mots (promesse, preuves, modules en bref, démonstration), à la nouvelle marque, avec de vraies photos d'élèves congolais ; la communication le tient à jour seule depuis la console (actualités, photos, témoignages, écoles de référence, titres de recherche, réseaux).

**Parties** (une conversation chacune)
- [x] ① Étude (`docs/claude/recherches/2026-10-30-site-refait.md`), photos libres (`maquettes/assets/photos/`), maquettes du site (accueil, écoles, parents, actualités, article) et de la console (onglets du site, actualités, photothèque)
- [ ] ② Serveur : `Testimonial`, `ReferenceSchool`, `PageMeta`, `Article`, `SitePhoto` + emplacements ; API console, droit `platform.site.edit`, journal, cache ; tests
- [ ] ③ Console : onglets de l'écran Site, écrans Actualités et Photothèque
- [ ] ④ Pages du site (gabarits, `site.css`, actualités, redirections, `sitemap.xml`), captures du produit (`make captures-site`), documents

**Hors périmètre** : page des prix (lot 3, SITE.4) ; sites des écoles (lot 15).

**Regard senior (à valider)**
- Page Modules fusionnée dans Écoles (301) ; « Questions » quitte le menu (reste sur l'accueil).
- Article programmé : la page filtre sur la date de publication, cache de 5 min, **aucune tâche de fond**.
- Texte d'article : petit Markdown (paragraphes, intertitres, listes, gras, liens) rendu par le serveur, HTML échappé, sans dépendance.
- Photothèque : Pillow (déjà là, S.4) ré-encode en WebP 1 600 et 600 px, métadonnées retirées ; emplacements fixes des pages (accueil, écoles, parents) ; photo par défaut = celles du dépôt.
- Témoignage publié seulement avec l'accord déposé (fichier privé) ; sections Témoignages et Écoles de référence cachées tant qu'elles sont vides.
- Réseaux (SITE.5) : les liens existent déjà dans l'identité (WEB.1d) ; ils passent dans l'écran Site (droit de la communication), partage des articles par simples liens.
- Photos : Wikimedia Commons (CC0, domaine public, CC BY / BY-SA), élèves en groupe ou de loin (livre de marque) ; bulletin animé au nom d'une école fictive.

**Critères d'acceptation** : accueil de 8 sections au plus au lieu de 11 (7 sans témoignage), aucune grille de cartes identiques ; aucune photo ni nom de l'ITIG sur le site ; crédits dans les mentions ; premier écran ≤ 150 Ko ; actualités paginées et dans le `sitemap.xml` ; chaque page à 390 et 1440 px.

**Tests** : isolation sans objet (plateforme) ; droit `platform.site.edit` (403 sinon) ; journal de chaque changement ; témoignage refusé sans accord ; article programmé invisible avant sa date ; Markdown sans injection HTML ; image ré-encodée sans métadonnées.

**Documents** : `reference.md` et `A-FAIRE.md` § 11 (adresses), `07` § 1 et § 4, `03` (journal), `maquettes/README.md`, skill `design`, `make demo` (articles fictifs).

**Risques** : poids du premier écran avec photos ; cache du site à vider à chaque publication ; anciennes adresses `/modules/` à rediriger.
