# Tâche 4.4.5 — Coordonnées (H5, M18)

**Règle suivie** (`02` H5, `04` § 3 priment sur la note de la maquette M18) : le parent envoie ses coordonnées ; **une demande par école** où il a une famille active ; chaque secrétariat l'**applique** à sa propre copie ou ne l'applique pas. Rien n'est changé dans l'école sans elle.

- Champs (portail) : adresse (commune, quartier, avenue, numéro → adresse de chaque élève de la famille dans l'école), e-mail (tuteur principal), contact d'urgence (nom + téléphone → tuteur « urgence » non principal, créé s'il manque). Le téléphone du compte ne change pas. « Téléphone secondaire » de la maquette remplacé par le contact d'urgence (pas de champ au modèle).
- Modèle `students.ContactChange [T]` : `family`, `changes` (champ → avant / après, seulement ce qui diffère), `status` (`pending`, `applied`, `dismissed`), `handled_by`, `handled_at` ; `created_by` = le parent. Une seule demande en attente par famille (contrainte) : un nouvel envoi la remplace.
- Services (`students/contact_changes.py`) : `submit(user, values)` (toutes écoles du compte, `in_school`), `apply(change, actor)`, `dismiss(change, actor)` ; audit `students.contact_change_applied` / `_dismissed`.
- API : portail `GET/POST /api/portal/profile/` ; Gestion `/api/contact-changes/?status=` (liste paginée) + `…/{id}/apply/`, `…/{id}/dismiss/`, droit `students.edit`.
- Front Portail : écran « Mon profil » (`/profile`, entrée Profil de la barre) : identité, formulaire, langue, déconnexion. Front Gestion : « Demandes des parents » (liste + détail, À traiter / Traitées / Toutes, Appliquer / Ne pas appliquer) ; compteur du menu : non (pas de mécanisme de compteur dans le menu).
- Aucune information d'une autre école n'est montrée à l'école (le bandeau « aussi un enfant au C.S. Les Volcans » de la maquette devient générique).
- `make demo` : 3 demandes en attente à l'ITIG.

Tests : isolation (liste, apply d'une autre école → 404 ; le portail n'écrit que dans les familles du compte, pas dans une famille suspendue), droit `students.edit` (403), apply / dismiss (valeurs écrites, audit, déjà traitée → 409), envoi qui remplace la demande en attente, sans changement → aucune demande. Front : un test par écran (envoi du formulaire, appliquer).
