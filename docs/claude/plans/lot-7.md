# Lot 7 — Finances et caisse complètes

**But** : l'école suit aussi ce qui sort (dépenses, sorties de caisse, budget), inscrit un nouvel élève sans réseau et garde des écrans « Impayés » et tableau de bord légers pour le serveur de 2 Go.

## Parties
- [x] ① Maquettes du lot (6, dans `maquettes/gestion/`) ; FIN.1 serveur : modèles, migration, services, API, droits, audit, démo, tests
- [x] ②a FIN.1 écran « Dépenses » (liste, filtres, saisie avec justificatif, validation, annulation, seuil et catégories, article d'aide) — à regarder à 390/1440 px avant la PR
- [x] ②b1 FIN.2 serveur : payer une dépense en espèces depuis une `CashSession`, clôture et bordereau qui la déduisent, audit, tests (argent, isolation) — **Opus**
- [x] ②b2 FIN.2 écrans en ligne : sortie de caisse, bon de sortie imprimé, ligne « sorties » dans la clôture — Sonnet
- [x] ②b3 FIN.2 hors ligne : sortie en file d'attente, synchro idempotente, Playwright réseau coupé — **Opus**
- [x] ③a HL.1 serveur : opération `student.enroll` (identifiants de l'appareil, frais dus compris), barèmes par classe dans la config, doublon signalé (notification), tests — **Opus**
- [x] ③b HL.1 appareil : « Inscrire un élève » hors ligne (maquette), élève provisoire à la caisse, Playwright réseau coupé (inscrire, encaisser, rétablir) — **Opus**
- [ ] ④ FIN.3 (budget, réalisé/prévu, entrées/sorties, comptes, Excel) ; PERF.7 ; OPS.5 ; fin du lot (docs, vérification, PR)

## Décisions (regard senior)
- Dépense = enregistrement immuable comme un paiement : annulation = nouvel enregistrement lié (motif, permission, audit). Montants entiers + devise + taux.
- Justificatif : image ré-encodée (Pillow) ou PDF, taille limitée, jamais servi hors de l'école.
- Sortie de caisse = dépense en espèces liée à une `CashSession` ; la clôture la déduit du théorique.
- Budget : une ligne par catégorie, année et devise ; rapports calculés en SQL (agrégats), pas d'objets par ligne.
- Export Excel : pas de nouvelle dépendance sans demander (vérifier ce qui est déjà installé).
- Rien de SYSCOHADA (V2) ; paie (lot 12) alimentera les dépenses plus tard.
- Sortie (②b1) : `finance.collect_payment` + session ouverte, jamais plus que ce que la session a reçu dans la devise (pas de fond de caisse : à valider) ; annuler : `finance.cancel_expense`, session ouverte ; attendu < 0 possible (hors ligne). Démo : sortie de 45 $, deux à payer. Reste : `reference.md`, `07` § 4, `03` (fin du lot).
- Hors ligne (②b3) : sur un appareil mémorisé, toujours par la file (comme l'encaissement), bon `…-P1-26-S0001` de l'appareil ; dépense payée ou annulée entre-temps : gardée (l'argent est parti), `conflict` au journal, **pas de notification** (cas rare, à valider) ; sorties faites ailleurs dans la même session pas vues par la clôture de l'appareil (le serveur recalcule).

- Inscription hors ligne (③a) : jamais refusée pour un doublon (l'élève a pu payer) ; doublon trouvé au serveur et pas déjà écarté sur l'appareil (« Ce sont deux élèves ») → notification `possible_duplicate` à ceux qui ont `students.edit`, sans champ ni fusion (à valider) ; frais dus aux identifiants de l'appareil (paiement réparti sur la bonne tranche), identifiant pris ailleurs ignoré ; barèmes envoyés seulement avec un droit sur les finances. Reste : `reference.md`, `03`, `04` (fin du lot).

- Inscription sur l'appareil (③b) : seulement sans réseau ou serveur injoignable (en ligne : écran habituel, matricule tout de suite) ; « Inscrire et encaisser » pour un compte qui a les deux droits (aucun rôle de départ ne les a : à l'école de régler ses rôles, à valider) ; famille existante cherchée par un enfant ou le code (les tuteurs ne descendent pas) ; photo après la synchro.

## Hors périmètre
Comptabilité complète, rapprochement bancaire, paiement en ligne.

## Critères d'acceptation
Une dépense saisie, validée, payée en espèces apparaît dans la clôture ; budget réalisé juste ; nouvel élève inscrit hors ligne puis synchronisé sans doublon ; « Impayés » mesuré avant/après.

## Tests obligatoires
Isolation entre deux écoles (dépenses, budget, justificatifs, exports), permissions (`finance.approve_expense`, annulation), argent (entiers, devises, clôture), audit, idempotence de synchro, Playwright hors ligne (inscrire, encaisser, rétablir).

## Documents à mettre à jour
`reference.md`, `A-FAIRE.md` § 11, `03` (journal, tableau Capacité), `04` (modèles), `07` § 1 et § 4, `maquettes/README.md`, articles d'aide, skill `deployer` (4 Go).

## Risques
Clôture de caisse existante (3.8.2) à ne pas casser ; nouvelles clés vers un élève (`import_cancellation.py`) pour l'inscription hors ligne.
