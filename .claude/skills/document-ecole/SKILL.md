---
name: document-ecole
description: Intégrer un document réel reçu de l'école pilote ITIG Don Bosco Goma (grille des frais, liste des élèves Excel, modèle de reçu, fiche d'inscription, bulletin, grille salariale, logo…) — le ranger, l'analyser, le comparer aux documents, au modèle de données et aux maquettes, lister les écarts et mettre à jour le suivi. À utiliser quand l'utilisateur dit avoir reçu, déposé ou joint un document de l'ITIG ou d'une autre école.
argument-hint: "<chemin du fichier ou type de document>"
---

# Intégrer un document de l'école : $ARGUMENTS

## 1. Ranger

- Sans argument : traiter chaque fichier de `docs/ecole-pilote/depot/` (sauf `LISEZMOI.md`).
- Contient des **données personnelles** (noms d'élèves ou du personnel, téléphones, salaires nominatifs, reçus remplis) → `docs/ecole-pilote/prive/` (hors Git). Sinon → `docs/ecole-pilote/documents/`.
- Nom : `AAAA-MM-JJ-sujet.ext`. Déplacer (pas copier) depuis `depot/` ; ne jamais copier de données personnelles dans le dépôt, les tests ou les données de démonstration.
- Vérifier avec `git status --ignored` que le fichier privé est bien ignoré.
- Faits publics nouveaux (adresse, options, calendrier…) → mettre à jour `docs/ecole-pilote/fiche-itig.md`.

## 2. Lire

PDF, Excel, Word ou image : utiliser l'outil adapté (skills `pdf`, `xlsx`, `docx`, ou lecture d'image). Pour une liste d'élèves, travailler sur les colonnes, les effectifs et les anomalies, pas sur les personnes.

## 3. Extraire et comparer

| Document | Ce qu'on en tire | Comparer avec |
|---|---|---|
| Grille des frais | types de frais, devise de chaque frais, montants par niveau / option / classe, tranches et dates limites, mensuel, réductions pratiquées, frais qui financent la motivation des enseignants | `04` § 4 (`FeeType`, `FeeRule`, `InstallmentTemplate`, `Discount`), `maquettes/gestion/frais-baremes.html` |
| Liste des élèves | colonnes disponibles, formats (dates, noms, post-noms), classes / sections / options, effectifs, doublons, cellules vides | `04` § 2–3, `maquettes/gestion/eleves-import.html` (correspondance des colonnes, D1) |
| Modèle de reçu | mentions obligatoires, numérotation, montant en lettres, format (58 / 80 mm, A4), exemplaires | `02` F3, `04` § 1 (réglages du reçu), `maquettes/gestion/recu.html` ; décision Q5 : la formulation de l'ITIG remplace celle proposée par Claude |
| Fiche d'inscription, liste de classe | champs, mise en page | `02` D5, tâche 2.4 |
| Bulletin, palmarès | structure officielle EPST, maxima, calculs | V1.4 (8.3, 8.4) — noter seulement |
| Fonctionnement de la caisse | nombre de caisses, caissiers, clôture actuelle | `02` F8, tâches 3.1 et 3.8 |
| Grille salariale, primes, avances | — | V1.3 (7.3) — noter seulement |
| Calendrier, date des bulletins P1 | découpage de l'année | `02` § 1 (ordre des versions), tâche 1.7 |
| Logo, en-tête, cachet, nom officiel | — | `School` (`logo`, `official_name`), reçu |
| Matériel (imprimante thermique…) | modèle, largeur papier | `03` § 7 |

Lister les **écarts** : champ absent du modèle, règle non prévue, libellé différent, montant ou découpage différent de la maquette, contradiction avec `02` ou `04`. Pour une règle scolaire RDC ambiguë : poser la question, ne pas supposer.

## 4. Proposer, puis mettre à jour

1. Présenter à l'utilisateur : résumé du document, écarts, modifications proposées (documents, maquettes, données de démonstration, nouvelles questions). **Ne pas modifier `docs/01` à `04` sans accord.**
2. Après accord, appliquer les modifications.
3. `docs/ecole-pilote/README.md` : statut « reçu », nom du fichier ; cocher la ligne correspondante (I1–I17) dans `docs/07-a-fournir.md`.
4. `docs/06-suivi.md` : entrée au « Journal », bloquant levé ou réduit, questions ajoutées ou tranchées ; si c'est un élément de « Avant de coder », cocher dans `docs/05` et recompter.
5. Terminer par `📍` l'état et les tâches maintenant débloquées.
