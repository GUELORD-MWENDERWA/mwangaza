# Tâche WEB.1a — Étude des grands sites, puis maquettes du site public

**But** : voir comment les meilleurs sites présentent un logiciel (structure, preuves, animations, poids sur téléphone), faire mieux, et dessiner chaque page du site public avant de la coder (WEB.1b).

**Hors périmètre** : code Django (WEB.1b) ; images de partage, données structurées, titres pour la recherche (WEB.1c) ; page des prix (WEB.1, V1.3) ; sites des écoles (WEB.2).

**Critères d'acceptation**
- Note `docs/claude/recherches/2026-10-17-site-public.md` : ≥ 8 sites (SaaS, logiciels scolaires, services africains), structure, ce qui convainc, animations, poids mesuré au téléphone, sources ; ce qu'on reprend et ce qu'on fait mieux.
- 7 maquettes dans `maquettes/site/` : accueil, écoles (directeur, comptable, caissier, enseignant), parents, modules, démonstration et contact, « Trouver mon école », mentions et confidentialité ; en-tête et pied communs ; captures à 390, 820 et 1440 px, sans débordement.
- Chaque animation est dessinée et son rôle écrit dans un `.note` ; coupées par `prefers-reduced-motion`.
- Rien qui fait « site d'IA » : ni dégradé violet, ni tache floue, ni verre dépoli, ni 3D, ni illustration générée ; images = captures du produit et emplacements de photos.

**Tests obligatoires** : pas de code de l'application, donc pas de test ; `captures.mjs` refuse une page qui déborde.

**Documents à mettre à jour** : `maquettes/README.md` (inventaire « Site public », 820 px dans les outils), `maquettes/index.html`, `docs/07-a-fournir.md` § 1, `05`, `06`, `03` (journal des décisions).

**Regard senior** : une seule page « Écoles » avec une section par rôle (quatre pages presque vides se classent mal) ; « Trouver mon école » renvoie vers le sous-domaine sans chercher en base (pas d'énumération des écoles, aucun coût) ; mentions et confidentialité : un gabarit, deux adresses.

**Risques** : poids des captures dans Git (pages longues) ; texte de confidentialité = sujet juridique, à faire relire (proposé, pas définitif).
