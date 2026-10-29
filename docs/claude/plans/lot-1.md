# Lot 1 — Marque Mwangaza (BRAND.1, BRAND.2)

Issue #409 · branche `lot/1-marque` · démarré le 2026-10-29

**But** : une vraie marque pour la plateforme (logo, couleurs, police, règles), choisie par l'équipe, décrite dans un livre de marque PDF (modèle : livre Ujuzi) et appliquée aux trois applications, sans air de gabarit.

**Parties** (une conversation chacune)
- [x] ① Étude de 8 marques (`docs/claude/recherches/2026-10-29-marque.md`), trois pistes (commit f39f60a9) : **piste A retenue**, logotype en Poppins comme Ujuzi, palette Ardoise, Craie, Bleu uniforme, Brume du lac, Soleil levant → `maquettes/marque/marque.html`
- [ ] ② Livre de marque PDF (`docs/marque/livre-de-marque.pdf`, HTML + WeasyPrint) et fichiers du logo (SVG, PNG) dans `maquettes/assets/logo/`
- [ ] ③ Marque appliquée : jetons, thème `packages/ui`, barres et connexions des trois applications, icônes et favicon, valeurs par défaut de `PlatformSettings` (migration), skill `design`, guides PDF (`make guide`), captures 390 / 1440 px

**Hors périmètre** : site public refait et photos (lot 2) ; facture réelle de la plateforme (lot 3 : seulement un exemple dans le livre) ; documents d'une école (reçu, bulletin : identité de l'école).

**Regard senior (à valider)**
- Le texte des applications reste en Atkinson Hyperlegible Next (lisibilité, déjà hors ligne, écrans vérifiés à 390 px) ; la piste choisit la police du logotype et des grands titres. Changer la police de toute l'interface obligerait à revérifier chaque écran pour un gain faible.
- Applications du livre (t-shirt, kakémono, carte) dessinées à plat en HTML, sans photomontage.
- **Un seul logo** (A) : l'utilisateur proposait de garder aussi C comme second logo « si c'est une bonne idée » ; écarté — une marque se reconnaît à un seul signe décliné en versions, deux logos doubleraient icônes, polices et thèmes, et la console permet déjà de changer de logo sans code (règle 9).
- Logotype converti en tracés avec fontTools (déjà installé avec WeasyPrint) : aucune nouvelle dépendance.

**Critères d'acceptation** : piste choisie notée (`07` T7, journal) ; PDF complet (sections du modèle) ; logo lisible de 16 à 512 px ; plus de jaune en grande surface ; aucune trace de l'ancien logo (maquettes, guides, page Django) ; couleurs de la plateforme toujours modifiables (règle 9) ; chaque écran principal à 390 et 1440 px.

**Tests** : contraste des nouvelles couleurs par défaut accepté par le serveur ; migration des valeurs par défaut qui n'écrase pas une identité déjà saisie dans la console.

**Documents** : `maquettes/README.md` (jetons, logo), skill `design`, `03` (journal des décisions), `07` § 1 et T7, `A-FAIRE.md`, `docs/claude/reference.md` (si commande nouvelle).

**Risques** : migration qui écraserait des couleurs déjà changées ; manifeste PWA et icônes gardés en cache (changer le nom des fichiers) ; guides PDF à régénérer.
