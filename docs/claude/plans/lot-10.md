# Lot 10 — Carte et présences

**But** : chaque élève et chaque membre du personnel a une carte (QR) imprimée au nom de l'école ; à l'entrée, une tablette ou un téléphone enregistré la lit (même sans réseau) ; la direction suit présents, retards, absents, corrige au journal ; le parent est prévenu et justifie l'absence depuis le Portail. Tâches : 6.1 (#41), 6.3 (#138), 6.5 (#139), 6.6 (#51), A.5.

## Parties (une conversation chacune)
- [ ] ① (maquettes faites le 2026-11-06) serveur : app `attendance` (carte, séance d'entrée, pointage idempotent, corrections, justifications, calcul du jour, alerte), PDF carte + planche A4, notifications d'absence — **Opus**
- [ ] ② Écrans : modèle de carte et impression (sélection multiple A.5), pointage caméra / borne hors ligne, suivi et corrections, Portail (justifier) — Sonnet
- [ ] ③ Fin du lot : Playwright hors-ligne, captures 390 / 1440, `/verifier`, tous les `.md`, aide, PR — Sonnet

## Décisions (regard senior)
- Carte : le QR porte un jeton aléatoire, **le serveur ne garde que son empreinte SHA-256** (+ 4 derniers signes) ; le jeton n'existe en clair que dans le PDF généré à l'émission. Perdue = révoquée, une nouvelle est émise. Hors ligne, l'appareil reçoit les empreintes (pas les jetons) et hache ce qu'il lit.
- Une seule séance « entrée » par jour et par école (créée au premier pointage) ; `AttendanceSession.course` vide. Appel en classe, lecteurs, NFC : lot 16 (EQP.4), même table. Pointage ajouté seulement ; correction = ligne au journal + `AuditLog`.
- Absents = calculés à la demande (élèves inscrits sans pointage ni justification, jours de cours hors congés `SchoolEvent`), jamais stockés. Une tâche par école et par jour (après l'heure limite) prévient les parents et compte les absences non justifiées pour l'alerte (seuil X réglé par l'école).
- Photo sur la carte seulement avec `photo_consent` ; personnel : initiales.
- Lecture caméra : `BarcodeDetector` si disponible ; iPhone n'en a pas → **bibliothèque de lecture QR = nouvelle dépendance, à demander avant la partie ②**.

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
