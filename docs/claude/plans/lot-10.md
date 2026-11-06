# Lot 10 — Carte et présences

**But** : chaque élève et chaque membre du personnel a une carte (QR) imprimée au nom de l'école ; à l'entrée, une tablette ou un téléphone enregistré la lit (même sans réseau) ; la direction suit présents, retards, absents, corrige au journal ; le parent est prévenu et justifie l'absence depuis le Portail. Tâches : 6.1 (#41), 6.3 (#138), 6.5 (#139), 6.6 (#51), A.5.

## Parties (une conversation chacune)
- [ ] ① Serveur — Opus, en deux sous-parties : [x] **a** carte (émission, révocation, PDF carte et planche A4) + pointage idempotent (fait le 2026-11-06 : app `attendance`, 4 droits, réglages `card` / `attendance`, `POST …/cards/print/`, `GET /api/attendance/roster/`, opération `attendance.scan`) ; [x] **b** suivi, corrections, justifications, notifications et alerte, `make demo` (fait le 2026-11-06 : `follow.py` calcule tout à la demande, `corrections.py`, `reports.py`, `parents.py` ; travail `absences` du planificateur ; 8 points d'API Gestion, 2 Portail) ; [ ] **c** cartes refaites d'après `maquettes/gestion/cartes-modeles.html` (2026-11-06) : élève en paysage, personnel en portrait (fente du cordon, bande « Personnel »), **bleu de la plateforme et son relief** (`card.color` vide = couleur de la plateforme), photo officielle du personnel `Membership.photo` et fonction `Membership.title`, photo de l'élève imprimée même sans `photo_consent` (choix 1A), `card.require_photo` (oui par défaut : pas de carte sans photo), service de photo officielle (droit `attendance.cards`, au journal, « à réimprimer » si la photo change après l'émission), date de naissance au choix de l'école, « Carte émise avec Mwangaza » au verso — Sonnet
- [ ] ② Écrans : modèle de carte et impression (sélection multiple A.5), **séance photo par classe** (`cartes-seance-photo.html`), pointage caméra / borne hors ligne avec **son, vibration et écran allumé réglables par appareil** (mêmes signaux que les lecteurs, `equipements.md` § 2.3 bis), photo officielle montrée à la lecture, suivi et corrections, Portail (justifier) — Sonnet
- [ ] ③ Fin du lot : Playwright hors-ligne, captures 390 / 1440, `/verifier`, tous les `.md`, aide, PR — Sonnet

## Décisions (regard senior)
- Carte : le QR porte un jeton aléatoire, **le serveur ne garde que son empreinte SHA-256** (+ 4 derniers signes) ; le jeton n'existe en clair que dans le PDF généré à l'émission. Perdue = révoquée, une nouvelle est émise. Hors ligne, l'appareil reçoit les empreintes (pas les jetons) et hache ce qu'il lit.
- Une seule séance « entrée » par jour et par école (créée au premier pointage) ; `AttendanceSession.course` vide. Appel en classe, lecteurs, NFC : lot 16 (EQP.4), même table. Pointage ajouté seulement ; correction = ligne au journal + `AuditLog`.
- Absents = calculés à la demande (élèves inscrits sans pointage ni justification, jours de cours hors congés `SchoolEvent`), jamais stockés. Une tâche par école et par jour (après l'heure limite) prévient les parents et compte les absences non justifiées pour l'alerte (seuil X réglé par l'école).
- Photo officielle (2026-11-06, demande de l'utilisateur) : prise et changée seulement par l'école (élève : `students.edit` ; personnel : `staff.manage`), au journal ; jamais par la personne (ni « Mon compte » ni Portail). À la porte, la tablette montre la photo officielle (vignette en cache, partie ②) : une photo collée sur une carte volée se voit. Format ID-1 85,6 × 53,98 mm = carte MIFARE du kit RC522. App Django **`attendance`** (pas `equipment` : c'est un module vendu ; le lot 16 y ajoute ses séances). « Perdues ce trimestre » → **cette année** (les périodes n'ont pas de dates). Imprimer = émettre : le PDF est rangé 10 min à son adresse (`printing.prepare_at`).
- Lecture caméra : `BarcodeDetector` si disponible ; iPhone n'en a pas → **bibliothèque de lecture QR = nouvelle dépendance, demandée le 2026-11-06** (proposée : `barcode-detector`, MIT, l'API standard partout, chargée seulement sans API native).
- Choix du 2026-11-06 (recommandés, validés) : photo de l'élève sur la carte même sans consentement (1A) ; pas de section dans le matricule, clé de contrôle seulement (2A, MAT.1) ; profils au lot 12 (3A, PROF.1). Son et vibration : Web Audio et `navigator.vibrate` (aucun fichier, aucune dépendance), son débloqué au premier appui, vibration cachée si l'appareil ne la permet pas ; caméra demandée après une phrase qui dit pourquoi.

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
