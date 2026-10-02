# Tâche 4.5.1 — Guides de première connexion (I3, M20)

4.5 découpée : 4.5.1 guides (2 écrans), 4.5.2 traductions (≈ 520 textes du serveur, relecture de l'anglais).

**Gestion** (`features/guide/`) : guide du caissier (5 étapes, page Caisse) et du comptable (6 étapes : Frais et barèmes ×2, Élèves, Annulations, Clôtures, Impayés).
- Choix par le code du rôle système (`cashier` d'abord, puis `accountant`) ; étapes filtrées par les droits de l'utilisateur.
- Chaque étape : adresse + cible `data-guide="…"` sur un vrai élément ; anneau lampe + reste assombri (calque `pointer-events: none` : l'utilisateur continue d'agir lui-même). Le guide ne change de page que depuis l'accueil, sur « Suivant » ou « Aide et guide ». Cible absente (ex. montant avant le choix d'un élève) : carte en bas, sans assombrir.
- Progression dans `localStorage` par utilisateur (`mwangaza.guide.<id>`) : étape, terminé. Hors-ligne d'office (textes i18n, aucun appel au serveur).
- « Passer le guide » = terminé ; croix = fermé jusqu'à la prochaine ouverture de l'application, reprend à la même étape. « Aide et guide » en bas du menu (latéral et tiroir) le relance au début.

**Portail** (`/guide`) : 3 étapes (enfants, paiements et reçus, annonces et coordonnées), exemples fixes traduits ; glisser ou « Suivant », « Passer ». Après l'activation : `/guide?first=1` puis « Installer » (si proposé) ou l'accueil ; Profil → « Revoir le guide ».

**Tests** : `guide.test.tsx` (démarrage, reprise sans changer de page, passer, relance ; étapes selon les droits ; aucun guide pour le directeur) ; Portail : activation → guide → accueil, « Revoir le guide ».

**Risques** : position de la carte sur petit écran (largeur pleine moins 16 px) ; pas de dépendance nouvelle (pas de bibliothèque de « tour »).
