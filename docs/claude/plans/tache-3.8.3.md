# Tâche 3.8.3 — Clôtures de caisse vues par le comptable (M16)

**Serveur** (`finance`) : `CashClosingViewSet` en lecture seule, `/api/cash-closings/`, droit `finance.view_reports`.
- Liste paginée des sessions (mois de l'école `month=AAAA-MM`, caisse) : caissier, heures, paiements, attendu / compté / écart par devise (figés à la clôture ; session ouverte : en direct), état `open` (ouverte aujourd'hui) / `unclosed` (ouverte avant aujourd'hui) / `ok` / `difference`, paiements arrivés après la clôture. Quelques requêtes par page (annotations, pas de N+1).
- `summary/` : sessions, caisses, écarts par devise de l'école (somme, sessions), sessions non clôturées (toutes, pour le bandeau).
- Détail `{id}/` : `closing_summary` + état + paiements arrivés après la clôture (liste). `closing_summary` d'une session close ne compte plus que les paiements reçus avant la clôture (bordereau identique).
- `export/` : Excel du mois (montants en nombres, format par devise ; `workbook` accepte un format par colonne), titres traduits (`make messages`).
- Appareil : `credit_uses` sur l'inscription de la synchro (parts de crédit utilisées, heure, annulation du crédit) → le duplicata les compte comme `balance_after`.

**Front** : `features/closings/ClosingsPage.tsx` (maquette `clotures-caisse`) : filtres mois + caisse, Excel, bandeau des sessions non clôturées, KPI, tableau, détail (lignes par devise, explication, reçus, annulations, heure de clôture / réception, signé par, arrivés après la clôture, bordereau = `SlipCopy` exporté, paiements de la session via `/api/payments/?session=`). `duplicateReceipt` compte `credit_uses`.

**Tests** : isolation (liste, détail, export), 403 sans `view_reports`, états et montants par devise (écart, non clôturée, ouverte), paiement arrivé après une clôture hors ligne (test de synchro étendu), nombre de requêtes de la liste ; Vitest : écran (KPI, détail), duplicata avec crédit utilisé avant.

**Hors tâche** : alerte au directeur au-delà du seuil (4.2), bandeau du tableau de bord (4.x).
