---
name: noter
description: Noter une étape, un événement, une décision, un blocage ou une question tranchée dans le suivi du projet Mwangaza (docs/06-suivi.md, et le journal des décisions si c'est technique). À utiliser quand l'utilisateur dit « note que… », « ajoute au journal », « on a décidé… », « l'ITIG a envoyé… », « c'est bloqué par… », ou après toute étape qui n'est pas une tâche du plan.
argument-hint: "<ce qu'il faut noter>"
---

# Noter dans le suivi : $ARGUMENTS

## 1. Classer l'information

| Type | Où l'écrire |
|---|---|
| Étape ou événement (réunion ITIG, test sur place, formation) | `docs/06-suivi.md` → « Journal » |
| Décision technique ou produit | « Journal » **et** `docs/03-architecture-technique.md` § 11 « Journal des décisions » (date, décision, raison) |
| Blocage nouveau | « Bloquants et en attente » (sujet, attendu de, tâches bloquées) + « Journal » |
| Blocage levé | retirer de « Bloquants » + « Journal » |
| Question tranchée | retirer de « Questions ouvertes » + « Journal » avec la réponse ; appliquer la réponse dans le document concerné (`02`, `04`…) si elle le modifie |
| Nouvelle question | « Questions ouvertes » (Q suivant, question, tâche, proposition) |
| Case « Avant de coder » faite (domaine acheté, comptes créés…) | cocher dans `docs/05-plan-de-travail.md`, recompter « Avancement », fermer l'issue GitHub `A.x` (`gh issue close <n> --comment "…"`) + « Journal » |
| Recherche faite (web, bibliothèque, règle EPST) | note avec sources dans `docs/claude/recherches/AAAA-MM-JJ-sujet.md` + une ligne au « Journal » |
| Information fournie, maquette fournie, décision prise (liste de `docs/07-a-fournir.md`) | cocher la ligne dans `07` + « Journal » ; si c'est Q1–Q9, traiter comme une question tranchée |
| Document reçu de l'école | utiliser la skill `document-ecole` |
| Action de l'utilisateur faite ou nouvelle (Docker installé, PR fusionnée, compte créé, visite à l'ITIG prévue) | cocher ou ajouter la ligne dans `A-FAIRE.md` + « Journal » |

Si l'information contredit un document de `docs/`, le signaler et demander avant de modifier le document.

## 2. Écrire

- Date du jour au format `AAAA-MM-JJ`, entrée la plus récente **en haut** du « Journal ».
- Format : `### AAAA-MM-JJ — titre court`, puis des puces **Fait** / **Décisions** / **Suite** (seulement celles utiles).
- Mettre à jour « Dernière mise à jour » dans « État actuel ».
- Français clair, phrases courtes, pas de jargon inutile.

## 3. Dans quelle PR (règles « Travail avec GitHub » de `CLAUDE.md`)

Une note ne crée jamais sa propre PR et ne se commite jamais sur `main`.

| Situation | Où va la note |
|---|---|
| Une tâche est en cours (branche `tache/…`) | commit sur cette branche : elle part dans la PR de la tâche |
| La PR de la dernière tâche est ouverte, pas encore fusionnée | commit sur sa branche, push ; attendre que les contrôles GitHub repassent au vert ; le signaler à l'utilisateur (la PR contient une note de plus) |
| Aucune PR ouverte, aucune tâche en cours | créer tout de suite la branche du prochain lot depuis `main` à jour (`git switch main && git pull && git switch -c lot/<N>-<mot-clé>`), commiter la note dessus, sans ouvrir de PR : `/tache` reprendra cette branche |
| Décision importante que l'utilisateur doit valider **avant** que Claude continue | exception : PR séparée `docs/<sujet>`, `base: main`, avec les sections « À valider », « À tester toi-même » (souvent « rien de visible »), « Après la fusion » ; dire pourquoi elle est séparée |

Commit en français : `docs: <ce qui est noté>`, terminé par la ligne Co-Authored-By.

## 4. Répondre

Une ou deux lignes : ce qui a été noté, où, et dans quelle PR ou branche ; s'il y a une PR à relire, les sections « À valider » et « Après la fusion ». Puis `📍` l'état actuel en une ligne.
