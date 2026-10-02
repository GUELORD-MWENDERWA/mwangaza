# Tâche 4.4.2 — Enfants et installable (H2, H6)

**Serveur** — `portal` :
- `GET /api/portal/families/` : familles reliées au compte (`Family.primary_user`), toutes écoles ; par famille : école, état (`active`, `suspended` par l'école, `school_unavailable` si école suspendue : aucune donnée de l'enfant), enfants inscrits (actifs) cette année : nom, classe, situation par devise (`finance.services.charges_by_enrollment` + `balance`), premier frais en retard, dernier paiement non annulé. Requêtes constantes par école reliée, chacune lue dans son école et son fuseau (`use_school`).
- `POST /api/portal/families/link/` (« Ajouter un enfant d'une autre école ») : code famille + **numéro du compte = numéro du tuteur principal** de cette école (comme l'activation) ; même erreur pour code inconnu ou numéro différent, essai compté ; famille déjà reliée à un autre compte : refus ; audit `portal.activated`.
- `students` : `Family.portal_suspended_at` ; `POST /api/families/{id}/portal-access/` `{suspended}` (`students.edit`, audit `students.portal_suspended` / `students.portal_restored`). Famille suspendue : activation, ajout et mot de passe oublié refusés.
- `make demo` : compte du portail relié à la famille partagée de l'ITIG ; famille des Volcans à ajouter (code affiché).

**Front** — Portail : accueil (bandeau « Installer », une carte par enfant, carte « accès suspendu » / « service indisponible », bouton « Ajouter un enfant d'une autre école »), page `/add-school`, page `/install` (invite du navigateur sur Android, 3 étapes sur iPhone ; « Plus tard » : 7 jours), proposée après l'activation. PWA : `vite-plugin-pwa` (déjà dans la Gestion), icônes de la Gestion, cache des données du portail vidé à la déconnexion. Gestion, fiche famille : « Suspendre l'accès » / « Rétablir l'accès » (confirmation) et état.

**Tests** — pytest : familles du compte seulement (autre compte, autre école non reliée : rien), famille suspendue et école suspendue sans données, montants par devise ; ajout (succès, mauvais numéro = mauvais code, déjà reliée ailleurs, suspendue) ; suspension (403, autre école 404, audit). Vitest : accueil (carte, suspendue), ajout (erreur traduite).

**Reporté à 4.4.3** : photo, écran des paiements d'un enfant (carte cliquable), reçus PDF, barre de navigation.

**Risques** — données lues hors de l'école de l'adresse (`all_schools`) : toujours filtrées par `primary_user` ; cache hors-ligne d'un téléphone partagé : vidé à la déconnexion.
