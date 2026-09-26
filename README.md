# Mwangaza (nom de travail)

Plateforme de gestion scolaire multi-écoles pour la RDC, lancement à Goma.
École pilote : ITIG Don Bosco Goma.

Deux applications sur un même serveur :

- **Gestion** (`{ecole}.mwangaza.cd/app`) — le personnel gère élèves, frais, caisse, reçus. Fonctionne **hors-ligne**.
- **Portail** (`parents.mwangaza.cd`) — les familles consultent paiements, reçus, échéances et annonces.

## Où en est le projet ?

→ **[`docs/06-suivi.md`](docs/06-suivi.md)** : état actuel, avancement, bloquants, journal de chaque étape.
Dans Claude Code : `/etat`. Sur GitHub : onglet **Milestones** (une barre de progression par version, une issue par tâche).

## Organisation du dossier

```
.
├── CLAUDE.md                  règles du projet, lues automatiquement par Claude Code
├── A-FAIRE.md                 ce que toi seul peux faire, comment, et toutes les commandes
├── PROMPT-DEMARRAGE.md        comment démarrer et quels prompts utiliser
├── README.md                  ce fichier
├── docs/
│   ├── 01-cahier-des-charges.md   tout le produit visé (V1.0 → V2)
│   ├── 02-perimetre-v1.md         ce qu'on construit maintenant, et ce qu'on ne construit pas
│   ├── 03-architecture-technique.md  stack, multi-écoles, hors-ligne, sécurité, journal des décisions
│   ├── 04-modele-de-donnees.md    entités, règles métier, permissions
│   ├── 05-plan-de-travail.md      tâches ordonnées à cocher
│   ├── 06-suivi.md                état actuel et journal
│   ├── 07-a-fournir.md            maquettes, informations et décisions encore manquantes
│   ├── ecole-pilote/              ITIG : fiche-itig.md, depot/ (tes fichiers, hors Git),
│   │                              documents/ (rangés), prive/ (données personnelles, hors Git)
│   └── claude/                    espace de travail de Claude : plans/, recherches/, revues/
├── maquettes/
│   ├── README.md              système de design + inventaire des écrans
│   ├── index.html             galerie : ouvrir dans un navigateur
│   ├── gestion/  portail/     maquettes HTML de chaque écran
│   ├── captures/              captures PNG desktop (1440 px) et mobile (390 px)
│   └── assets/                styles.css (jetons du design) et police Atkinson Hyperlegible
└── .claude/skills/            skills Claude Code du projet
```

Code (tâche 0.1, voir `docs/03-architecture-technique.md` § 3) : `backend/` (Django), `frontend/` (workspace pnpm : `apps/gestion`, `apps/portail`, `packages/api|ui|i18n|money`), `infra/` (Docker Compose), `firmware/` (V1.2), `Makefile`.

## Travailler avec Claude Code

| Commande | Rôle |
|---|---|
| `/etat` | Où on en est, prochaine tâche, bloquants |
| `/tache 1.1` | Réaliser une tâche du plan de bout en bout |
| `/noter …` | Noter une étape, une décision, un document reçu |
| `/ecran …` | Construire un écran d'après sa maquette |
| `/design` | Système de design (couleurs, composants, formats) |
| `/backend` | Modèle, service ou endpoint Django conforme aux règles |
| `/argent` | Montants, devises, taux, répartition, affichage |
| `/hors-ligne` | Synchronisation et caisse sans internet |
| `/verifier` | Contrôle des règles non négociables avant commit |
| `/document-ecole` | Intégrer un document réel de l'ITIG |

## Démarrer

Pas à pas (Docker, `.env`, vérifications, dépannage) : **[`A-FAIRE.md`](A-FAIRE.md)**.

Prérequis : Git, Docker, Python 3.12, Node 22, [uv](https://docs.astral.sh/uv/), pnpm (`corepack enable pnpm`), make.

```bash
make install     # dépendances
make dev         # tout lancer dans Docker
```

Puis ouvrir la Gestion sur http://itig.localhost:5173/app/ et le Portail sur http://localhost:5174/.
Toutes les commandes : `make` (détail dans `CLAUDE.md`, section « Commandes »).
