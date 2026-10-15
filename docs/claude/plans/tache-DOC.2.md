# Tâche DOC.2 — Reçu en bande (issue #252, branche `tache/DOC.2-recu-bande-registre`)

**But** : sur imprimante ordinaire, un reçu par feuille de 21 cm de large, demi A4 (14,8 cm) ou tiers d'A4 (9,9 cm), au choix de l'école ; plus d'exemplaires multiples.

**Hors périmètre** : le registre des reçus (PDF/Excel) → découpé en **DOC.3** (autre module serveur ; regard senior : une page de plus à dessiner, des documents produits par paquets).

**Critères** : `sheet_size` ∈ {half, third}, `copies` retiré ; migration des réglages existants (a6/a5 → half, small → third) ; reçu, reçu d'annulation et bordereau à la bonne taille de page (`@page`) ; carte « Reçus » sans « Exemplaires ».

**Tests** : réglages refusent une ancienne valeur et ignorent `copies`, journal ; écran des paramètres ; PDF des deux formats = 1 page.

**Documents** : 01, 02, 03 (journal), 04 § 1, 05, 06, 07 M5, guide.html, openapi.

**Risques** : tiers d'A4 avec beaucoup de lignes de frais (débordement caché) — deux colonnes pour gagner de la place.
