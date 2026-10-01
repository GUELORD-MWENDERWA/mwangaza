# Tâche 4.3 — Annonces côté école (H4)

**Serveur** — nouvelle app `notifications` (domaine « Notifications et annonces », `04` § 5) :
- `Announcement` [T] : titre, message, destinataires `all_families` ou `class_groups` (plusieurs classes de l'année en cours, comme la maquette ; `04` en prévoyait une seule), pièce jointe PDF (5 Mo, reconnue à `%PDF-`, jamais publique), `published_at`, `published_by`, `archived_at`.
- `/api/announcements/` : liste paginée (récentes d'abord), publication (multipart), `…/{id}/archive/`, `…/{id}/attachment/` (PDF), `…/recipients/` (nombre de familles touchées pour « Publier pour N familles »). Permission `announcements.publish` partout.
- Familles touchées : familles ayant au moins un enfant inscrit (actif) dans l'année en cours, dans les classes choisies ; une fratrie compte une fois.
- Pas de modification après publication (les familles ont pu lire) : archiver puis republier. Audit : `announcements.published`, `announcements.archived`.

**Front** — `features/announcements/AnnouncementsPage.tsx` (maquette `gestion/annonces`) : formulaire (titre, message, toutes les familles / certaines classes, PDF), aperçu, bouton « Publier pour N familles », liste Publiées / Archivées avec pièce jointe et « Archiver ».

**Hors V1.0 / plus tard** : destinataire « Personnel » (aucun écran où le personnel lit une annonce en V1.0) ; notification sur les téléphones (V1.1) ; « lue par N familles » : avec le portail (4.4), qui marque une annonce lue.

**Tests** : isolation (lire, archiver, PDF, viser une classe d'une autre école), permission 403, règle des familles touchées (fratrie, inscription non active, autre année), PDF refusé, audit ; un test d'écran (publication pour certaines classes).

**Démo** : 3 annonces fictives par école (dont une archivée).
