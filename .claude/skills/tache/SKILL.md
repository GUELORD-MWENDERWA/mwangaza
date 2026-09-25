---
name: tache
description: Réaliser une tâche du plan de travail Mwangaza de bout en bout (ex. « /tache 1.1 », « fais la tâche 2.3 ») — relecture des documents, branche, tests d'abord, code, vérification des règles, cochage du plan et mise à jour du suivi. À utiliser dès que l'utilisateur demande de faire, commencer, continuer ou terminer une tâche numérotée de docs/05-plan-de-travail.md.
argument-hint: "<numéro de tâche, ex. 1.1>"
---

# Réaliser la tâche $ARGUMENTS

Suivre les étapes dans l'ordre. Annoncer chaque étape à l'utilisateur en une ligne.

## 1. Préparer

1. Lire `docs/06-suivi.md`. Si une autre tâche est « en cours », demander s'il faut la terminer d'abord.
2. Trouver la tâche dans `docs/05-plan-de-travail.md`. Vérifier que les tâches dont elle dépend sont cochées ; sinon le dire.
3. Relire les références citées (A1, F5…) dans `docs/02-perimetre-v1.md`, puis les sections liées de `01-cahier-des-charges.md`, `03-architecture-technique.md` et `04-modele-de-donnees.md`.
4. Vérifier le périmètre : si quelque chose relève de V1.1 / V1.2 / V2 (`02` § 3), le signaler et ne pas le coder.
5. Lister les bloquants de `06-suivi.md` qui touchent cette tâche (ex. document ITIG manquant) et les questions ouvertes à trancher. Si une règle scolaire RDC est floue : demander, ne pas supposer.
6. Choisir les skills à suivre selon le contenu :
   - modèle, service, endpoint Django → `backend`
   - montants, devises, taux, soldes → `argent`
   - synchronisation, Dexie, caisse sans réseau → `hors-ligne`
   - écran → `ecran` (qui s'appuie sur `design`)

## 2. Démarrer

1. Issue GitHub de la tâche : `gh issue list --state open --search "\"$ARGUMENTS —\" in:title" --json number,title` → noter son numéro `#n`.
2. Branche : `git switch main && git pull && git switch -c tache/<numéro>-<mot-clé>` (ex. `tache/1.1-core-tenant`).
3. Dans `docs/06-suivi.md` → « État actuel » : tâche en cours, branche, issue, date du jour.
4. Écrire le plan dans `docs/claude/plans/tache-<numéro>.md` (fichiers créés / modifiés, tests prévus, décisions à prendre, risques) et le résumer à l'utilisateur. Pour la tâche 0.1, **attendre la validation** avant de créer des fichiers (voir `PROMPT-DEMARRAGE.md`). Pour les autres, continuer sauf si le plan contient une décision non couverte par les documents.
5. Commenter l'issue : `gh issue comment <n> --body "Démarrée — branche tache/…, plan : docs/claude/plans/tache-<numéro>.md"`.

## 3. Construire

1. **Tests d'abord** pour les règles métier (pytest + factory_boy ; Vitest ; Playwright pour les parcours).
2. Code minimal pour faire passer les tests, en respectant `CLAUDE.md` (glossaire, logique dans `services.py`, i18n, pas de nouvelle dépendance sans demander).
3. Tâche qui touche la caisse ou le hors-ligne : test Playwright qui coupe le réseau, encaisse deux paiements, rétablit le réseau et vérifie aucun doublon, numéros de reçus corrects, soldes justes côté serveur.

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
4. Nouvelle commande (tâches 0.x surtout) → section « Commandes » de `CLAUDE.md`.
5. Commit(s) en français, style conventionnel (`feat(finance): encaissement partiel`), terminés par la ligne Co-Authored-By. Commiter, pousser et ouvrir la PR seulement si l'utilisateur l'a demandé (une autorisation générale du type « commit et push à chaque tâche » suffit) ; sinon proposer les commandes.
6. PR : `gh pr create --base main --title "<numéro> — <titre>" --body "…résumé, tests, revue…\n\nCloses #<n>"`. La fusion dans `main` ferme l'issue.

Dernière ligne de la réponse : `📍 Tâche X.Y terminée — prochaine : X.Z`.
