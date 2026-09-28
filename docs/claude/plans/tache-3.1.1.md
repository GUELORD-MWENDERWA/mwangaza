# Tâche 3.1.1 — Encaissement côté serveur (Refs #21)

**Fichiers** : `finance/models.py` (`CashRegister`, `CashSession`, `Payment`, `PaymentAllocation`, `PaymentCancellation` minimal ; les trois derniers [I] : ORM + déclencheur PostgreSQL) ; `services.py`, `serializers.py`, `views.py`, `urls.py`, `demo.py` ; `audit/actions.py` ; écran « Échéancier particulier » (échéances non payées seulement) ; `make api`.

**API** : `/api/cash-registers/` (lecture : encaisser ou configurer ; écriture : `finance.configure_fees` ; désactivée, jamais effacée) ; `/api/cash-sessions/` (ouvrir, `current`) ; `/api/payments/` (liste paginée : session, inscription, recherche ; création idempotente par `id` client).

**Règles** :
- Une session ouverte par caisse et par caissier (contraintes partielles). Fermeture : 3.8.
- Répartition par défaut : devise reçue d'abord, échéances les plus anciennes ; autre devise seulement si demandé. Ajustement : parts dans la devise reçue, converties (Q4, demi supérieur). Total des parts = montant reçu ; surplus refusé (crédit : 3.6).
- Taux : celui de l'année, sinon le dernier connu (signalé) ; obligatoire si l'école a deux devises.
- Reçu `{ÉCOLE}-{CAISSE}-{AA}-{000001}` (AA : année scolaire de l'inscription), séquence sous verrou de la caisse.
- Annulé = une `PaymentCancellation` existe (demande / validation : 3.8) ; ses allocations sortent du solde.
- `sync_charges` : un frais payé, même en partie, ne bouge plus et tient la place de la tranche de même rang (changement de classe : pas de double tranche). `reschedule_charges` : échéances sans paiement seulement.

**Tests** : isolation A/B (caisses, sessions, paiements) ; 403 ; répartition (ancienne d'abord, partielle, ajustée, conversion dans les deux sens) ; surplus refusé ; même `id` deux fois → un paiement ; deux sessions refusées ; immuabilité ORM + base ; audit ; solde après paiement puis annulation ; `sync_charges` et `reschedule_charges` avec frais payés.

**Risque** : taille → commit puis /compact si besoin ; `PaymentCancellation` complétée en 3.8.
