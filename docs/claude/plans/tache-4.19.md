# Tâche 4.19 — Reprise en cours d'année (E6)

**But** : importer d'un fichier Excel ce que chaque élève a payé avant la plateforme, sans toucher à la caisse.

- **Données** : pas de nouveau modèle. `Payment.origin` (`cash` | `prior`) ; `cash_session` vide pour `prior` (contrainte en base : l'un ne va pas sans l'autre). Référence dans une série à part `{ÉCOLE}-RP-{AA}-{séquence}` (code `RP` réservé, comme `AN`). Soldes, relevé, impayés, portail et annulation habituelle marchent donc sans rien réécrire.
- **Serveur** : `finance/prior_payments.py` — `template_workbook` (élèves de l'année : matricule, nom, classe, reste dû), `check` (aperçu), `record` (une transaction, `bulk_create`, verrou inscriptions puis école, `touch_enrollments`, journal par paiement). API `POST /api/finance/prior-payments/` (fichier ; `confirm` + totaux de l'aperçu) et `GET …/template/`.
- **Règles** : une ligne = un élève (matricule), un montant, une devise (celle des frais ; pas de conversion), frais facultatif ; répartition habituelle (échéances les plus anciennes). Erreurs : élève inconnu, montant illisible, devise, frais inconnu, plus que le dû, reprise déjà enregistrée (un fichier renvoyé deux fois ne double rien). Ligne sans montant : ignorée.
- **Hors caisse** : exclu de « encaissé » du tableau de bord et des derniers paiements ; sessions et clôtures : exclu de fait (pas de session). Pas de reçu : lecture, réimpression, PDF du portail et vérification publique refusés.
- **Permission** `finance.import_prior_payments` (directeur, comptable ; pas le support) + migration qui l'ajoute aux rôles existants.
- **Écrans** : Gestion `/app/frais/reprise` (fichier → aperçu avec totaux et erreurs → fait), lien depuis « Frais et barèmes » ; ligne « Payé avant … » dans l'historique de l'élève, le relevé et le Portail (nom de la plateforme lu des paramètres). Maquette `gestion/reprise-paiements.html` dessinée d'après `eleves-import`.
- **Tests** : enregistrement et soldes, hors tableau de bord et clôture, erreurs, double envoi, aperçu périmé (409), permission (403), isolation entre deux écoles, annulation habituelle, portail sans reçu ; un Vitest de l'écran.

**Simplifié (regard senior)** : pas de table d'import ni de tâche de fond (le fichier est renvoyé à la validation, ≤ 5 000 lignes en une transaction) ; pas de date par ligne (la date est celle de la reprise) ; pas de conversion de devise ; `make demo` inchangé (aucun modèle nouveau, le modèle pré-rempli suffit pour essayer).

**Risques** : `cash_session` vide dans les écrans qui affichent la caisse d'un paiement (types du client, reçu d'annulation).
