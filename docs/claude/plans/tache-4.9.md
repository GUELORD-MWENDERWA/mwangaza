# Tâche 4.9 — Invitation des familles au portail (H7)

**Serveur** (`apps/students/invitations.py`, actions de `FamilyViewSet`) :
- État du portail d'une famille : `activated`, `suspended`, `no_phone` (tuteur principal sans numéro : activation impossible), `code_expired` (nouveau code périmé), `pending` ; ajouté au sérialiseur famille, filtre `class_group` sur `/api/families/`.
- `GET /api/families/activation/` : par classe de l'année, familles et familles activées (une requête, `students.view`).
- `GET /api/families/letters/?class_group=&output=html|pdf` : une lettre par famille `pending` de la classe ; `GET /api/families/{id}/letter/` : une seule (400 si pas `pending`). Deux lettres par A4 (trait de coupe). `students.edit`. PDF : code noté `students.family_code_printed` (`record_many`) ; aperçu : code masqué.
- `POST /api/families/{id}/invitation-message/` : texte prêt à partager + numéro du tuteur ; noté `students.family_code_shared`.
- QR et lien : `<portail>/activate#<code>` (fragment : jamais envoyé au serveur ni dans les journaux) ; le Portail préremplit le code.

**Front** : écran « Invitations au portail » (`/app/students/invitations`, lien depuis la liste des élèves) : tableau par classe (activées / total), puis familles de la classe choisie avec leur état, lettres de la classe, lettre et message par famille. Fiche famille : « Lettre d'invitation » et « Message à partager » (Copier, WhatsApp, SMS). Portail : `#code` prérempli sur `/activate`.

**Maquettes** : `gestion/invitations-portail.html`, `gestion/lettre-invitation.html` (dessinées par Claude).

**Tests** : isolation (lettres, message, résumé : autre école → 404 / rien), permissions (lecture `students.view`, lettres et message `students.edit` → 403), audit (PDF et message notés, aperçu non), états (`no_phone`, `code_expired`, activée exclue des lettres) ; Vitest : dialogue du message (texte, liens WhatsApp / SMS), préremplissage du Portail.

**Risques** : 800 familles → une classe à la fois (≤ ~60 lettres), pas de lettres de toute l'école d'un coup.
