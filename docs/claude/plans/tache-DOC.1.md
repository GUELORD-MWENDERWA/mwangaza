# Tâche DOC.1 — Signature et cachet

**But** : l'école dépose son cachet et la signature du chef (nom, titre) dans ses paramètres (`school.configure`) ; chaque membre du personnel dépose sa signature dans « Mon compte » (`Membership.signature`, propre à l'école). Images PNG/JPEG contrôlées (S.4), enregistrées en PNG réduit à 800 px, fond blanc rendu transparent (Pillow, sans dépendance), jamais publiques : servies au personnel connecté de l'école (`HasSchoolAccess`, cache privé), intégrées en `data:` aux PDF.

**Où** : reçu (caissier + cachet ; thermique en gris), reçu d'annulation (demandeur, valideur + cachet), bordereau de clôture (caissier ; le comptable signe à la main en recevant l'argent), convocation (auteur + cachet) ; au nom du chef + cachet : situation financière, fiche d'inscription, circulaire, lettre d'invitation. Rien déposé : ligne à la main comme aujourd'hui.

**Hors périmètre** : bulletins, attestations, palmarès (8.3 et suite) ; registre des reçus (DOC.2) ; reçu du portail parent (pas d'image : des milliers de comptes parents n'ont pas à recevoir le cachet numérique ; le reçu papier le porte) ; pages publiques de vérification (QR) : jamais d'image.

**Critères** : dépôt / retrait / remplacement au journal (`school.signature_changed`, `staff.signature_changed`) ; école B ne lit ni ne change le cachet ni les signatures de A ; personne sans `school.configure` : 403 ; sans compte : 403 ; image piégée refusée.

**Tests** : `schools` (dépôt, permission, isolation, audit, nettoyage de l'image), `accounts` (ma signature, celle d'un collègue, isolation), un document serveur avec l'image ; front : carte des paramètres (envoi), reçu avec / sans signature.

**Documents** : 05, 06, 04 (champs), 03 (journal des décisions), `reference.md` + `A-FAIRE.md` § 11 (API, écrans), 07 § 4 (`make demo` : cachet et signatures fictifs), `maquettes/README.md` (cartes sans maquette).

**Risques** : reçu imprimé hors ligne → image en cache navigateur (adresse versionnée, `me.school.documents` gardé pour le démarrage hors ligne) et préchargée à l'ouverture de la caisse ; image absente → ligne à la main.
