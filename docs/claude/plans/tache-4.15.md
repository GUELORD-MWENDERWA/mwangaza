# Tâche 4.15 — Type d'espace et arrêt (serveur et console)

Issue #158 · branche `tache/4.15-type-espace` · règles : `03` § 4 bis, `02` A4.

**Serveur** (`apps/schools`, une migration)
- `School.environment` (`live` réel, `test` essai, `demo` démonstration), `live` par défaut et pour les écoles existantes ; choisi à la création, absent de la modification, et `save_school` refuse un changement.
- `School.Status.STOPPED` ; `School.CLOSED_STATUSES` et `is_closed` remplacent chaque contrôle « suspendue » (middleware, droits, session support, portail, notifications) : un état fermé de plus ne s'oublie nulle part.
- Adresse d'un espace arrêté : 403 `school_stopped` ; `/api/me/` ne le liste plus.
- `services.stop(school, actor, reason)` : motif obligatoire, journal de la plateforme (`school.stopped`, motif dans `after`) et journal de l'école ; `reactivate` relance aussi un espace arrêté.
- API console : filtre `environment` sur la liste, `environment` à la création, `POST …/stop/` ; tableau de bord : espaces réels seulement.

**Console** (`features/schools`, `features/dashboard`) : onglets Réels · Essai · Démonstration, type choisi à la création, type affiché sur la fiche, « Arrêter » avec motif, « Relancer », filtre « Arrêtés » ; l'état `trial` s'appelle « Essai gratuit » (ne pas confondre avec l'espace d'essai). Gestion : page « Espace arrêté ». Maquette `console/ecoles` mise à jour.

**Tests** : permission (super-admin seul) sur `stop` ; arrêt = plus d'accès (adresse, droits, portail) et données gardées ; motif obligatoire et journaux ; type jamais changé ; tableau de bord sans les espaces d'essai et de démonstration ; liste filtrée par type. Vitest : onglets, arrêt avec motif.

**Regard senior — retiré ou simplifié**
- Pas de colonnes `stopped_at` / `stopped_reason` : le journal de la plateforme garde déjà le motif, la date et l'auteur (historique de la fiche).
- Arrêt réversible (« Relancer ») : un espace réel ne se supprime jamais, une erreur de clic doit se rattraper.
- Espace de démonstration créé ici = vide, avec un directeur ; rempli et sans directeur à la 4.17. `make demo` : `itig` et `volcans` restent réels jusqu'à la 4.17 (plan), le tableau de bord garde donc ses chiffres en développement.
- Aucun coût serveur : une colonne, pas d'écriture par requête, pas d'index (table de quelques lignes).
