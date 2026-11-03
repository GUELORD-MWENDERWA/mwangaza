# Lot 4 — Bulletins aux parents

**But** : à la fin de la première période, le parent voit sur le Portail les notes et le bulletin de son enfant (si les frais sont réglés ou une dérogation accordée), peut écrire à l'école, et l'école est prévenue des étapes des notes.

## Parties
- [x] ① Serveur : blocage du bulletin liés aux frais + dérogation (8.4.6), notifications des notes validées / résultats proclamés ou rouverts (8.2.6) ; maquette `derogations-bulletin.html` dessinée
  - Reste de 8.2.6 (à faire en partie ④) : total corrigé par un autre, fiche rouverte, remplaçant désigné, date limite proche, repêchage à saisir ; chaque sorte est déjà désactivable
- [x] ② Serveur Portail : notes, bulletins PDF contrôlés, résultats (un appel par enfant), fil parent ↔ école par élève (8.8)
  - Droit de répondre = `announcements.publish` ; PDF 10 par minute ; journal des consultations de bulletins à faire en ④ (S.10)
- [x] ③ Écrans Portail (scolarité, bulletin, écrire à l'école) et Gestion (dérogations, réponses) ; maquettes `portail/enfant-bulletin`, `gestion/messages-parents`
  - Gestion : « Dérogations de bulletin » (`grades.waive_fees`) et « Messages des parents » (`announcements.publish`) sous Communication ; réglage « Retenir le bulletin » dans Paramètres › Portail ; Portail : cartes notes / décision / bulletin / « Écrire à l'école » sous la conduite
- [ ] ④ Portail sans réseau (HL.3), rapidité (PERF.6), revue de sécurité (S.10)

## Décisions (regard senior)
- Le blocage porte sur le **PDF du bulletin** (servi par le Portail après contrôle du droit), pas sur la décision de passage, toujours visible. Règle : frais **échus** impayés = bulletin retenu ; réglage de l'école (`report_requires_payment`, défaut : non) ; calcul à la lecture, rien stocké en plus ; réglage rangé dans `School.settings["portal"]`.
- Dérogation = une ligne (`FeeWaiver` : famille ou élève, motif, jusqu'au, accordée par) ; jamais modifiée, levée = `lifted_at` (seul changement, journalisé) ; droit dédié `grades.waive_fees` au préfet.
- Fil parent ↔ école : un `Thread` par élève, des `Message` ; pas de pièces jointes, pas de temps réel (la messagerie complète reste V1.7).
- Portail sans réseau : on garde la dernière réponse JSON lue (IndexedDB déjà utilisée ?), lecture seule, effacée à la déconnexion ; pas de PDF hors ligne.

## Hors périmètre
Messagerie complète, paiement en ligne, envoi du PDF par courriel/WhatsApp.

## Tests obligatoires
Isolation (parent d'une autre famille, autre école : 404), bulletin retenu / servi / dérogation expirée, droit de dérogation (403), audit, un message par geste de notification, limite d'essais sur le PDF.

## Documents à mettre à jour
`reference.md`, `A-FAIRE.md` § 11, `07` § 1 et § 4, `04` (FeeWaiver, Thread, Message), `03` journal, `maquettes/README.md`, 05 (cases), 06.
