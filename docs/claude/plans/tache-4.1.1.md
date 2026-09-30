# Tâche 4.1.1 — Impayés (G1)

Découpée de la 4.1 le 2026-09-30 (G2 et colonnes de la liste des élèves : 4.1.2).

**Serveur** (`apps/finance/unpaid.py`, vues dans `views.py`, permission `finance.view_reports`)
- Calcul : frais dus des inscriptions actives de l'année (`_ordered` + `_settle`, réductions et annulations comprises), en retard = échéance passée et reste > 0 ; par devise, jamais additionnés.
- Filtres : classe, type de frais, tranche (libellé), retard de plus de N jours (au niveau du frais), devise ; tri : montant (dollars puis francs, ou la devise filtrée), retard, nom, classe.
- `GET /api/unpaid/` paginé (50) : élève, classe, frais en retard, montants par devise, retard max, tuteur principal, dernier paiement non annulé (requêtes groupées pour la page).
- `GET /api/unpaid/summary/` : élèves concernés / inscrits, montant échu par devise, plus de 30 jours, tranches proposées.
- `GET /api/unpaid/export/?output=xlsx|pdf|html` : Excel une ligne par frais en retard ; PDF A4 paysage par classe (total par classe) ou liste unique ; xlsx et pdf tracés (`finance.unpaid_exported`).

**Front** (`features/unpaid/`) : écran « Impayés » (maquette `impayes`), écran « Exporter » (maquette `impayes-export`, aperçu + options). Ligne → fiche élève, onglet Finances.

**Tests** : isolation entre deux écoles (liste et export), 403 sans `finance.view_reports`, calcul (réduction, paiement annulé, deux devises non additionnées, filtre retard/devise/tranche), audit de l'export ; front : filtres → requête, montants par devise.

Risque : calcul en Python sur ~1 200 élèves (2 requêtes) ; acceptable pour la V1.
