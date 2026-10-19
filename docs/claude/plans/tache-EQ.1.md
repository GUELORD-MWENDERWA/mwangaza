# Tâche EQ.1 — Équipe de la plateforme : serveur

**But** : chaque membre de l'équipe n'a que les droits de son travail. 13 droits et 6 rôles fixes (`accounts/platform_roles.py`), `User.platform_roles` (liste) ; `is_platform_admin` garde son sens de « compte de la plateforme » (double authentification, adresses, session courte, aucun droit d'école). `HasPlatformPermission` remplace `IsPlatformAdmin` sur les 11 vues de la console ; écoles : droit selon l'espace (réel : `schools.*`, essai/démo : `demos.manage`, liste filtrée sans `schools.view`). Équipe (`/api/console/team/`, `platform.team.manage`) : inviter (mot de passe provisoire), changer les rôles, retirer (compte désactivé, mot de passe inutilisable : sessions coupées). Dernier propriétaire protégé. Le super-admin d'aujourd'hui devient propriétaire (migration).

**Hors périmètre** : écrans (EQ.2), contenus du site (SITE), abonnements (ABO : le rôle finance existe, son droit ne garde encore rien).

**Critères d'acceptation** : chaque rôle reçoit 403 hors de ses droits sur chaque point de la console ; un point de la console sans droit déclaré fait échouer un test ; administration Django et session support : propriétaire / `platform.accounts.support` seulement ; alertes envoyées selon le droit (journal : `audit.view`, demandes de démonstration : `leads.manage`) ; `me` donne rôles et droits (menu d'EQ.2).

**Tests obligatoires** : matrice rôles × points de la console (403) ; écoles réelles invisibles au commercial ; invitation, rôles, retrait (session coupée), dernier propriétaire (409), journal avec l'auteur ; numéro d'un compte d'école refusé.

**Documents** : 05, 06, 03 (journal des décisions), 04 (`User`), `reference.md` (API, `make demo`), `A-FAIRE.md` § 11, 07 § 4, skill `backend`.

**Risques** : toutes les vues de la console (la garde parcourt les adresses `/api/console/`) ; `make demo` en dev : un compte par rôle de l'équipe (`0000000001`…`0000000005`), désactivés hors `DEBUG` comme le super-admin fictif.

**Regard senior** : pas de modèle `PlatformMember` (une colonne sur `User`, lue avec le compte : aucune requête de plus par appel) ; pas de remise à zéro d'un membre par le support (retirer puis réinviter).
