# Tâche 5.6.1 — Notifications : événements immédiats

5.6 découpée (2026-10-12) : les envois **à heure fixe** (échéance proche, retard, caisse non clôturée, relances réglées par l'école) demandent un planificateur, un écran de réglages et une purge — c'est la 5.6.2. Ici, ce qui part au moment de l'action, sans tâche planifiée.

## Fait ici
- `notifications/events.py` : `payment_received` (parent de la famille, ouvre la page de l'enfant et ses reçus), `announcement_published` (familles visées qui ont un compte), `cash_difference` (clôture au-delà du seuil de l'école → comptes qui lisent les rapports), `cancellation_requested` (→ comptes qui valident ; signale le dépassement du seuil du jour).
- Appelés depuis `finance.services` (`record_payment`, `close_cash_session`, `request_cancellation`) et `notifications.services.publish`, dans la transaction ; envoi après validation (socle 5.5).
- Texte écrit dans la **langue du destinataire** (`User.language`), plus celle de la requête.
- 4 sortes nouvelles (`Notification.Kind`, migration de choix) ; préférences : Portail (paiement, annonce), Gestion (alertes offertes selon les droits du compte dans l'école).
- Envoi Web Push par paquets de 200 (une annonce à 1 000 familles ne bloque pas un worker).
- Portail : bloc « Ce que je reçois » sur l'écran des notifications (maquette mise à jour) ; Gestion : libellés des sortes.
- `make demo` : notifications de paiement et d'annonce du parent fictif.

## Retiré ou reporté (regard senior)
- « Annonce au personnel » : l'annonce de l'école au personnel n'existe qu'en 5.7 ; celle de la plateforme est déjà notifiée (5.5.1).
- Ouvrir le PDF du reçu directement : téléchargement brutal dans l'application installée ; la page de l'enfant montre le solde et le reçu en un geste.
- Pas de notification pour la reprise (`origin=prior`) ni pour un paiement renvoyé deux fois (idempotence).

## Tests (`notifications/tests/test_events.py`)
Isolation (l'autre école ne reçoit rien), bons destinataires (droits, portail suspendu, acteur exclu), montants et seuils, rejeu sans doublon, préférences selon les droits.

## Coût serveur
Par paiement : 1 lecture + 1 écriture + 1 tâche. Table `Notification` : ~50 000 lignes par école et par an → purge à 90 jours en 5.6.2.
