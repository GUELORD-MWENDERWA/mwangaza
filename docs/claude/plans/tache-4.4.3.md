# Tâche 4.4.3 — Paiements et reçus (Portail, H3)

**Serveur (`apps/portal`)**
- `children.py` : enfant d'une famille reliée au compte (sinon, ou famille / école suspendue : 404), lu dans son école (`use_school`, fuseau) : solde, frais dus actifs avec un état d'affichage (`paid`, `paid_early`, `partial`, `overdue`, `upcoming`), paiements (annulés marqués), photo seulement si `photo_consent`.
- `GET /api/portal/children/{id}/`, `…/photo/`, `GET /api/portal/payments/{id}/receipt/` (PDF A5 WeasyPrint, paiement annulé : 404).
- Reçu : gabarit `portal/receipt.html` (même contenu que le reçu de la caisse, QR vers `/v/{id}` de l'école, mention « Copie téléchargée sur le portail ») ; montant en lettres porté en Python (`core/words.py`, même règles que `@mwangaza/money`).
- Pas d'audit du téléchargement (lecture de ses propres reçus, pas une réimpression de caisse).

**Portail**
- Écran `/children/:id` (maquette `enfant-paiements`) : en-tête enfant, payé / reste par devise, bandeau retard, prochaine échéance, détail des frais, reçus (PDF). Onglets Scolarité (V1.2) et Profil : pas encore.
- Barre de navigation en bas (Accueil, Paiements) ; Annonces et Profil s'y ajoutent en 4.4.4 / 4.4.5. Carte de l'accueil cliquable + photo.

**Tests** : serveur — enfant d'un autre compte / autre école 404, suspendu 404, états et montants par devise, annulé exclu du PDF, photo sans consentement 404, PDF d'un reçu (contenu) ; montant en lettres (quelques cas) ; écran : états des frais et lien PDF.
**Risques** : WeasyPrint lent (un reçu A5 : léger) ; date « d'avance » au fuseau de l'école (serveur).
