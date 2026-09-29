# Tâche 3.7.2 — Appareils de l'école

**Serveur (`apps/sync`)** : `GET /api/devices/` (appareils actifs de l'école, compte, dernier contact, paginé) et `POST /api/devices/<id>/revoke/`, droit `roles.manage` ; même `services.revoke_device` que « Mes appareils » (audit `devices.revoked`, session fermée, déconnexion si c'est la session en cours). `sync_device` note le dernier contact (`last_seen_at`, au plus une écriture par 30 s) : l'écran sait qui est en ligne.

**Navigateur** : écran `features/devices/DevicesPage.tsx` (maquette `appareils-synchro`) :
- « Appareils de l'école » (avec `roles.manage`) : préfixe, appareil et compte, état (en ligne si contact < 3 min, sinon hors ligne), dernier contact, « Révoquer » avec confirmation qui prévient que les opérations pas encore envoyées seront perdues.
- « Cet appareil (P1) » : dernière synchro, en attente, données locales, stockage persistant, dernier numéro de reçu, « Synchroniser maintenant » ; « File d'attente » : opérations en attente et refusées (heure, type, reçu et montant).
- Pas d'appareil mémorisé : message qui explique « Se souvenir de cet appareil ».
- Entrée du menu : `roles.manage`, `students.view` ou `finance.collect_payment` (le caissier voit sa file).
- Effacement : un appareil déconnecté découvert à la connexion (`attachDevice`) efface aussi sa base locale (aujourd'hui seule la synchro le fait).

**Hors maquette, laissé** : bouton « Autoriser un appareil » (l'appareil s'enregistre lui-même à la connexion) ; colonne « En attente » des autres appareils (le serveur ne peut pas la connaître pour un appareil hors ligne).

**Tests** : pytest — isolation (école B ni listée ni révocable), 403 sans `roles.manage`, audit de la révocation par un responsable, dernier contact mis à jour. Vitest — `attachDevice` efface la base d'un appareil déconnecté ; écran : révocation appelle l'API, carte « Cet appareil » sans appareil.

**Risque** : révoquer un appareil hors ligne qui a encaissé fait perdre ses encaissements non envoyés → avertissement dans la confirmation (À valider).
