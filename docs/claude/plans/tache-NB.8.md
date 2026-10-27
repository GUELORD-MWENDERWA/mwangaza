# NB.8 — Titulaire : bulletins de sa classe et saisie depuis Ma classe (#404)

**But** (demande du 2026-10-27) : le titulaire imprime les bulletins de sa classe et complète, depuis « Ma classe », la fiche d'un cours dont on lui a remis les points à la main. Ajouts de la même demande : grille des cours figée (la branche visible jusqu'à l'enseignant), « Modèles officiels » rendus utiles, récréation gardée au milieu d'un long atelier.
**Fait** : `_ReportCardView` (titulaire et cotitulaire, 403 `not_your_class`) ; `report-card-status/` donne les élèves ; menu « Bulletins » (`homeroomPermissions`) ; « Ma classe » : « Saisir » et « Bulletins de la classe » ; `Table freeze` sur les cours et le placement ; carte « Programme officiel du ministère » ; récréation : éditeur (bande au-dessus de la séance), impression (case coupée), libellés.
**Hors périmètre** : la récréation dans « Mon horaire » en liste (pas de ligne de récréation aujourd'hui) ; l'horaire général (pas de colonne de récréation).
**Tests** : bulletins du titulaire et du cotitulaire, refus ailleurs, autre école, journal ; menu ; impression coupée autour de la récréation.
**Regard senior** : le titulaire ne reçoit pas `students.view` (trop large) : la liste des élèves vient du contrôle du bulletin, limitée à sa classe.
