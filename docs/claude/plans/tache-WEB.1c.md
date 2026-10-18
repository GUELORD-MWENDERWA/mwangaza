# Tâche WEB.1c — Visibilité (issue #329)

**But** : qu'on trouve « Mwangaza School », l'espace parents et son école avec peu de mots, et qu'un lien partagé sur WhatsApp ou Facebook montre une vraie image.

**Hors périmètre** : titres modifiables dans la console (SITE) ; adresse et réseaux sociaux de la plateforme (WEB.1d, `sameAs` les lira) ; note et prix pour Google (rien d'inventé : sans prix ni avis, pas d'étoiles dans les résultats).

**Critères d'acceptation**
- Image de partage 1200 × 630 par page et par langue (`/partage/<page>-<langue>.jpg`), dessinée par Pillow d'après l'identité (nom, icône, couleurs) et la maquette `maquettes/site/partage.html` ; en cache, adresse versionnée (`?v=`) ; `twitter:card` large.
- Nouveau champ d'identité **« Nom pour la recherche »** (`site_name`, défaut « Mwangaza School ») : titres, `og:site_name`, données structurées (`alternateName` = nom court), image de partage, titre du Portail à la connexion. Console : un champ de plus (maquette d'abord).
- Données structurées sur **chaque** page : DTMS éditeur (`Organization`, dtms.site), auteur (`Person`, `SOFTWARE_AUTHOR_SAME_AS`), `SoftwareApplication` éducative (Web, Android, iOS), `WebPage`, fil d'Ariane (hors accueil), questions fréquentes (accueil, parents).
- Titres (≤ 60 signes) et descriptions (≤ 155) réécrits pour la recherche ; `sitemap.xml` avec les images de chaque page.
- Portail : `/` et `/login` indexables (titre « Espace parents — Mwangaza School », description, canonique) ; le reste du Portail, la Gestion et la console restent `noindex` ; `robots.txt` du Portail laisse lire `/api/platform/` (le titre en dépend).

**Tests obligatoires** : JSON-LD de chaque page (types, éditeur, fil d'Ariane), image JPEG 1200 × 630 et page inconnue → 404, `site_name` modifiable par le super-admin seulement et journalisé.

**Documents** : `05`, `06`, `03` (journal), `04` (champ), `07` § 1, `maquettes/README.md`, `reference.md`, `A-FAIRE.md` (toi : liens depuis dtms.site, Google Business Profile, Search Console), `infra/README.md` si besoin.

**Risques** : Pillow lit le WOFF2 (vérifié) ; poids de l'image < 300 Ko (WhatsApp) ; Caddy : en-tête `noindex` par chemin sur le Portail ; effet de titre du Portail (le parent écrase l'enfant).
