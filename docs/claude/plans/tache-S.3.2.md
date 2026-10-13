# Tâche S.3.2 — Comptes à privilèges : alertes sur l'écran du super-admin

**But.** Le super-admin est prévenu sur l'écran de ses appareils, console fermée, dès qu'un compte super-admin est utilisé ou qu'une école est ouverte « en tant qu'école ».

**Regard senior.** Service worker de la console écrit à la main (`public/push-sw.js`, réception et clic seulement) : pas de Workbox ni de cache, la console reste toujours en ligne et ne peut pas servir une vieille version. Aucune ligne `Notification` (table par école) : l'alerte part du journal, qui reste le centre. Pas de bouton « alerte d'essai » : se reconnecter en produit une vraie.

**Hors périmètre.** Centre de notifications et préférences dans la console ; alerte par SMS ou e-mail (5.6.3) ; alerte pour les autres actions du support (déjà au journal).

**Critères d'acceptation.**
1. Écran « Journal » : carte « Alertes sur cet appareil », bouton « Recevoir les alertes sur cet appareil » / « Ne plus recevoir », états refusé et indisponible ; filtre « Accès » du journal.
2. `GET /api/console/alerts/` (clé publique), `POST …/subscribe/`, `POST …/unsubscribe/` : super-admin, adresse de la console seulement.
3. Envoi par Celery, après validation de la transaction, à chaque `access.login`, `access.code_refused`, `access.address_refused` et à chaque session support ouverte : à tous les comptes super-admin actifs abonnés (celui qui agit compris : son compte a pu être pris), texte dans la langue du destinataire, clic → « Journal » ou « Sessions support ».
4. L'abonnement survit à la déconnexion et à la fin de session (2 h) : c'est justement console fermée que l'alerte sert ; un compte désactivé ou qui n'est plus super-admin ne reçoit plus rien.

**Tests obligatoires.** Permissions (personnel d'une école : 403 ; adresse d'une école : 404) ; l'alerte ne part qu'aux navigateurs de la console, jamais à l'abonnement Gestion ou Portail du même compte ni à un ancien super-admin ; une alerte par entrée `access.*` et par session support ; abonnement expiré supprimé ; adresse d'abonnement en `https` seulement.

**Documents.** `05`, `06`, `03` (décisions), `04` (`PushSubscription`), `reference.md`, `A-FAIRE.md` § 11, `maquettes/README.md` (carte ajoutée au journal), `frontend/apps/console` (commentaire de `vite.config.ts`).

**Risques / à vérifier.** `admin.localhost` accepté comme contexte sûr pour le service worker en développement ; CSP de S.1 (`worker-src` hérite de `default-src 'self'`) ; iPhone : console à installer sur l'écran d'accueil.
