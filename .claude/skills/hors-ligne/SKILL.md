---
name: hors-ligne
description: Fonctionnement hors-ligne et synchronisation de l'application Gestion Mwangaza — Device et préfixe, UUID v7 côté client, numéro de reçu sans serveur, file d'opérations (outbox) Dexie, push / pull / snapshot idempotents, ChangeLog, surpaiement, stockage persistant, indicateur de synchro, PIN hors-ligne, tests Playwright réseau coupé. À utiliser pour les tâches 3.3 à 3.8 et pour tout écran ou endpoint qui doit marcher sans internet (caisse, élèves, reçus, plus tard présences et notes).
---

# Hors-ligne et synchronisation

Référence complète : `docs/03-architecture-technique.md` § 5 (principes, endpoints, navigateur, authentification). Modèles : `docs/04-modele-de-donnees.md` § 6 et `Device`.

## Ce qui marche sans réseau en V1.0

Notes (8.2.3) : feuilles lues en ligne puis saisies sans réseau (`grades.save`, copie Dexie `grades` ; mêmes droits qu'en ligne : le carnet est à l'enseignant du cours, `grades.enter_any` n'y met qu'un total, NB.1), envoi et validation en ligne. Consultation des élèves et de leur situation financière, encaissement, impression et réimpression des reçus, demande d'annulation (validée en ligne), clôture de caisse (envoyée à la reconnexion). La configuration (frais, barèmes, rôles, classes) se fait **en ligne seulement**.

## Écrire hors-ligne (navigateur)

1. Identifiant **UUID v7 généré sur l'appareil** pour tout enregistrement créé.
2. Numéro de reçu : `{CODE_ECOLE}-{PREFIXE_APPAREIL}-{AA}-{séquence sur 6 chiffres}` (ex. `ITIG-C1-26-000184`). Séquence dans IndexedDB.
3. **Une seule transaction Dexie** : incrément de la séquence + écriture locale du paiement + ajout de l'opération dans l'outbox. Jamais l'un sans les autres.
4. Opération d'outbox : `{op_id, type, payload, created_at, device_id}` ; `payload` validé par le même schéma zod que le formulaire.
5. `paid_at` = heure de l'appareil ; `synced_at` est posé par le serveur.

## Synchroniser

- Envoi **dans l'ordre**, par lots, `POST /api/sync/push` ; réponse par `op_id` : appliquée / déjà appliquée / rejetée + raison. Opération rejetée : la garder visible et la signaler, ne pas la supprimer en silence.
- Déclencheurs : retour du réseau, démarrage, toutes les 60 s en ligne.
- Descente : `GET /api/sync/pull?since={seq}&limit=…` depuis le `ChangeLog` de l'école ; premier chargement `GET /api/sync/snapshot` (compressé).
- La séquence de reçus est renvoyée au serveur à chaque synchronisation (`Device.last_receipt_seq`) pour être restaurée après réinstallation.

## Côté serveur

- `SyncOperation.op_id` unique : une opération reçue deux fois est appliquée **une seule fois** et renvoie **le même résultat**. Appliquée, elle est effacée après 90 jours (`operations.purge`, A.2) : ce qu'une nouvelle opération crée porte l'identifiant donné par l'appareil, pour qu'un renvoi tardif ne fasse pas de doublon.
- Argent : écritures ajoutées seulement, jamais de conflit ; solde recalculé depuis tous les paiements ; surplus → `StudentCredit` signalé au comptable.
- Données modifiables (fiche élève) : dernière écriture gagne, **champ par champ**, historique dans l'audit, conflit signalé si le même champ est modifié dans la même fenêtre.
- Chaque changement d'une entité descendue écrit une ligne `ChangeLog` (seq croissante par école).
- Appareil révoqué : push refusé, effacement local au prochain contact.

## Navigateur

- `navigator.storage.persist()` au démarrage ; avertissement visible si refusé.
- `SyncIndicator` toujours visible : en ligne / hors-ligne / N opérations en attente / dernière synchronisation.
- Mise à jour de l'application (service worker) : proposée, **jamais forcée** tant qu'il reste des opérations non envoyées.
- Navigateurs cibles de la Gestion : Chrome, Edge récents.

## Authentification hors-ligne (B5, tâche 3.7)

Connexion complète en ligne au moins une fois par appareil puis tous les 7 jours (configurable). PIN vérifié contre une empreinte PBKDF2 locale ; 5 PIN faux → reconnexion complète exigée. Révocation par l'admin → effacement local.

## Tests obligatoires

- **Playwright** : couper le réseau (`context.setOffline(true)`), encaisser deux paiements, imprimer, rétablir le réseau ; vérifier aucun doublon, numéros de reçus corrects et consécutifs, soldes justes côté serveur.
- Recharger la page hors-ligne : données et outbox toujours là.
- **pytest** : même lot envoyé deux fois → une seule écriture ; deux appareils qui paient le même élève → deux paiements + crédit ; appareil révoqué → refus.
- Mise à jour du service worker avec opérations en attente → pas d'activation forcée.
