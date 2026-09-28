# Tâche 3.3.1 — Appareils

**Serveur (app `sync`)** : `Device` [T] (`user`, `kind`, `label`, `prefix` unique dans l'école, `cash_register`, `public_key` SPKI base64 P-256 vérifiée, `session_key`, `last_seen_at`, `last_receipt_seq`, `revoked_at`). `services.py` : `register_device` (préfixe `P{n}` jamais réutilisé ni égal au code d'une caisse, verrou sur l'école), `resume_device`, `revoke_device` (efface la session de l'appareil), `verify_signature` (signature brute r‖s de WebCrypto). Session : `sync.device` = {id, school}. Audit : `sync.device_registered`, `sync.device_revoked`.
**API** `/api/me/devices/` : liste de mes appareils dans l'école (non révoqués, `is_current`), `POST` enregistrer, `POST {id}/resume/` (révoqué → 409 `device_revoked`), `POST {id}/revoke/`. Membre actif de l'école exigé.
**Audit** : `AuditLog.device` (FK, PROTECT) et `device_time` (heure de l'appareil, remplie par la synchro en 3.3.2) ; `record()` prend l'appareil de la session (`RequestInfo`) et `device_time=` ; serializer + écran du journal (appareil, heure de l'appareil / de réception).
**Front** : `lib/device.ts` (IndexedDB brut `mwangaza-device` par compte, paire ECDSA non exportable, libellé « Windows · Edge », `attachDevice` après `done`), case « Se souvenir de cet appareil » (cochée, gardée dans `sessionStorage` jusqu'à `done`), carte « Appareils connectés » de Mon compte (Déconnecter avec confirmation).
**Démo** : un appareil par caissier et secrétaire des deux écoles.

**Tests** : pytest — isolation (autre école : 404 sur resume / revoke, liste vide), autre compte (404), sans connexion (403), préfixes (suite, caisse `P1` sautée), clé invalide (400), révocation (session fermée, audit), resume révoqué (409), audit porte l'appareil, signature WebCrypto réelle vérifiée (jeu fixe généré par Node). Vitest — libellé du navigateur, choix resume / enregistrer / oublier.

**Décisions** : préfixe `P{n}` (poste) pour ne jamais croiser un numéro de reçu donné par le serveur avec le code de caisse (C1) ; `Device` dans l'app `sync` (plan) et non `accounts` ; clé dans une base IndexedDB à part, sans Dexie (3.4).
**Risques** : jsdom sans IndexedDB ni WebCrypto (logique testée avec un stockage injecté).
