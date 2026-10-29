---
name: tache
description: Réaliser un lot du plan de travail Mwangaza (ex. « /tache lot 3 », « fais le lot suivant », « continue le lot ») — ou, par exception, une tâche isolée (« /tache 8.4.6 ») — de bout en bout : fiche du lot, branche partie de main, maquettes d'abord, une partie par conversation avec push de sauvegarde, tests utiles, vérification des règles, cochage du plan, suivi, une seule PR à la fin avec contrôles GitHub verts et sections « À valider », « À tester toi-même », « Après la fusion ». À utiliser dès que l'utilisateur demande de faire, commencer, continuer ou terminer un lot ou une tâche de docs/05-plan-de-travail.md.
argument-hint: "lot <N> (ex. lot 1) — ou un numéro de tâche"
---

# Réaliser $ARGUMENTS

Depuis le 2026-10-29 on travaille **par lots** (`05` § 2) : un lot = 2 à 7 tâches d'un thème = une branche = **une PR**, fait en **parties** (une conversation chacune). Appliquer **« Économie de tokens » de `CLAUDE.md`** (lire peu, tests utiles, documents courts). Annoncer chaque étape en une ligne.

## 1. Où en est le lot

1. `docs/06-suivi.md` : « État actuel » seulement (`sed -n` jusqu'à « Avancement »).
2. Le lot : sa ligne dans `05` § 2 et la fiche de chacune de ses tâches (`grep -n` sur le numéro dans `05`). **Sans argument** (« /tache », « le suivant ») : le premier lot non fini de la file.
3. Fiche du lot `docs/claude/plans/lot-<N>.md` :
   - elle existe → lire ses cases ; reprendre **à la première partie non cochée** (`git fsck`, `git switch lot/<N>-…`, `git pull`, `git merge main` si `main` a bougé) ; aller au § 3 ;
   - elle n'existe pas → § 2.

## 2. Démarrer le lot (première conversation seulement)

1. Relire seulement les passages utiles (`grep -n`) de `01` à `04` et de `07-a-fournir.md` (valeurs « en attendant »). Ce qui relève d'une version suivante → le signaler, ne pas le coder. Règle scolaire RDC floue : demander, ne pas supposer.
2. **Regard senior** (`CLAUDE.md`, « Façon de travailler ») : chaque tâche du lot est-elle utile, faisable, sans coût caché pour le serveur ? Retirer ou simplifier ; noter la raison dans la fiche et dans « À valider ».
3. Branche **partie de `main` à jour** : `git fsck`, puis `git switch main && git pull && git switch -c lot/<N>-<mot-clé>`. Si le lot a besoin d'une PR pas encore fusionnée : le dire et attendre.
4. Issue : `gh issue list --state all --search "\"Lot <N> —\" in:title" --json number,title` ; absente → `gh issue create --title "Lot <N> — <titre>" --milestone "V1 complète" --body-file <fichier>` (tâches en cases, avec le `#n` de leurs anciennes issues : `gh issue list --state open --search "\"<numéro> —\" in:title"`). Jalon absent → `gh api repos/GUELORD-MWENDERWA/mwangaza/milestones -f title="V1 complète"`.
5. Fiche `docs/claude/plans/lot-<N>.md`, **30 lignes maximum** : But (pour l'école) · Parties (`- [ ]`, une conversation chacune, reprises de `05` § 2) · Hors périmètre · Critères d'acceptation · Tests obligatoires · Documents à mettre à jour · Risques / à vérifier dans le code. La résumer en 3 lignes ; continuer sauf décision non couverte par les documents.
6. `docs/06-suivi.md` → « État actuel » : lot et partie en cours, branche, issue, date. `gh issue comment <n> --body "Démarré — branche lot/…, fiche : docs/claude/plans/lot-<N>.md"`.
7. **Maquettes de tous les écrans et documents du lot, en une passe**, avant le code (skill `design`, « Méthode » ; `maquettes/README.md`).

## 3. Une partie (une conversation)

1. Skills à suivre : modèle / service / endpoint → `backend` ; montants → `argent` ; synchronisation → `hors-ligne` ; écran → `ecran`.
2. **Tests d'abord**, seulement ceux qui protègent quelque chose : isolation entre deux écoles, permissions (403), argent, audit, vraies règles métier. Pas de test de ce que Django / DRF / React garantissent, de variante presque identique, de libellé ou de mise en page. Playwright seulement pour un chemin critique (connexion, caisse, hors-ligne). Dans un fichier de tests ouvert : supprimer ou fusionner les redondants ; jamais un test d'isolation, de permission, d'argent ou d'audit.
3. Code minimal et propre (`CLAUDE.md` : glossaire, `services.py`, i18n, pas de nouvelle dépendance sans demander) ; pas de N+1 (`select_related` / `prefetch_related`, annotations), listes paginées. Nouveau modèle → `make demo` (`07` § 4) ; nouvelle clé vers un élève → `import_cancellation.py`.
4. Lancer seulement les tests du module touché : `set -a && . ./.env && set +a && cd backend && uv run pytest apps/<app> -q 2>&1 | tail -3` ; `cd frontend && pnpm exec vitest run apps/gestion/src/features/<dossier> 2>&1 | tail -5` ; types : `cd frontend && pnpm typecheck 2>&1 | grep 'error TS'`.
5. Caisse ou hors-ligne : test Playwright qui coupe le réseau, encaisse deux paiements, rétablit le réseau, vérifie aucun doublon, reçus et soldes justes. Erreurs glissées exprès seulement pour l'argent, l'isolation et le hors-ligne.
6. Nouvel écran : une capture à 390 px et une à 1440 px (`make apercu`), comparées à la maquette (alignement, débordement, textes bruts).
7. **Fin de la partie** : cocher la partie dans la fiche et le compteur « Avancement » de `06` ; commit (français, style conventionnel, ligne Co-Authored-By) ; `git push -u origin lot/<N>-…` (sauvegarde : sans PR, la CI ne tourne pas). Pas la dernière partie → dire « Partie k/n faite et sauvegardée. Tape /clear puis /tache lot <N> », ligne `📍`, s'arrêter. Conversation longue au milieu d'une partie : commit, puis « Tape /compact ».

## 4. Fin du lot (après la dernière partie)

1. **Définition de « fini »** (`05` § 8.2), sécurité comprise, pour chaque tâche du lot : une case non remplie = lot pas fini. `make lint` une fois (sortie filtrée). Pas de suite complète en local (la CI la lance ; jamais un nouveau `make demo` dans un test) ; `make test-e2e` seulement si un parcours Playwright a changé. `.tsx` modifié : `apps/gestion/textes.test.ts` ; docstring de vue modifiée : `make api`.
2. Skill `verifier` : résultat en quelques lignes, pour la PR.
3. `docs/05-plan-de-travail.md` : cocher les tâches `- [x]` et barrer la ligne du lot dans § 2 (`~~**Lot N**~~ ✓`).
4. `docs/06-suivi.md` : « État actuel » (aucun lot en cours, prochain lot, date), bloquants réglés retirés, **journal : 3 à 5 lignes** en haut — `### AAAA-MM-JJ — Lot N : titre` puis fait, tests, décisions, suite.
5. **Tous les autres `.md`, une fois** (liste de `CLAUDE.md`, « Suivi du projet ») ; pour chacun : « le lot le rend-il faux ou incomplet ? » :
   - nouvel écran ou API → « Adresses en développement » de `docs/claude/reference.md` **et** `A-FAIRE.md` § 11 ; `make demo` → `reference.md`, `A-FAIRE.md` § 11 **et** `07` § 4 ; commande → `CLAUDE.md` (court) et `reference.md` ;
   - action de l'utilisateur nouvelle, faite ou urgente → `A-FAIRE.md` « Maintenant » (et § 8–9) ;
   - décision technique → `03` « Journal des décisions » ; règle ou champ → `02` / `04` ; maquette → `07` § 1 et `maquettes/README.md` ;
   - façon de faire, commande ou helper de test → skills concernées et README du dossier ; à partir du lot 6, un article d'aide par nouvel écran.
   Contrôle : `git diff main --stat -- '*.md'`.
6. Dernier commit et push, puis PR **unique**, `base: main` : `gh pr create --base main --title "Lot <N> — <titre>" --body-file <fichier>` (modèle ci-dessous). **Ne jamais fusionner.** Corriger la description : `gh api -X PATCH repos/GUELORD-MWENDERWA/mwangaza/pulls/<n> -F body=@<fichier>` (`gh pr edit` échoue).
7. **Pas d'attente à vide** (une PR ne lance que les contrôles de ses fichiers, `.github/scripts/changes.sh` ; « skipped » est normal) : surveiller la CI **en arrière-plan** — `gh run list --branch <branche> --limit 1` jusqu'à ce que le passage existe, puis `gh run watch <id> --exit-status` — et répondre tout de suite (§ 5). Vert : « ✅ contrôles verts, tu peux fusionner ». Rouge : `gh run view <id> --log-failed | tail -40`, corriger, pousser, le dire.

### Modèle de description de PR

Français simple, court ; l'utilisateur comprend **sans lire le code**.

```markdown
## Ce que ça change
Une puce par tâche du lot : ce qui est nouveau pour l'école ou la plateforme, et pourquoi.

## Tests
Tests ajoutés, `make lint` et tests des modules touchés ; suite complète : CI. Vérification des règles : 2 à 4 lignes (✔ / points à noter).

## À valider
Décisions acceptées en fusionnant (où les lire) ; nouvelles dépendances avec leur raison. Sinon : « Rien. »

## À tester toi-même
5 à 8 étapes : commande ou adresse complète → résultat attendu.

## Après la fusion
Fusionner sur GitHub, puis `git switch main && git pull` (+ `make install` / `make migrate` si besoin), `make deploy` (ou « déploie » à Claude), puis `/clear` et `/tache lot <N+1>`.

Closes #<issue du lot>
Closes #<ancienne issue de chaque tâche du lot encore ouverte>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## 5. Répondre à l'utilisateur

Message court, sans attendre la CI : lien de la PR, « contrôles en cours, je te dis ✅ dès qu'ils sont verts », « À valider », « À tester toi-même », « Après la fusion » ; action nouvelle de `A-FAIRE.md` s'il y en a. Puis « Fusionne la PR, puis tape /clear et /tache lot <N+1> » (et le modèle conseillé : Sonnet pour un lot simple, Opus pour un lot difficile).

Dernière ligne : `📍 Lot <N> terminé — prochain : lot <N+1>`.

## Tâche isolée (exception)

`/tache <numéro>` : seulement pour une correction urgente ou une tâche hors lot demandée par l'utilisateur. Mêmes étapes en une conversation : branche `tache/<numéro>-<mot-clé>`, fiche `docs/claude/plans/tache-<numéro>.md` (20 lignes), issue « <numéro> — … », PR « <numéro> — … » ; dire pourquoi elle est hors lot.
