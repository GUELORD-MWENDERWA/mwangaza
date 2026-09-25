# Démarrer avec Claude Code

## 1. Préparer le dossier

Place ce dossier `mwangaza/` tel quel (ou copie son contenu dans un dépôt Git vide) :

```
mwangaza/
├── CLAUDE.md                 ← lu automatiquement par Claude Code
├── PROMPT-DEMARRAGE.md       ← ce fichier
├── README.md                 ← présentation et organisation du dossier
├── docs/                     ← cahier des charges, périmètre, architecture, données, plan, suivi
│   └── ecole-pilote/         ← documents réels de l'ITIG (prive/ hors Git)
├── maquettes/                ← écrans HTML, captures PNG, système de design
└── .claude/skills/           ← skills du projet (/etat, /tache, /noter, /ecran…)
```

Puis, dans le terminal de VS Code (le dépôt Git est déjà initialisé) :

```bash
git add . && git commit -m "docs: cahier des charges, maquettes, suivi et skills"
claude
```

Outils à installer sur ton PC avant : Git, Docker Desktop, Python 3.12+, Node.js LTS, pnpm.

## 2. Premier prompt (à coller tel quel)

```
Tu vas construire Mwangaza, une plateforme de gestion scolaire multi-écoles pour la RDC, avec l'ITIG Don Bosco Goma comme école pilote.

Avant d'écrire la moindre ligne de code :
1. Lis entièrement CLAUDE.md, puis docs/01 à docs/05, puis maquettes/README.md.
2. Regarde les captures dans maquettes/captures/desktop et maquettes/captures/mobile, en particulier caisse-encaissement, recu, eleve-fiche et portail-enfant-paiements.
3. Fais-moi un résumé en 10 points maximum de ce que tu as compris : le produit, le périmètre V1.0, les règles non négociables (multi-écoles, argent en entiers, paiements immuables, hors-ligne), et la stack.
4. Liste les questions ou contradictions que tu as trouvées dans les documents.

Ensuite, propose ton plan pour la tâche 0.1 du plan de travail (structure du monorepo, Docker Compose de développement, commandes), sans rien créer.
Attends ma validation avant de créer des fichiers.
```

## 3. Prompts suivants (un par tâche)

Raccourci : `/tache 1.1` fait tout ce qui suit (y compris le test Playwright hors-ligne pour la caisse) et met à jour `docs/06-suivi.md`. `/etat` dit où on en est. Le prompt complet reste valable :

Après validation du plan, pour chaque tâche :

```
Fais la tâche 1.1 du plan de travail (docs/05-plan-de-travail.md).
Respecte CLAUDE.md. Écris les tests d'abord pour les règles métier.
Si la tâche touche un écran, reproduis la maquette correspondante (capture PNG + fichier HTML) avec React, Tailwind et shadcn/ui, en utilisant les jetons de maquettes/README.md.
À la fin : lance les tests, montre-moi le résultat, coche la tâche dans le plan et propose le message de commit.
```

Quand une tâche concerne la caisse ou le hors-ligne, ajoute :

```
Ajoute un test Playwright qui coupe le réseau, encaisse deux paiements, rétablit le réseau et vérifie : aucun doublon, numéros de reçus corrects, soldes justes côté serveur.
```

## 4. Bonnes habitudes

- **Une tâche à la fois.** Relis le code, lance l'application, teste toi-même, puis commit.
- Si Claude propose d'ajouter une bibliothèque qui n'est pas dans la stack, demande-lui pourquoi avant d'accepter.
- Quand tu reçois un document réel de l'ITIG (grille des frais, bulletin officiel, liste d'élèves), mets-le dans `docs/ecole-pilote/` (ou `docs/ecole-pilote/prive/` s'il contient des données personnelles) et lance `/document-ecole`.
- Pour tout événement hors tâche (réunion à l'ITIG, décision, blocage) : `/noter …`.
- Chaque fin de semaine : demande à Claude de mettre à jour le « Journal des décisions » de `docs/03-architecture-technique.md`.
- Ne mets jamais de mot de passe, clé ou jeton dans le dépôt : utilise un fichier `.env` ignoré par Git.
