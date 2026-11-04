# Centre d'aide — mode d'emploi pour écrire

Les articles servent au site (`/aide/`, `/en/help/`), au panneau « Aide » des trois applications et
aux guides PDF (`make guide`). Code : `apps/core/help_center.py`.

## Où

`<langue>/<application>/<clé>.md` : langue `fr` ou `en` ; application `gestion`, `portail` ou
`console` (la console reste dans la console : ni site, ni sitemap). La **clé** (nom du fichier, en
anglais, ex. `take-payment`) est la même dans les deux langues : chaque article existe en `fr` et en
`en` (un test le vérifie).

## En-tête, puis une ligne vide

```
title: Encaisser un paiement
slug: encaisser-un-paiement
summary: Une phrase qui dit à quoi sert l'article.
groups: cash
roles: cashier, accountant
order: 10
updated: 2026-11-04
```

- `title`, `summary`, `groups` : obligatoires. `groups` : `start`, `direction`, `secretariat`,
  `cash`, `teachers`, `parents`, `console` ; la première est la rubrique de l'article (fil
  d'Ariane, sommaire, chapitre du PDF), les suivantes le montrent aussi sur l'accueil.
- `slug` : adresse dans cette langue (sinon la clé) ; `roles` : rôles de départ (« Pour : … ») ;
  `order` : place dans la rubrique (petit d'abord) ; `updated` : date de la dernière vraie
  modification.

## Texte

- `## Intertitre`, paragraphes, `- liste`, `1. étape`, `**gras**`.
- `> **À savoir.** …` : encadré.
- `![Légende](capture:caisse)`, seule sur sa ligne : capture `static/core/aide/<langue>/caisse.webp`
  (`make captures-aide`) ; une au plus par article ; inconnue, elle ne laisse rien.
- `[texte](aide:cancel-payment)` : lien vers un autre article (par sa clé).
- Une ligne `---` : la suite (questions fréquentes) n'est pas dans le guide PDF.
- Jamais de HTML (il est affiché tel quel), jamais le nom de la plateforme ni d'une école : « la
  plateforme », « votre école ».

## Quoi de neuf

`<langue>/whats-new/AAAA-MM-JJ.md`, un par mise en ligne : une phrase de résumé, puis une section
par application en mots simples, sans détail technique :

```
Une phrase de résumé.

[gestion]
- Ce qui change dans la Gestion.

[portail]
- Ce qui change dans l'espace parents.
```
