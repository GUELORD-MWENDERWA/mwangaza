# Lot 3 — Vendre : contrats, abonnements, factures

**But** : l'école signe un contrat avec la plateforme, accepte les conditions, reçoit des factures ; la plateforme les gère depuis la console.

## Parties
- [x] ① Offres, conditions générales, contrat (serveur) : app `billing` — `Plan`, `Contract` (brouillon → signé, immuable, avenant), `LegalDocument` versionné, `LegalAcceptance` ; API console + API école ; 6 tests
- [ ] ② Contrat PDF (WeasyPrint), textes CTR.1 (CGU, confidentialité, registre), écrans console (offres, contrats, conditions) et fenêtre d'acceptation dans la Gestion ; factures, avoirs, paiements, relevé (ABO.2)
- [ ] ③ Échéances et lecture seule (ABO.3), « Mon abonnement » (ABO.4), page des prix (WEB.1, SITE.4)

## Décisions (regard senior)
- Prix = **par élève inscrit et par période** (un seul chiffre par offre) ; « prix par module » retiré : un module en plus = un autre plan ou un avenant. Moins de cas à facturer.
- Le contrat **copie** modules et prix du plan : changer l'offre ne réécrit pas l'existant.
- Un seul contrat actif par école (contrainte en base) ; avenant = nouveau contrat lié.
- Tarif (T6) et informations légales (I20) inventés pour la démo, modifiables dans la console.

## Hors périmètre
Paiement en ligne (V2), signature électronique qualifiée.

## Tests obligatoires
Droits de la console, immuabilité du contrat, un contrat actif, acceptation une seule fois par version, isolation entre écoles, journaux (plateforme et école).
