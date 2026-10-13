# Plan M.2.2 — Modules : écrans (issue #217)

**But** : les écrans suivent les modules de l'école ; une école neuve choisit ses modules à la création.

**Hors périmètre** : 403 serveur du portail sans `finance` / `communication` (suite si besoin) ; rôles libres (M.3).

**Décisions (regard senior)**
- Le menu de la Gestion suit déjà les permissions de `/me`, qui excluent les modules absents : rien à refaire, un test le prouve. On ajoute `modules` à `/me` (école courante) pour le reste.
- Message « Aucun module activé » sur l'accueil si `modules` est vide.
- Mise en route : étapes calculées d'après les modules (`setup.py`), sans requête de plus ; le serveur reste maître.
- Console : cases des modules à la création (composant partagé avec la fiche) ; dépendances affichées « Nécessite … », cochées d'office ; le serveur tranche (`resolve`).
- Portail : `school_modules` par famille ; « Paiements » et « Annonces » cachés si aucune école active n'a le module.

**Tests** : `/me` rend les modules ; mise en route sans `finance` ; menu sans module ; console (dépendance cochée) ; e2e école neuve : modules choisis à la création, module absent nulle part.

**Documents** : `05`, `06`, `reference.md`, `maquettes/README.md` si écart.
