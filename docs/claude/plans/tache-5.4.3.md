# Tâche 5.4.3 — Annonces de la plateforme aux écoles

**Serveur (`notifications`)** : `PlatformAnnouncement` [G] (titre, message, destinataires `all_schools` / `schools` + écoles choisies, `published_at`, `archived_at/by` ; jamais modifiée) et `PlatformAnnouncementRead` [G] (annonce, compte, unique). `platform_services.py` : publier, archiver (journal de la plateforme : `announcement.published` / `.archived`), annonces visibles par une école.
- Console `/api/console/announcements/` (liste paginée avec « lue par N », création, `<id>/archive/`) : `IsPlatformAdmin`.
- Gestion `/api/platform-announcements/` (liste paginée, `is_read`) et `read/` (ids) : tout compte de l'école ; session support = lecture sans trace.
- Visible par une école : non archivée, à toutes les écoles ou à elle, publiée après la création de l'école.

**Console** : menu « Annonces », écran `/announcements` (rédiger à gauche, publiées à droite, archiver).
**Gestion** : bandeau (dernière annonce non lue : « Lire », « Fermer » = lue) sous la barre du haut ; écran `/app/platform-news` (lu à l'affichage) ; lien en bas du menu avec le nombre de non lues.

**Tests** : isolation (annonce ciblée sur une autre école invisible, `read/` sans effet), console refusée hors super-admin, journal (publier, archiver), archivée / antérieure à l'école cachées ; Vitest : publication console, bandeau qui se ferme.
**Maquette** : `console/annonces.html` (dessinée, à valider) + capture. **Démo** : 3 annonces (toutes les écoles, ITIG seule, une archivée).
**Décisions** : pas de pièce jointe ni de ciblage par rôle (tout le personnel de l'école) ; pas de modification après publication (comme 4.3).
