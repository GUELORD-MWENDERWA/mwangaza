---
name: etat
description: Faire le point sur l'avancement du projet Mwangaza — tâche en cours, cases cochées, prochaine tâche, bloquants, questions ouvertes, état Git. À utiliser quand l'utilisateur demande « où on en est », « le point », « l'état du projet », « qu'est-ce qui reste », ou au début d'une session de travail.
---

# Faire le point

Lecture seule : ne modifie aucun fichier, sauf si l'utilisateur le demande ou si une incohérence doit être corrigée (dans ce cas, le signaler d'abord).

## Étapes

1. Lire `docs/06-suivi.md` en entier.
2. Compter les cases de `docs/05-plan-de-travail.md` par bloc :
   `grep -c '^- \[x\]'` et `grep -c '^- \[ \]'` section par section du plan (§ 3 Lancement, § 4 Modules, § 4 bis Sécurité, § 7 V1.2 à V1.7, V2 ; les tâches faites avant le 2026-10-13 sont dans l'annexe et l'archive).
3. État Git : `git branch --show-current`, `git status --short | head`, `git log --oneline -5`.
   GitHub : progression des jalons `gh api repos/{owner}/{repo}/milestones --jq '.[] | "\(.title) \(.closed_issues)/\(.open_issues+.closed_issues)"'`, PR ouvertes `gh pr list`.
4. Vérifier la cohérence entre les trois sources :
   - le tableau « Avancement » de `06-suivi.md` correspond aux cases de `05` ;
   - la « Tâche en cours » correspond à la branche courante ;
   - une tâche cochée a une entrée dans le « Journal » ;
   - une tâche cochée a son issue GitHub fermée (et inversement).
   Signaler tout écart et proposer la correction.
5. Déterminer la prochaine tâche : première ligne non faite de **la file** (`05` § 2), en sautant celles marquées 👤 (à faire par l'utilisateur, à lui rappeler) et en tenant compte des bloquants de `06-suivi.md`.

## Réponse (courte, en français)

```
📍 Phase : … · Lot : …
✅ Fait : X / Y tâches du lot en cours (détail sur une ligne)
🔨 En cours : tâche … (branche …) — ou « aucune »
➡️ Prochaine : tâche … — une phrase sur son contenu
⛔ Bloquants : … (seulement ceux qui touchent les 2 prochaines tâches)
❓ Questions à trancher bientôt : …
```

Terminer par une proposition concrète : « Lancer `/tache lot N` ? » (ou la reprise du lot en cours)
