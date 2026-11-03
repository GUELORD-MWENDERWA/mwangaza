# Lot 3 — Vendre : contrats, abonnements, factures

**But** : l'école signe un contrat avec la plateforme, accepte les conditions, reçoit des factures ; la plateforme les gère depuis la console.

## Parties
- [x] ① Offres, conditions générales, contrat (serveur) : app `billing` — `Plan`, `Contract` (brouillon → signé, immuable, avenant), `LegalDocument` versionné, `LegalAcceptance` ; API console + API école ; 6 tests
- [x] ② Serveur : factures, avoirs, paiements de l'école, relevé (ABO.2) ; contrat et facture en PDF (WeasyPrint) ; identité légale de la plateforme (I20) ; textes CTR.1 (CGU, confidentialité, registre) semés
- [ ] ③ Écrans : console (offres, contrats, conditions, factures, paiements, relevé) et fenêtre d'acceptation dans la Gestion ; maquettes d'abord
- [ ] ④ Échéances et lecture seule (ABO.3), « Mon abonnement » (ABO.4), page des prix (WEB.1, SITE.4)

## Décisions (regard senior)
- Prix = **par élève inscrit et par période** (un seul chiffre par offre) ; « prix par module » retiré : un module en plus = un autre plan ou un avenant. Moins de cas à facturer.
- Le contrat **copie** modules et prix du plan : changer l'offre ne réécrit pas l'existant.
- Un seul contrat actif par école (contrainte en base) ; avenant = nouveau contrat lié.
- La partie ② d'origine (serveur + PDF + écrans) ne tenait pas dans une conversation : serveur d'abord, écrans ensuite.
- Facture = jamais modifiée ; annulation = avoir complet lié (pas d'avoir partiel). Paiement = jamais modifié ; erreur = écriture d'annulation liée avec motif.
- Tarif (T6) et informations légales (I20) inventés pour la démo, modifiables dans la console.

## Hors périmètre
Paiement en ligne (V2), signature électronique qualifiée.

## Tests obligatoires
Droits de la console, immuabilité du contrat, un contrat actif, acceptation une seule fois par version, isolation entre écoles, journaux (plateforme et école).

## Documents à mettre à jour en fin de lot
`make demo` (offres Essentiel et Complet, contrat et facture de itig-demo, 3 textes légaux v1) → `reference.md`, `A-FAIRE.md` § 11, `07` § 4 ; I20 (champs de l'identité) → `07` § 2 ; `03` journal des décisions (facture/avoir/paiement immuables) ; `04` entités `Invoice`, `InvoiceLine`, `InvoicePayment`.
