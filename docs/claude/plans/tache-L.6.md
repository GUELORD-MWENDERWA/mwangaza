# Tâche L.6 — Travailler sans internet : code PIN proposé après la connexion

**But** — Constaté le 2026-10-17 : la Gestion installée affiche « Pas de connexion au serveur » sans réseau. Le démarrage sans réseau (B5, 3.7.1) marche, mais exige un appareil mémorisé **et** un code PIN, et rien ne propose le PIN (carte cachée dans « Mon compte »).

**Hors périmètre** — nouveaux écrans hors ligne (seules la caisse et les élèves travaillent sans réseau en V1, `02`) ; changement des règles du PIN (7 jours, 5 essais).

**Critères d'acceptation** — bandeau « Travailler sans internet sur cet appareil » sur un appareil mémorisé sans PIN, jamais en session support ni sur « Mon compte », « Plus tard » jusqu'à la prochaine ouverture, disparu dès le PIN enregistré ; le bouton ouvre la carte PIN prête à la saisie ; page hors ligne : comment préparer l'appareil quand aucun compte n'a de PIN. Maquette `gestion/hors-ligne-preparer` d'abord ; 390 et 1440 px regardés.

**Tests obligatoires** — Vitest : bandeau avec et sans PIN ; test existant « pas de réseau au démarrage » gardé. Le parcours Playwright hors ligne (PIN puis caisse) existe déjà.

**Documents à mettre à jour** — `05`, `06`, `03` (journal), `07` § 1, `maquettes/README.md`, `A-FAIRE.md` (étapes faites, mise en ligne).

**Risques / à vérifier** — aucun appel serveur en plus (appareil lu dans IndexedDB) ; le nom de la plateforme jamais dans les textes (règle 9, `textes.test.ts`).
