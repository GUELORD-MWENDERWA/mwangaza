# Tâche 3.2.3 — Page publique de vérification `/v/{id}` et QR code du portail sur la fiche

Réf. : F4 (`02`), `03` § 7 (QR, vérification), maquette `portail/verification-recu`.

- **Page `/v/<uuid>`** rendue par Django (`apps/finance/verification.py`, gabarit
  `finance/receipt_verification.html`) : sans JavaScript ni connexion, légère sur un téléphone ;
  le Portail React n'existe qu'en 4.4. École = sous-domaine (middleware) ; paiement cherché dans
  l'école seulement. États : authentique (vert), annulé le … (rouge), inconnu (rouge, 404).
  « Falsifié » et « émis hors ligne, en attente de synchronisation » : 3.3 (signature de l'appareil).
- Affiché : école, numéro, date (fuseau de l'école), élève en initiales + classe, montant.
  `never_cache` (un reçu peut être annulé), `X-Robots-Tag: noindex`, textes traduits (gettext).
- Dev : proxy Vite `^/v/` de la Gestion vers Django (le QR du reçu pointe sur l'adresse de l'école).
- **Fiche d'inscription** : QR code de l'adresse du portail dans le cadre « code famille » ;
  `segno` (Python pur, sans dépendance, BSD ; accepté le 2026-09-28) → `core.documents.qr_code`.
- Tests : reçu valide (pas de nom complet), annulé, inconnu, paiement d'une autre école = inconnu ;
  QR présent sur la fiche avec code famille.
- Risques : école suspendue → réponse JSON du middleware (inchangé) ; Caddy route `/v/` en 4.6.
