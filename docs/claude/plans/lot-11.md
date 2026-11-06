# Lot 11 — Bibliothèque et ateliers

**But** : l'école prête ses livres et ses outils sans papier ni cahier perdu ; le parent est prévenu ; un livre perdu devient une dette payée à la caisse ; les ateliers savent ce qu'ils ont, ce qui manque et qui l'a pris. Tâches : INV.1, BIB.1, BIB.2, BIB.3, ATL.1, ATL.2, ATL.3.

## Parties (une conversation chacune)
- [x] ①a Serveur — Opus (2026-11-06) : app `inventory` (modèles de tout le lot), modules `library` / `workshops`, 6 droits, rôle « Bibliothécaire », catalogue + exemplaires + import Excel, règles (`/api/library/rules/`), prêt / retour par la synchro (`inventory.loan`, `inventory.return`), prolongation, constat → `StudentCharge` (source `item`) et rectification, pénalité de retard, liste du guichet (`/api/library/desk/`), `import_cancellation.py`, libellés front (droits, notifications, audit, modules)
- [ ] ①b Serveur — Opus : rappels quotidiens (`Job.LOANS`, BIB.3) ; Portail « livres de mon enfant » ; ateliers `/api/workshops/…` (lieux, articles, stock + seuil, mouvements et correction, commandes → dépense FIN.1 → réception, bons de sortie, outils prêtés : même synchro) ; inventaires (comptage, écarts, validation) ; `make demo` (+ compte bibliothécaire `0000001011`, droits du chef d'atelier) et `test_demo.py`
- [ ] ② Écrans — Sonnet : **a** bibliothèque (catalogue, étiquettes, guichet prêt / retour hors ligne, prêts et retards, constat, règles, bon de prêt PDF, Portail : « livres de mon enfant ») ; **b** ateliers (stock, commandes, bon de sortie, outils prêtés) et inventaire scanné
- [ ] ③ Fin du lot — Sonnet : Playwright hors ligne (prêt + retour réseau coupé, aucun doublon), captures 390 / 1440, aide, `/verifier`, tous les `.md`, PR

## Décisions (regard senior)
- Une seule app **`inventory`** (pas `equipment`, qui est celle des appareils) ; deux modules vendus : `library` (BIB) et `workshops` (ATL), le moteur INV.1 est dessous et dérive des deux ; `library` dépend de `students`.
- Mouvement de stock **immuable** (comme un paiement) : erreur = mouvement inverse. Stock = somme des mouvements, jamais un compteur modifié ; un exemplaire a un état (`available`, `lent`, `lost`, `withdrawn`) changé seulement par un prêt / retour / constat.
- Hors ligne (niveau A, `equipements.md` § 5) : seuls **prêt et retour** passent par la file ; « livre déjà prêté » au rejeu = rejet visible dans « à revoir », pas de blocage. Catalogue, commandes, inventaire : en ligne.
- Perte : un `StudentCharge` (règles de l'argent), pas de nouvelle table de dettes ; tarif = prix de remplacement de l'article.
- Pénalité de retard facultative, désactivée par défaut ; rappels par le planificateur existant, **une tâche par jour et par école** (pas une par prêt).
- Inventaire : feuille de comptage (scan des étiquettes) → écarts → mouvements de régularisation validés par la direction ; **en ligne** (`equipements.md` § 5 à corriger).
- ①a : les limites (nombre de prêts, retard, ouvrage de référence) sont appliquées **par l'appareil** au guichet ; au rejeu le serveur ne refuse que l'impossible (déjà prêté, perdu, élève parti) : refuser un prêt déjà fait laisserait le livre dehors sans trace. Une seule bibliothèque par école (créée au premier besoin) ; l'enseignant reçoit `workshops.request`, le directeur la gestion et la validation.

Partie ② : étiquettes et bon de prêt (PDF), libellés de la source `item` et des erreurs ; docs/04 § 8 (rôle Bibliothécaire, 6 droits : tableau recopié dans `test_starter_roles.py`).

## Hors périmètre
Achat d'ouvrages en ligne, numérique (PDF des livres), lecteurs RFID / NFC (lot 16), comptabilité des immobilisations.

## Critères d'acceptation
Livre prêté et rendu (même réseau coupé), parent prévenu avec la date, retard relancé une fois par jour, perte → dette payée avec reçu normal, stock bas signalé, commande suivie de la demande à la sortie, outil prêté à un élève.

## Tests obligatoires
Isolation (catalogue, prêts, stock, commandes, inventaire, Portail) ; 403 sans droit ; audit (prêt, retour, perte, mouvement, commande, régularisation) ; idempotence des opérations de synchro ; conflit « déjà prêté » ; argent de la perte en entiers + devise.

## Documents à mettre à jour
`05`, `06`, `03`, `04`, `07` § 1 et § 4, `reference.md`, `A-FAIRE.md` § 11, `maquettes/README.md`, `CLAUDE.md` (liste des apps), aide, `equipements.md` § 5.

## Risques
`import_cancellation.py` (prêts liés à un élève) ; `StudentCharge` payé à la caisse ; dépense FIN.1 ; tâche quotidienne en lot.
