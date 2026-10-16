# Plan PERF.3 — Bulletin plus léger (issue #280, branche tache/PERF.3-bulletin-leger)

**But** : une page de bulletin ≤ 1 s de mise en page et ≤ 5 Mo de PDF. Mesuré avant : 2,1 s, 115 Ko (HTML 1,1 Mo : polices en base64). Coût annoncé après : ≈ 0,8 s par page, mêmes 115 Ko.
**Profil** (cProfile WeasyPrint, bulletin de 23 cours) : mise en page ≈ 70 % dont ≈ 80 % dans la colonne flex de la feuille (le tableau y était mesuré deux fois) ; polices ≈ 0,35 s par document (1 Mo de base64 décodé à chaque fois). `table-layout: fixed` était déjà en place.
**Fait** : (1) feuille en bloc au lieu de colonne flex, le bloc sous le tableau reçoit sa hauteur calculée (`_under_height`) ; (2) polices lues une fois par processus (`printing._fonts`, `printing.to_pdf`), le HTML du PDF n'en porte plus (l'aperçu oui).
**Hors périmètre** : retirer les petits flex de l'en-tête (gain < 0,1 s, risque sur la mise en page) ; autres documents : seul (2) leur profite, leur mise en page n'est pas retouchée.
**Critères** : même géométrie qu'avant (écart ≤ 0,5 mm mesuré sur `.under`/`.foot`) ; PDF avec polices Liberation embarquées ; aperçu HTML avec polices ; clés des PDF gardés recalculées (une fois).
**Tests** : hauteur du bloc sous le tableau (valeur mesurée avant, bornes pour 10 à 60 lignes) ; polices dans le PDF mais pas dans son HTML ; tests existants de PDF gardés / impression.
**Documents** : 05, 06, 03 (journal), reference.md.
**Risques** : bas de feuille si la note de pied passe à 4 lignes (traduction) → `FOOT_HEIGHT`, `SAFETY` ; mémoire : la configuration de polices reste en mémoire dans chaque processus (quelques Mo).
