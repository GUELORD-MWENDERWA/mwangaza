# Tâche 8.3.4 — Options d'impression au choix (IMP.1)

**But** : un seul jeu d'options (`paper` A4/A5, `orientation`, `per_sheet` 1–3) appliqué par le serveur à tous les documents imprimables, et un panneau « Imprimer » commun côté Gestion dont les choix sont gardés par personne et par document.

**Décisions (regard senior)**
- Mémoire **sur l'appareil** (localStorage, clé = utilisateur + document), pas de table : aucune écriture serveur, rien à synchroniser. Valeurs de départ dans le code ; **pas de réglage d'école** (aucun besoin réel, une page de réglages en plus).
- `per_sheet` seulement pour les documents « coupons » (convocation, circulaire) : sur un tableau de plusieurs pages, N exemplaires n'ont pas de sens. Copie du corps du HTML N fois (aucun calcul serveur de plus).
- Colonnes : déjà au choix (liste de classe : colonnes ; impayés : téléphone, détail) ; elles rejoignent la mémoire. Reçus : imprimés côté appareil avec les exemplaires de l'école (déjà réglables) → hors périmètre. Fiches de cotes : 8.3.6 utilisera ce panneau. Bulletin : formulaire officiel fixe, hors options.

**Hors périmètre** : réglage d'école, reçu imprimé hors ligne, bulletin.

**Critères** : paper/orientation/per_sheet validés et appliqués (`@page`) pour liste de classe, impayés, registre des reçus, situation, fiche d'inscription, convocation, circulaire ; valeur inconnue → 400 ; panneau commun sur ces écrans, choix retrouvés au retour.

**Tests** : serveur — `@page` suit les options, `per_sheet` répète le coupon, 400 sur valeur inconnue ; front — mémoire par personne et par document.

**Documents** : 05, 06, reference.md, A-FAIRE § 11 si adresse, 07 § 1, skill design (impression).

**Risques** : gabarits qui fixent `@page size` (impayés, registre : paysage en dur) → passer par la base.
