# Tâche 8.3.5 — Notes seules sur le formulaire pré-imprimé + lot de la classe

**But** : (1) imprimer le bulletin en « notes seules » : seules les valeurs (élève, cours, maxima, notes, totaux, places) sortent, à la position exacte du bulletin fidèle (8.3.3) ; cadres, titres, cases noires et textes fixes disparaissent, car le formulaire officiel les porte déjà ; (2) imprimer toute la classe en un seul PDF, un élève par feuille.

**Décisions (regard senior)**
- Même gabarit, une classe CSS `only` : aucune seconde mise en page à entretenir, l'alignement du 8.3.3 (écart ≤ 1 mm) sert aussi ici.
- Réglage de calage `dx`/`dy` (−5 à 5 mm), mémorisé par appareil (localStorage) : chaque imprimante décale un peu.
- Lot : bulletin de la classe calculé **une fois**, un gabarit rendu par élève, corps concaténés (`break-before: page`) ; pas de tâche de fond (≈ 50 feuilles, secondes).
- Audit : une ligne par élève imprimé. Pas de réglage d'école.

**Hors périmètre** : fiches de cotes (8.3.6), sens/papier (formulaire A4 fixe).

**Critères** : `mode=grades_only` masque textes fixes, bordures et fonds noirs mais garde les valeurs ; `enrollment` absent → tous les élèves de la classe ; 409 tant que des feuilles ne sont pas validées ; mêmes droits ; audit par élève ; démo : rien à ajouter (notes déjà complètes).

**Tests** : lot = N pages + N lignes d'audit ; autre école → 404 ; mode seul garde nom/notes, retire « SUBJECTS » ; décalage borné (400).

**Documents** : 05, 06, reference.md, 07 § 1, maquettes/README, skill design (impression).

**Risques** : `dx/dy` doit décaler tout le cadre sans changer la pagination ; poids du PDF d'une classe de 60.
