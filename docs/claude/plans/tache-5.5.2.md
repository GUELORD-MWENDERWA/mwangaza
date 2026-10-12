# Tâche 5.5.2 — Notifications dans le Portail (plan)

Issue #40 · branche `tache/5.5.2-portail-notifications` · 2026-10-12 · posée sur la branche de la 4.21 (PR #187 pas encore fusionnée : à fusionner d'abord)

1. **Serveur** (`apps/portal/notifications.py`, vues, routes `/api/portal/notifications/…`) : centre du parent toutes écoles mêlées (seulement les écoles où une de ses familles a encore accès), « lue », notification d'essai, préférences, abonnement et désabonnement de ce navigateur. Aucun modèle nouveau : `Notification`, `PushSubscription` et l'envoi de la 5.5.1 prévoient déjà le Portail.
2. **Portail** : `push-sw.js` chargé par le service worker ; écran `/notifications` (activer sur cet appareil, essai, liste, tout marquer lu) ; cloche dans l'en-tête ; désabonnement à la déconnexion ; `/install` : sur iPhone, les notifications demandent l'application installée.
3. **Commun** : la logique d'abonnement du navigateur passe de la Gestion à `@mwangaza/ui` (`createPush`), les deux applications l'utilisent.
4. Maquette `maquettes/portail/notifications.html` dessinée d'après `gestion/notifications` et `portail/annonces`.

## Regard senior
- **Pas d'écran de préférences à part** : aucune sorte de notification ne vise encore les parents (elles arrivent en 5.6) ; le bloc « sortes à recevoir » ne s'affiche que s'il y a des sortes, l'API est prête.
- **Pas de relecture périodique de la cloche** (des milliers de parents) : non lues lues à l'ouverture, puis quand une notification arrive sur l'appareil.
- Pas de donnée de démonstration : le bouton d'essai en crée une.

## Tests
Serveur : un parent ne lit ni ne marque que ses notifications du Portail, jamais celles d'un autre compte, de la Gestion ou d'une école qui lui a coupé l'accès ; routes refusées à l'adresse d'une école et sans session ; abonnement sans école, envoi au seul navigateur du Portail. Front : activation et liste (Vitest).
