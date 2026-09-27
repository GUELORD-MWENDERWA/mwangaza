---
name: tache
description: Réaliser une tâche du plan de travail Mwangaza de bout en bout (ex. « /tache 1.1 », « fais la tâche 2.3 ») — relecture des documents, branche partie de main, tests d'abord, code, vérification des règles, cochage du plan, mise à jour du suivi, une seule PR avec contrôles GitHub verts et sections « À valider », « À tester toi-même », « Après la fusion ». À utiliser dès que l'utilisateur demande de faire, commencer, continuer ou terminer une tâche numérotée de docs/05-plan-de-travail.md.
argument-hint: "<numéro de tâche, ex. 1.1>"
---

# Réaliser la tâche $ARGUMENTS

Suivre les étapes dans l'ordre, en appliquant **« Économie de tokens » de `CLAUDE.md`** (lire peu, tests utiles, documents courts). Annoncer chaque étape en une ligne.

## 1. Préparer

1. `docs/06-suivi.md` : lire seulement « État actuel » et « Bloquants » (`grep -n`). Si une autre tâche est « en cours », demander s'il faut la terminer d'abord.
2. Trouver la tâche dans `docs/05-plan-de-travail.md` ; vérifier que ses dépendances sont cochées.
3. Relire seulement les passages utiles (`grep -n` sur les références A1, F5…, le nom des modèles) de `02-perimetre-v1.md`, `01`, `03`, `04`. Pas de lecture intégrale d'un document déjà connu.
4. Périmètre : ce qui relève de V1.1 / V1.2 / V2 (`02` § 3) → le signaler, ne pas le coder.
5. **Taille** : si la tâche dépasse à peu près un module serveur ou deux écrans, proposer de la découper dans `05` **avant de coder** et attendre la réponse. Tâche simple (écrans de saisie, documents) : rappeler que `/model` permet de passer à Sonnet.
6. Bloquants et lignes de `07-a-fournir.md` qui touchent la tâche : valeur « en attendant » de `07`, le dire. Règle scolaire RDC floue : demander, ne pas supposer.
7. Skills à suivre : modèle / service / endpoint → `backend` ; montants → `argent` ; synchronisation → `hors-ligne` ; écran → `ecran`.

## 2. Démarrer

1. Issue : `gh issue list --state open --search "\"$ARGUMENTS —\" in:title" --json number,title` → `#n`.
2. Branche **partie de `main` à jour** : `git switch main && git pull && git switch -c tache/<numéro>-<mot-clé>`. Branche déjà créée : `git switch` dessus puis `git merge main`. Si la tâche a besoin d'une PR pas encore fusionnée : le dire et attendre.
3. `docs/06-suivi.md` → « État actuel » : tâche en cours, branche, issue, date.
4. Plan dans `docs/claude/plans/tache-<numéro>.md`, **20 lignes maximum** (fichiers, tests prévus, décisions, risques) ; le résumer en 3 lignes. Continuer sauf décision non couverte par les documents.
5. `gh issue comment <n> --body "Démarrée — branche tache/…, plan : docs/claude/plans/tache-<numéro>.md"`.

## 3. Construire

Tout ce qui est fait pendant la tâche va sur cette branche, dans la PR de la tâche (PR séparée seulement : décision importante à valider avant de continuer, ou correction urgente qui bloque ; dire pourquoi).

1. **Tests d'abord**, seulement ceux qui protègent quelque chose : isolation entre deux écoles, permissions (403), argent, audit, vraies règles métier. Pas de test de ce que Django / DRF / React garantissent, de variante presque identique, de libellé ou de mise en page. Playwright seulement pour un chemin critique (connexion, caisse, hors-ligne).
2. Dans un fichier de tests ouvert pour la tâche : supprimer ou fusionner les tests redondants ; jamais un test d'isolation, de permission, d'argent ou d'audit.
3. Code minimal et propre (`CLAUDE.md` : glossaire, `services.py`, i18n, pas de nouvelle dépendance sans demander) ; pas de N+1 (`select_related` / `prefetch_related`, annotations), listes paginées.
4. Pendant le travail, lancer seulement les tests du module touché : `cd backend && uv run pytest apps/<app> -q 2>&1 | tail -5`, `cd frontend/apps/gestion && pnpm exec vitest run <fichier> 2>&1 | tail -15`.
5. Nouveaux modèles → enrichir `make demo` (données fictives, `docs/07-a-fournir.md` § 4).
6. Caisse ou hors-ligne : test Playwright qui coupe le réseau, encaisse deux paiements, rétablit le réseau, vérifie aucun doublon, reçus et soldes justes. Erreurs glissées exprès seulement pour l'argent, l'isolation et le hors-ligne.
7. Conversation longue en cours de tâche : commiter, puis dire à l'utilisateur « Tape /compact ».

## 4. Vérifier

1. **Une seule fois à la fin** : `make lint` puis `make test` (sorties filtrées avec `tail`) ; `make test-e2e` seulement si un parcours Playwright a changé ou si la connexion / la caisse sont touchées (sinon la CI le fait). Montrer le résultat réel ; un échec → corriger.
2. Skill `verifier` : résultat en quelques lignes, mis dans la PR (pas de fichier dans `docs/claude/revues/`).
3. Nouvel écran : une seule capture, à 390 px, comparée à la maquette. Pas de rejeu des étapes « À tester toi-même ».

## 5. Clôturer (obligatoire)

1. `docs/05-plan-de-travail.md` : cocher `- [x]`.
2. `docs/06-suivi.md` : « État actuel » (tâche en cours = aucune, prochaine, date), compteur du bloc dans « Avancement », bloquants réglés retirés, **journal : 3 à 5 lignes** en haut — `### AAAA-MM-JJ — Tâche X.Y : titre` puis fait, tests, décisions, suite.
3. `03` « Journal des décisions » seulement pour une vraie décision technique. `A-FAIRE.md` seulement si l'utilisateur a une action à faire. `CLAUDE.md` et skills seulement si une commande change.
4. Commits en français, style conventionnel, terminés par la ligne Co-Authored-By ; commit, push et PR sans redemander (autorisation générale de l'utilisateur).
5. PR **unique**, `base: main` : `gh pr create --base main --title "<numéro> — <titre>" --body-file <fichier>` (modèle ci-dessous). **Ne jamais fusionner.** Corriger la description : `gh api -X PATCH repos/GUELORD-MWENDERWA/mwangaza/pulls/<n> -F body=@<fichier>` (`gh pr edit` échoue).
6. `gh pr checks <n> --watch`. Rouge : `gh run view <id> --log-failed | tail -40`, corriger, pousser, recommencer. Donner la PR seulement quand tout est vert.
7. Numéro de la PR dans « État actuel » de `06` : dans le commit de clôture si possible (ouvrir la PR avant ce dernier commit), sinon un petit commit, puis contrôles verts.

### Modèle de description de PR

Français simple, court ; l'utilisateur comprend **sans lire le code**.

```markdown
## Ce que ça change
2 à 5 puces : ce qui est nouveau pour l'école ou le projet, et pourquoi.

## Tests
Nombre et résultat (`make test`, `make lint`), contrôles GitHub verts. Vérification des règles : 2 à 4 lignes (✔ / points à noter).

## À valider
Décisions acceptées en fusionnant (où les lire) ; nouvelles dépendances avec leur raison. Sinon : « Rien. »

## À tester toi-même
3 à 5 étapes : commande ou adresse complète → résultat attendu (vrai aussi si l'étape est déjà faite).
Rien de visible : le dire et donner la commande qui montre le résultat.

## Après la fusion
Fusionner sur GitHub, puis `git switch main && git pull` (+ `make install` / `make migrate` si besoin), puis `/clear` et `/tache X.Z`.

Closes #<n>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## 6. Répondre à l'utilisateur

Message court : lien de la PR, contrôles verts, « À valider », « À tester toi-même », « Après la fusion » ; action nouvelle de `A-FAIRE.md` s'il y en a. Puis « Fusionne la PR, puis tape /clear et /tache X.Z » (et le rappel `/model` → Sonnet si X.Z est simple).

Dernière ligne : `📍 Tâche X.Y terminée — prochaine : X.Z`.
