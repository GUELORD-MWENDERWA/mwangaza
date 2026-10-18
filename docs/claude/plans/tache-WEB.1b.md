# Tâche WEB.1b — Pages du site public (d'après les maquettes de WEB.1a)

**But** : remplacer la page unique (`apps/core/site.py`) par les 7 pages de `maquettes/site/` en français et en anglais : accueil, écoles, parents, modules, démonstration et contact, « Trouver mon école », mentions et confidentialité ; gabarit commun (en-tête, menu du téléphone sans JavaScript, pied complet avec « © DTMS »), animations en CSS et quelques lignes de JavaScript, vraies captures du produit en WebP.

**Hors périmètre** : formulaire de demande de démonstration, son modèle, l'alerte au super-admin et l'écran de la console (**WEB.1d**, découpée le 2026-10-18 à ta demande) ; images de partage, données structurées complètes, titres pour la recherche (WEB.1c) ; page des prix (V1.3).

**Critères d'acceptation**
- 7 pages × 2 langues, lisibles sans JavaScript, en cache (`Cache-Control: public`), une seule lecture en base par page (plus les chiffres, en cache une heure) ; `hreflang` et lien de langue vers la même page ; `sitemap.xml` avec les 14 adresses.
- Nom, logo, couleurs, contact : identité de la plateforme ; modules : catalogue `accounts/modules.py` (+ une description traduite par module) ; « Prochainement » : liste du code du site, pas du gabarit.
- Bande de chiffres : espaces réels seulement, masquée sous 5 écoles réelles. « Trouver mon école » : aucune recherche en base, code mal formé → même page avec l'erreur.
- Captures du produit refaites par une commande (`make captures-site`), WebP en deux largeurs ; aucun débordement à 390, 820 et 1440 px (`make apercu`, partie « site »).

**Tests obligatoires** : chaque page répond dans les deux langues avec ses liens `hreflang` ; chiffres de la plateforme sans essai ni démonstration et masqués sous 5 écoles ; « Trouver mon école » ne mène qu'à une adresse d'école.

**Documents** : `05` (WEB.1b cochée, WEB.1d ajoutée), `06`, `03` (journal), `reference.md`, `A-FAIRE.md` (§ 11 ; accord écrit de l'ITIG pour ses photos avant `make deploy`), `CLAUDE.md` (commande, adresses), `maquettes/README.md` (écarts), `07` § 1.

**Regard senior** : textes de mentions et confidentialité dans les gabarits traduits, pas dans un champ de la console (deux langues, mise en forme, relecture d'un juriste : un champ texte demanderait Markdown, donc une dépendance) ; `legal_notice` de la console, s'il est rempli, s'affiche comme identifiants de l'éditeur. Adresse postale : texte du site jusqu'à WEB.1d, qui l'ajoute à l'identité avec l'écran console.

**Risques** : poids des captures (budget 150 Ko pour le premier écran) ; photos de l'ITIG : accord écrit à avoir avant la mise en ligne ; textes juridiques à faire relire.
