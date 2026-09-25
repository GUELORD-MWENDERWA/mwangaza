---
name: document-ecole
description: Intégrer un document réel reçu de l'école pilote ITIG Don Bosco Goma (grille des frais, liste des élèves Excel, modèle de reçu, fiche d'inscription, bulletin, grille salariale, logo…) — le ranger, l'analyser, le comparer aux documents, au modèle de données et aux maquettes, lister les écarts et mettre à jour le suivi. À utiliser quand l'utilisateur dit avoir reçu, déposé ou joint un document de l'ITIG ou d'une autre école.
argument-hint: "<chemin du fichier ou type de document>"
---

# Intégrer un document de l'école : $ARGUMENTS

## 1. Ranger

- Contient des **données personnelles** (noms d'élèves, téléphones, salaires nominatifs, reçus remplis) → `docs/ecole-pilote/prive/` (hors Git). Sinon → `docs/ecole-pilote/`.
- Nom : `AAAA-MM-JJ-sujet.ext`. Si le fichier est ailleurs, proposer le déplacement ; ne jamais copier de données personnelles dans le dépôt, les tests ou les données de démonstration.

## 2. Lire

PDF, Excel, Word ou image : utiliser l'outil adapté (skills `pdf`, `xlsx`, `docx`, ou lecture d'image). Pour une liste d'élèves, travailler sur les colonnes, les effectifs et les anomalies, pas sur les personnes.

## 3. Extraire et comparer

| Document | Ce qu'on en tire | Comparer avec |
|---|---|---|
| Grille des frais | types de frais, devise de chaque frais, montants par niveau / option / classe, tranches et dates limites, mensuel, réductions pratiquées, frais qui financent la motivation des enseignants | `04` § 4 (`FeeType`, `FeeRule`, `InstallmentTemplate`, `Discount`), `maquettes/gestion/frais-baremes.html` |
| Liste des élèves | colonnes disponibles, formats (dates, noms, post-noms), classes / sections / options, effectifs, doublons, cellules vides | `04` § 2–3, `maquettes/gestion/eleves-import.html` (correspondance des colonnes, D1) |
| Modèle de reçu | mentions obligatoires, numérotation, montant en lettres, format 80 mm / A4 | `02` F3, `maquettes/gestion/recu.html`, questions Q2 et Q5 de `06-suivi.md` |
| Fiche d'inscription, liste de classe | champs, mise en page | `02` D5, tâche 2.4 |
| Bulletin, palmarès | structure officielle EPST, maxima, calculs | V1.2 (6.3, 6.4) — noter seulement |
| Fonctionnement de la caisse | nombre de caisses, caissiers, clôture actuelle | `02` F8, tâches 3.1 et 3.8 |
| Grille salariale, primes, avances | — | V1.1 (5.3) — noter seulement |
| Calendrier, date des bulletins P1 | découpage de l'année | `02` § 1 (ordre V1.1 / V1.2), tâche 1.7 |
| Logo, en-tête, cachet, nom officiel | — | `School` (`logo`, `official_name`), reçu |
| Matériel (imprimante thermique…) | modèle, largeur papier | `03` § 7 |

Lister les **écarts** : champ absent du modèle, règle non prévue, libellé différent, montant ou découpage différent de la maquette, contradiction avec `02` ou `04`. Pour une règle scolaire RDC ambiguë : poser la question, ne pas supposer.

## 4. Proposer, puis mettre à jour

1. Présenter à l'utilisateur : résumé du document, écarts, modifications proposées (documents, maquettes, données de démonstration, nouvelles questions). **Ne pas modifier `docs/01` à `04` sans accord.**
2. Après accord, appliquer les modifications.
3. `docs/ecole-pilote/README.md` : statut « reçu », nom du fichier.
4. `docs/06-suivi.md` : entrée au « Journal », bloquant levé ou réduit, questions ajoutées ou tranchées ; si c'est un élément de « Avant de coder », cocher dans `docs/05` et recompter.
5. Terminer par `📍` l'état et les tâches maintenant débloquées.
