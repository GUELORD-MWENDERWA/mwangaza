# Tâche 4.4.4 — Annonces du portail (H4)

**Serveur**
- `notifications` : modèle `AnnouncementRead` [T] (`announcement`, `family`, unique ensemble) ; `read_by` (familles qui l'ont lue) dans la liste de la Gestion ; réponse du PDF mise en commun (`attachments.attachment_response`).
- `portal/announcements.py` : annonces visibles d'un compte = pour chaque famille reliée (école active, accès non suspendu) ayant un enfant inscrit (actif) cette année, les annonces non archivées de son école, à toutes les familles ou aux classes de ses enfants, publiées après la fin de l'année scolaire précédente. Une seule requête paginée (toutes écoles), `read` par famille, classes concernées.
- Points d'API : `GET /api/portal/announcements/` (`?family=`), `POST …/announcements/read/` (`ids`, idempotent, ignore ce qui n'est pas visible), `GET …/announcements/<id>/attachment/`.
- `make demo` : une partie des familles a lu les annonces publiées (jamais la famille du compte de démonstration du portail).

**Front**
- Portail : écran `/announcements` (maquette `portail/annonces`), puces par école (2 écoles ou plus), « Nouvelle » sur une annonce pas encore lue, marquée lue à l'affichage, « Plus anciennes » ; entrée « Annonces » de la barre du bas ; mise en cache hors ligne de la 1re page.
- Gestion : « lue par N familles » sous chaque annonce.

**Tests** : visibilité (classes, archivée, autre classe, année passée, autre école, accès ou école suspendus), marquage idempotent et compté dans la Gestion, PDF refusé à une autre famille ; Vitest de l'écran (marquage des non lues, filtre par école).

**À valider** : règle « publiée après la fin de l'année précédente » ; marquée lue dès l'affichage.
