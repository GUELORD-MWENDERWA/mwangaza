# Tâche 3.7.1 — PIN de déverrouillage et démarrage sans réseau (B5, M4)

Front seulement : le PIN ne quitte jamais l'appareil (03 § 5.5), aucun changement d'API.

- `lib/device.ts` : l'enregistrement de l'appareil (base `mwangaza-device`) garde aussi `pin` (empreinte PBKDF2-SHA-256 + sel), `pinFailures`, `loggedInAt` (dernière connexion complète, mise à jour par `attachDevice`), `me` et `school` (lus en ligne, pour démarrer sans réseau), `seenAt` ; `update()` dans une transaction (pas d'écrasement entre deux écritures) ; `allDevices()`.
- `lib/pin.ts` : `hashPin`, `checkPin`, `weakPin` (4 chiffres, pas 0000 ni suite 1234 / 4321), `pinState` → `ok` / `none` / `blocked` (5 faux) / `expired` (connexion complète > 7 jours) / `signed_out`.
- Déconnexion (« Se déconnecter ») : `loggedInAt` effacé → mot de passe exigé ; le PIN reste défini.
- `features/shell/PinUnlock.tsx` (maquette `deverrouillage-pin`) : remplace la page « Hors ligne » de `SchoolGate` et `RequireAuth` quand `/api/school/` ou `/api/me/` ne répond pas et qu'un compte de l'appareil a un PIN ; bandeau, avatar, « Bonjour … », école, dernière synchro et opérations en attente, points + pavé (clavier aussi), « Changer d'utilisateur » (poste partagé). Déverrouillé : école et compte gardés mis dans le cache de TanStack Query.
- `AppShell` : garde `me` + `school` sur l'appareil à chaque lecture en ligne.
- Mon compte : carte « Code PIN de déverrouillage » (Défini / Pas défini sur cet appareil, dialogue deux saisies) ; sans appareil mémorisé : explication.
- 7 jours : constante de l'application (pas de réglage d'école en V1).

Tests : `lib/pin.test.ts` (empreinte juste / fausse, 5 faux, 7 jours, déconnexion, PIN faibles) ; Playwright `hors-ligne.spec.ts` : PIN défini dans Mon compte, API coupée puis rechargement → écran PIN, code faux puis juste, caisse ouverte et paiement hors ligne, retour du réseau → synchronisé.
Risque : Vite (dev) ne sert pas l'application sans réseau → test avec `/api/**` coupé avant le rechargement, puis réseau coupé.
