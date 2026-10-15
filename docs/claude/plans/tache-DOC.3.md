# Plan DOC.3 — Registre des reçus (PDF et Excel)

**But** : `GET /api/receipt-register/` (`finance.view_reports`) : un reçu par ligne (numéro, date, élève, classe, montant, devise, caissier, annulé), par période (du… au…) et par caisse ; totaux par devise et par caisse ; cachet et signature du chef à la fin (DOC.1). Sorties `xlsx`, `pdf`, `html` (aperçu). Bouton « Registre des reçus » sur l'écran Clôtures de caisse (choix jour / mois / dates, caisse, format).

**Hors périmètre** : paiements de reprise (`origin=prior`, sans reçu) ; reçus d'annulation (colonne « annulé » avec leur numéro, pas de ligne propre) ; réglage `copies` (déjà retiré en DOC.2).

**Regard senior** : pas de tâche de fond Celery. Période bornée à 366 jours, PDF à 3 000 reçus (au-delà : message « réduis la période ou prends l'Excel »), Excel écrit ligne à ligne (50 000 max) : une requête, pas de file ni de table de plus. Une école de 1 200 élèves fait ~1 500 reçus par mois.

**Critères** : annulés listés mais hors totaux (comptés à part) ; totaux par devise jamais additionnés ; fuseau local pour les jours ; export tracé dans l'audit (`finance.receipt_register_exported`) ; aperçu non tracé.

**Tests** : isolation (autre école absente, caisse d'une autre école refusée), permission (caissier sans `view_reports` : 403), totaux et annulés, filtre caisse et dates, audit, plafonds.

**Documents** : 05 (cocher + file), 06, reference.md, A-FAIRE § 11, 07 § 1, maquettes/README, traductions (`make messages`), `make api`.

**Risques** : requêtes N+1 (select_related enrollment/student/class/cashier/session/cancellation) ; texte i18n des .po.
