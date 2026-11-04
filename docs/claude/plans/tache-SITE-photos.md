# Tâche SITE-photos — photos récentes et articles longs (hors lot, demande de l'utilisateur 2026-11-03)

**Pourquoi hors lot** : le site public (lot 2) est fini ; l'utilisateur trouve les photos de démonstration trop anciennes (2007 à 2014) et les articles trop courts.

## Fait
- 7 photos de 2021 à 2026 (Wikimedia Commons, CC0 ou CC BY-SA, jamais NC ni ND), en bleu et blanc, classes et écoles de RDC : `eleves-anis`, `classe-bleue`, `classe-tableau`, `ecole-bleue`, `classe-ordinateurs`, `recreation`, `ecole-muja` (WebP 1 200 et 600 px, métadonnées retirées). Crédits : `maquettes/assets/photos/README.md`.
- 5 anciennes photos supprimées du dépôt (WebP et maquettes) ; `make demo` retire aussi leurs lignes de la photothèque (`demo_articles.retire_photos`, sauf si un article les montre).
- 7 articles de démonstration réécrits, 900 à 1 200 mots chacun, 2 photos (haut + une dans le texte, différentes).
- Photos dans les articles à la largeur du texte (plus de débordement de 80 px) ; séparateur « · » dans la ligne date / auteur / lecture.

## Décisions (utilisateur)
- Visages visibles acceptés (classe, groupe) si la licence permet l'usage commercial. Il remplacera des photos lui-même depuis la photothèque de la console.

## À faire après la fusion
- Serveur : au prochain déploiement, passer `create_demo_articles` (ou `make deploy-site` du lot 5 une fois fusionné) pour retirer les anciennes photos de la photothèque en ligne ; **seulement sur « déploie »**.
