# Tâche 3.8.1 — Annulation d'un paiement (F7)

**Serveur (`finance`)** : modèle `CancellationRequest` [T] (paiement, motif, demandeur, heure, appareil, état `pending` / `approved` / `rejected`, décideur, commentaire ; une seule demande en attente par paiement). `PaymentCancellation` reçoit `receipt_number` (`ITIG-AN-26-000007`, série de l'école par année, verrou sur l'école ; code de caisse `AN` réservé).
Services : `request_cancellation` (motif obligatoire ; sans `finance.view_reports`, seulement ses paiements), `approve_cancellation` (pas sa propre demande ; crée `PaymentCancellation`, annule les crédits du surplus du paiement et, par devise, les crédits de réduction à hauteur du trop-payé disparu — le plus récent d'abord, reste recréé), `reject_cancellation`, `reprint_cancellation` (duplicata, audit). Audit de chaque étape.
API : `/api/cancellations/` (liste paginée par état, détail, création, `approve`, `reject`, `reprint`) ; lecture : `approve_cancellation` voit tout, le demandeur seulement ses demandes. `PaymentSerializer` : `cancelled_at`, `cancellation_pending`.
Sync : opération `cancellation.request` (idempotente par `op_id` et par demande en attente).

**Front** : écran `/cancellations` (maquette `annulations` : onglets, tableau, panneau de décision) ; dialogue « Demander une annulation » depuis la caisse et le crédit (maquette `demande-annulation` créée d'après `caisse-accueil` / `eleve-reduction`), par la file sur un appareil mémorisé ; reçu d'annulation au format de reçu de l'école (maquette `recu-annulation`) ; paiement « annulation demandée » à la caisse ; duplicata sur l'appareil exact (paiement annulé après lui compté).

**Tests** : isolation (liste, détail, décision, opération), 403 (caissier ne valide pas, pas sa propre demande), audit, crédits annulés (surplus, réduction partielle), numéro de série, idempotence de l'opération ; front : dialogue par la file, décision, duplicata.

**Hors périmètre** : alerte « > 3 annulations / jour / caissier » (4.2, M5) ; 2FA déjà exigée à la connexion pour toute permission finance : pas de second code.
