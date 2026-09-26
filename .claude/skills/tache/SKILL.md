---
name: tache
description: Réaliser une tâche du plan de travail Mwangaza de bout en bout (ex. « /tache 1.1 », « fais la tâche 2.3 ») — relecture des documents, branche partie de main, tests d'abord, code, vérification des règles, cochage du plan, mise à jour du suivi, une seule PR avec contrôles GitHub verts et sections « À valider », « À tester toi-même », « Après la fusion ». À utiliser dès que l'utilisateur demande de faire, commencer, continuer ou terminer une tâche numérotée de docs/05-plan-de-travail.md.
argument-hint: "<numéro de tâche, ex. 1.1>"
---

# Réaliser la tâche $ARGUMENTS

Suivre les étapes dans l'ordre. Annoncer chaque étape à l'utilisateur en une ligne.

## 1. Préparer

1. Lire `docs/06-suivi.md`. Si une autre tâche est « en cours », demander s'il faut la terminer d'abord.
2. Trouver la tâche dans `docs/05-plan-de-travail.md`. Vérifier que les tâches dont elle dépend sont cochées ; sinon le dire.
3. Relire les références citées (A1, F5…) dans `docs/02-perimetre-v1.md`, puis les sections liées de `01-cahier-des-charges.md`, `03-architecture-technique.md` et `04-modele-de-donnees.md`.
4. Vérifier le périmètre : si quelque chose relève de V1.1 / V1.2 / V2 (`02` § 3), le signaler et ne pas le coder.
5. Lister les bloquants de `06-suivi.md` et les lignes de `07-a-fournir.md` qui touchent cette tâche (maquette, information ITIG, décision) et les questions ouvertes à trancher ; pour une information manquante, utiliser la valeur « en attendant » de `07` et le dire. Si une règle scolaire RDC est floue : demander, ne pas supposer.
6. Choisir les skills à suivre selon le contenu :
   - modèle, service, endpoint Django → `backend`
   - montants, devises, taux, soldes → `argent`
   - synchronisation, Dexie, caisse sans réseau → `hors-ligne`
   - écran → `ecran` (qui s'appuie sur `design`)

## 2. Démarrer

1. Issue GitHub de la tâche : `gh issue list --state open --search "\"$ARGUMENTS —\" in:title" --json number,title` → noter son numéro `#n`.
2. Branche, **toujours partie de `main` à jour** (`CLAUDE.md` « Travail avec GitHub », règle 3) : `git switch main && git pull && git switch -c tache/<numéro>-<mot-clé>` (ex. `tache/1.1-core-tenant`). Si la branche existe déjà (créée par `/noter` entre deux tâches), `git switch` dessus puis `git merge main`. Si la tâche a besoin d'une PR pas encore fusionnée : le dire à l'utilisateur et attendre la fusion, ne pas partir de cette branche.
3. Dans `docs/06-suivi.md` → « État actuel » : tâche en cours, branche, issue, date du jour.
4. Écrire le plan dans `docs/claude/plans/tache-<numéro>.md` (fichiers créés / modifiés, tests prévus, décisions à prendre, risques) et le résumer à l'utilisateur. Pour la tâche 0.1, **attendre la validation** avant de créer des fichiers (voir `PROMPT-DEMARRAGE.md`). Pour les autres, continuer sauf si le plan contient une décision non couverte par les documents.
5. Commenter l'issue : `gh issue comment <n> --body "Démarrée — branche tache/…, plan : docs/claude/plans/tache-<numéro>.md"`.

## 3. Construire

Tout ce qui est fait pendant la tâche (corrections, petites réparations, documents, demandes de l'utilisateur arrivées en cours de route) va sur cette branche, dans la PR de la tâche. PR séparée seulement pour une décision importante à faire valider avant de continuer, ou une correction urgente qui bloque le travail : dire pourquoi.

1. **Tests d'abord** pour les règles métier (pytest + factory_boy ; Vitest ; Playwright pour les parcours).
2. Code minimal pour faire passer les tests, en respectant `CLAUDE.md` (glossaire, logique dans `services.py`, i18n, pas de nouvelle dépendance sans demander).
3. Nouveaux modèles → enrichir `make demo` (données fictives, voir `docs/07-a-fournir.md` § 4) pour que l'utilisateur voie la fonction dans l'application.
4. Tâche qui touche la caisse ou le hors-ligne : test Playwright qui coupe le réseau, encaisse deux paiements, rétablit le réseau et vérifie aucun doublon, numéros de reçus corrects, soldes justes côté serveur.

## 4. Vérifier

1. Lancer lint + tests (commandes de la section « Commandes » de `CLAUDE.md`). Montrer le résultat réel ; si un test échoue, le dire et corriger.
2. Appliquer la skill `verifier` sur les changements ; enregistrer le tableau dans `docs/claude/revues/tache-<numéro>.md`.
3. Si la tâche touche un écran : lancer l'application et comparer à la capture de la maquette.

## 5. Clôturer (obligatoire)

1. `docs/05-plan-de-travail.md` : cocher `- [x]` la tâche.
2. `docs/06-suivi.md` :
   - « État actuel » : tâche en cours = aucune, prochaine tâche, date ;
   - « Avancement » : recompter le bloc ;
   - « Bloquants » / « Questions ouvertes » : retirer ce qui est réglé ;
   - « Journal » : nouvelle entrée en haut —
     `### AAAA-MM-JJ — Tâche X.Y : titre` puis **Fait**, **Tests** (nombre, résultat), **Décisions**, **Reste / suite**.
3. Décision technique nouvelle → ligne dans « Journal des décisions » de `docs/03-architecture-technique.md`.
4. Nouvelle commande (tâches 0.x surtout) → section « Commandes » de `CLAUDE.md` **et** `A-FAIRE.md` § 11 (la retirer de « Prévues »). Action nouvelle pour l'utilisateur (installer, configurer, demander à l'ITIG) → `A-FAIRE.md`, et la citer dans la réponse.
5. Commit(s) en français, style conventionnel (`feat(finance): encaissement partiel`), terminés par la ligne Co-Authored-By. Commiter, pousser et ouvrir la PR seulement si l'utilisateur l'a demandé (une autorisation générale du type « commit et push à chaque tâche » suffit) ; sinon proposer les commandes.
6. PR, **une seule pour la tâche**, `base: main` : `gh pr create --base main --title "<numéro> — <titre>" --body-file <fichier>` avec le modèle ci-dessous. La fusion dans `main` ferme l'issue. **Ne jamais fusionner.** Pour corriger la description ensuite : `gh api -X PATCH repos/GUELORD-MWENDERWA/mwangaza/pulls/<n> -F body=@<fichier>` (`gh pr edit` échoue : « Projects (classic) is being deprecated »).
7. **Contrôles GitHub** : `gh pr checks <n> --watch`. Rouge : lire le journal (`gh run view <id> --log-failed`), corriger, pousser sur la même branche, recommencer. On ne donne la PR à l'utilisateur que quand tout est vert.
8. Noter le numéro de la PR et le résultat des contrôles dans `docs/06-suivi.md` (« État actuel », journal) et `A-FAIRE.md` (ligne « relire et fusionner la PR #n ») ; commit et push sur la même branche, puis vérifier que les contrôles repassent au vert.

### Modèle de description de PR

Français simple ; l'utilisateur doit comprendre ce qui a changé **sans lire le code**.

Avant de donner « À tester toi-même » et « Après la fusion » : les **rejouer soi-même dans l'ordre**, conteneurs arrêtés (`make stop`), comme l'utilisateur les tapera. Le résultat attendu doit rester vrai si l'étape est déjà faite (ex. `make migrate` → « Applying … OK », ou « No migrations to apply » si déjà appliquée).

```markdown
## Ce que ça change
2 à 6 puces : ce qui est nouveau pour l'école ou pour le projet, et pourquoi. Pas de noms de fichiers sauf s'ils aident.

## Tests
Nombre de tests et résultat (`make test`, `make lint`), contrôles GitHub verts ; revue : `docs/claude/revues/tache-<numéro>.md`.

## À valider
Les décisions ou propositions que tu acceptes en fusionnant, avec où les lire (fichier et section) ; nouvelles dépendances avec leur raison. Sinon : « Rien. »

## À tester toi-même
Commandes exactes, pages à ouvrir (adresse complète), résultat attendu pour chacune :
1. `gh pr checkout <n>` puis `…` → attendu : …
2. Ouvrir http://… → attendu : …
Si rien n'est visible dans l'application : le dire, et donner la commande qui montre le résultat (ex. `make test` → « 42 passed »).

## Après la fusion
D'abord fusionner la PR sur GitHub (bouton *Merge pull request*), puis : `git switch main && git pull` (+ `make install` si des dépendances ont changé, `make migrate` s'il y a des migrations), puis la prochaine tâche : `/tache X.Z`.

Closes #<n>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## 6. Répondre à l'utilisateur

Message de fin court, **les trois mêmes sections** que la PR (« À valider », « À tester toi-même », « Après la fusion »), sans détails techniques inutiles, avec le lien de la PR et l'état des contrôles (verts). Signaler toute action nouvelle notée dans `A-FAIRE.md`.

Dernière ligne de la réponse : `📍 Tâche X.Y terminée — prochaine : X.Z`.
