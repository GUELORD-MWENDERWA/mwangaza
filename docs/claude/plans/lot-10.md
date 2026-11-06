# Lot 10 — Carte et présences

**But** : chaque élève et chaque membre du personnel a une carte (QR) imprimée au nom de l'école ; à l'entrée, une tablette ou un téléphone enregistré la lit (même sans réseau) ; la direction suit présents, retards, absents, corrige au journal ; le parent est prévenu et justifie l'absence depuis le Portail. Tâches : 6.1 (#41), 6.3 (#138), 6.5 (#139), 6.6 (#51), A.5.

## Parties (une conversation chacune)
- [x] ① Serveur — Opus : [x] **a** carte + pointage idempotent (2026-11-06) ; [x] **b** suivi, corrections, justifications, parents prévenus, alerte, `make demo` (2026-11-06) ; [x] **c** (2026-11-06) cartes refaites d'après `gestion/cartes-modeles.html` (cartes congolaises fournies : en-tête officiel, `IdCard.number` séquentiel, noms, naissance, sexe, cachet `School.stamp` à cheval sur la photo, signature, « Délivrée à … le … », formule aux autorités, année ; bleu de la plateforme et son relief ; élève paysage, personnel portrait ; `card.fields`, `card.require_photo`, `Membership.photo` et `title`, service de photo officielle au journal, « à réimprimer ») + **MAT.1** (clé `{C}`, plage du / au / prochain, `organisation-scolaire.html`) + ligne du ministère réglable par la plateforme (EDU-NC, plus « EPST » en dur)
- [ ] ② Écrans — Sonnet : **a1 faite (2026-11-06)** : page `Cartes` (`features/cards/` : élèves / personnel, compteurs, émission + PDF, planche A4 ou une par page, réimpression, carte perdue, onglet Modèle de carte, `without_photo`) ; **a2 faite (2026-11-06)** : séance photo (caméra, file d'envoi, repli appareil du téléphone), fonction du personnel (`title`), matricule (variables, plage, `{C}`), « Ligne du ministère » (Identité, console) ; **reste : b** ; **a** modèle de carte et champs (`printed_fields`, formule, photo exigée), impression (A.5, « à réimprimer », `without_photo`), séance photo par classe et du personnel (`/api/attendance/photos/…`), fonction du personnel (`title`), matricule (plage, `{C}`), « Ligne du ministère » dans Identité de la console ; **b** pointage caméra / borne hors ligne (photo officielle montrée), **SIG.1** sons, vibration, écran allumé (pointage, caisse, séance photo, alertes ; réglage « Cet appareil » de `mon-compte.html`), suivi et corrections, Portail (justifier)
- [ ] ③ Fin du lot : Playwright hors-ligne, captures 390 / 1440, `/verifier`, tous les `.md`, aide, PR — Sonnet

## Décisions (regard senior)
- Carte : le QR porte un jeton aléatoire, **le serveur ne garde que son empreinte SHA-256** (+ 4 derniers signes) ; le jeton n'existe en clair que dans le PDF généré à l'émission. Perdue = révoquée, une nouvelle est émise. Hors ligne, l'appareil reçoit les empreintes (pas les jetons) et hache ce qu'il lit.
- Une seule séance « entrée » par jour et par école (créée au premier pointage) ; `AttendanceSession.course` vide. Appel en classe, lecteurs, NFC : lot 16 (EQP.4), même table. Pointage ajouté seulement ; correction = ligne au journal + `AuditLog`.
- Absents = calculés à la demande (élèves inscrits sans pointage ni justification, jours de cours hors congés `SchoolEvent`), jamais stockés. Une tâche par école et par jour (après l'heure limite) prévient les parents et compte les absences non justifiées pour l'alerte (seuil X réglé par l'école).
- Photo officielle (2026-11-06, demande de l'utilisateur) : prise et changée seulement par l'école (élève : `students.edit` ; personnel : `staff.manage`), au journal ; jamais par la personne (ni « Mon compte » ni Portail). À la porte, la tablette montre la photo officielle (vignette en cache, partie ②) : une photo collée sur une carte volée se voit. Format ID-1 85,6 × 53,98 mm = carte MIFARE du kit RC522. App Django **`attendance`** (pas `equipment` : c'est un module vendu ; le lot 16 y ajoute ses séances). « Perdues ce trimestre » → **cette année** (les périodes n'ont pas de dates). Imprimer = émettre : le PDF est rangé 10 min à son adresse (`printing.prepare_at`).
- Lecture caméra : `BarcodeDetector` si disponible ; iPhone n'en a pas → **bibliothèque de lecture QR = nouvelle dépendance, demandée le 2026-11-06** (proposée : `barcode-detector`, MIT, l'API standard partout, chargée seulement sans API native).
- Choix du 2026-11-06 (recommandés, validés) : photo de l'élève sur la carte même sans consentement (1A) ; pas de section dans le matricule, clé de contrôle seulement (2A, MAT.1) ; profils au lot 12 (3A, PROF.1). Son et vibration : Web Audio et `navigator.vibrate` (aucun fichier, aucune dépendance), son débloqué au premier appui, vibration cachée si l'appareil ne la permet pas ; caméra demandée après une phrase qui dit pourquoi.

- ① c (2026-11-06) : clé `{C}` = **algorithme de Damm** (refuse toute faute d'un chiffre et toute inversion de voisins ; Luhn laisse passer 09 ↔ 90), toujours à la fin du format. Réglage des champs : `card.printed_fields` (`fields` est un nom réservé de DRF). Photo officielle : `attendance.cards` (séance photo, élève et personnel) ou `students.edit` (fiche) ; lue à la porte avec `attendance.scan` (`/api/attendance/photos/…`) ; jamais par la personne. `require_photo` coché par défaut : personnes sans photo laissées de côté (`without_photo`), 409 si plus personne. « À réimprimer » = empreinte de ce que la carte imprime (`IdCard.face_hash`), recalculée à la lecture. Plage pleine pendant un import : l'import échoue (message générique), rare.

## Hors périmètre
NFC, lecteurs ESP32, appel en classe, séances de cours (lot 16) ; paie liée aux présences du personnel (lot 12).

## Critères d'acceptation
Carte émise, imprimée (carte et planche A4 de la sélection), révoquée ; pointage hors ligne rejoué sans doublon ; carte révoquée ou d'une autre école refusée ; retard après l'heure réglée ; absents du jour par classe ; correction au journal ; parent prévenu une fois ; justification vue par l'école.

## Tests obligatoires
Isolation (cartes, pointages, justifications, rapports, Portail) ; 403 sans droit ; audit (émission, révocation, correction) ; idempotence du pointage ; jour de congé non compté ; parent d'un autre enfant refusé.

## Documents à mettre à jour
`05`, `06`, `03` (§ 10 et journal), `04`, `07` § 1 et § 4, `reference.md`, `A-FAIRE.md` § 11, `maquettes/README.md`, aide, spec équipements § 4.

## Risques
`import_cancellation.py` (clés vers l'élève) ; coût : une écriture par pointage, tâche quotidienne en lot ; modules `attendance` (`accounts/modules.py`, `FEATURES`).
