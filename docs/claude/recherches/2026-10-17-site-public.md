# Site public : ce que font les grands sites, ce qu'on fait mieux (WEB.1a, 2026-10-17)

But : avant de dessiner le site de la plateforme (`maquettes/site/`), voir comment les meilleurs sites présentent un logiciel, et ce qu'un parent ou un directeur de Goma paie en données pour les voir.

## Méthode

- **Structure** : page d'accueil de chaque site lue le 2026-10-17 (version française quand elle existe).
- **Poids** : premier écran mesuré avec Chrome sans interface, à 390 px, cache vide, 9 s sans faire défiler. C'est ce que paie un téléphone avant de voir quelque chose. Script jetable, pas gardé. PageSpeed Insights a refusé (quota sans clé). Les sites qui bloquent les robots ne sont **pas mesurés** : aucun chiffre n'est deviné.

## Les sites

| Site | Type | Structure | Ce qui convainc | Animations | 1er écran |
|---|---|---|---|---|---|
| [Stripe](https://stripe.com/fr) | SaaS | héros + logos clients ; produits en cartes ; chiffres (135+ devises, 99,999 % de disponibilité) ; études de cas chiffrées ; développeurs ; actualités ; pied en 6 colonnes avec la langue | des chiffres vérifiables, le produit montré | dégradé animé en tête, cartes au survol | 409 Ko, 37 requêtes |
| [Linear](https://linear.app) | SaaS | héros + 4 boutons ; trois promesses ; 4 blocs texte + capture qui alternent, légendés « Fig. » ; nouveautés datées ; 3 citations nommées ; appel final | le produit au centre, de vraies captures légendées, la sobriété | micro-animations dans les captures | 806 Ko, dont 345 Ko de polices |
| [Notion](https://www.notion.com/fr) | SaaS | menu par public (« Notion pour » entreprises, PME…) ; captures empilées ; logos ; 3 blocs (enregistrer, trouver, automatiser) ; cas d'usage ; citations ; chiffres | une section par besoin, deux boutons (gratuit, démo) | discrètes | 740 Ko, 54 requêtes |
| [PowerSchool](https://www.powerschool.com) | scolaire, É.-U. | menu par public (familles, classes, administration) ; un chiffre dans le héros (60 M d'élèves, 90 pays) ; logos de districts ; témoignages avec photo ; vidéo | publics séparés, preuves | animation « Connected OS » | 524 Ko, dont 273 Ko de JS |
| [Toddle](https://www.toddleapp.com) | scolaire, international | « Get a demo » seul bouton ; mur de 2 500 écoles ; **lettre du fondateur** ; 9 modules, chacun avec sa capture ; chiffres ; sécurité ; « Ready to see Toddle in action? » | une voix humaine, un module = une capture, une seule action | non vu | non mesuré (page vide pour un robot) |
| [Fedena](https://www.fedena.com) | scolaire, Inde | héros + chiffres (40 000 établissements) ; essai gratuit, prix ; 6 modules + « 50+ » ; application mobile ; témoignages ; **questions fréquentes** | la FAQ, les prix visibles | — | non mesuré |
| [Classe365](https://www.classe365.com) | scolaire | héros « avec l'IA » ; solutions ; prix et récompenses ; ressources | — | 18 | 246 Ko, page de 14 500 px au téléphone |
| [Pronote](https://www.index-education.com/fr/logiciel-gestion-vie-scolaire.php) | scolaire, France | « le lien direct et sécurisé entre l'école et les familles » ; **démos par public** (enseignants, élèves, parents, vie scolaire) en version téléphone et ordinateur ; aide | essayer sans s'inscrire, par public | aucune | non mesuré (refusé) |
| [Zeraki](https://www.zeraki.app) | scolaire, Kenya | produits séparés : Analytics (notes, bulletins, parents), Finance (frais), Timetables ; 4 000+ écoles ([Acumen](https://acumen.org/companies/zeraki-analytics/)) | un produit par besoin, à l'échelle africaine | — | inaccessible depuis notre machine |
| [Edves](https://edves.net) | scolaire, Nigeria | redirection par pays ; parents qui paient les frais par carte ou banque, reçu automatique ([TechCabal](https://techcabal.com/?p=87886), [Dealroom](https://app.dealroom.co/companies/edves)) | le paiement en ligne des frais | — | page de redirection seulement |
| [Wave](https://www.wave.com/fr/) | service africain | « Votre allié mobile money » + 3 promesses chiffrées (gratuit, 1 %) ; 6 points ; 2 témoignages avec prénom et photo ; boutons des magasins | **phrases courtes, mots simples, prix en clair**, français et anglais | aucune | **51 Ko, 7 requêtes** |
| [M-Pesa](https://www.safaricom.co.ke/main-mpesa) | service africain | refuse la lecture automatique (403) | — | — | 630 Ko, dont 402 Ko de JS |
| [mwangazaschool.com](https://mwangazaschool.com/) | notre site (2026-10-14) | une page : héros, fonctions, rôles, « conçu pour les écoles telles qu'elles sont », FAQ, contact | — | aucune | 41 Ko, 5 requêtes |

**En RDC** (presse, sites non lus) : Shule System, 144 écoles annoncées ([We Are Tech](https://www.wearetech.africa/fr/fils/tech-stars/mannick-syllas-bryant-numerise-la-gestion-et-la-vie-scolaire-en-rdc)) ; E-School B, paiements fractionnés, mobile money, faible connexion ([VC4A](https://vc4a.com/ventures/e-school-b-sas/?lang=fr)) ; Futuriss, démo sur demande ([Actualite.cd](https://actualite.cd/index.php/2024/08/27/futuriss-la-revolution-de-la-gestion-academique-en-republique-democratique-du-congo-et)). Aucun ne met en avant la vitesse sur une connexion lente ni les deux devises.

## Ce qu'on reprend

- **Une action principale partout** : « Demander une démonstration » (Toddle, Notion) ; deux accès secondaires toujours visibles : « Trouver mon école » et « Espace parents ». Pas d'inscription en ligne : on ouvre nous-mêmes un espace d'essai.
- **Un menu par public** : Écoles, Parents (PowerSchool, Notion, Pronote).
- **Le produit au centre** : de vraies captures légendées (Linear), une par rôle (Toddle).
- **Des faits, pas des adjectifs** (Stripe) ; témoignages nommés **seulement** quand une vraie école l'accepte (Wave, Linear).
- **Phrases courtes, prix en clair** (Wave) ; questions fréquentes (Fedena) ; pied de page complet (Stripe, Notion).

## Ce qu'on fait mieux

1. **Vitesse** : premier écran ≤ 150 Ko (Wave 51 ; Stripe 409, Notion 740, Linear 806). Deux graisses de police préchargées, captures WebP en chargement différé sous le premier écran, ≤ 5 Ko de JavaScript, pages en cache, lisibles sans JavaScript.
2. **Le pays dès le premier écran** : dollars et francs, sans internet, reçu thermique 58 / 80 mm, Mobile Money annoncé honnêtement « prochainement ».
3. **Français et anglais complets** (Pronote : français seul ; Toddle, Zeraki : anglais seul).
4. **Les parents comme un vrai public** : une page à eux, activation en 3 étapes, installation sur le téléphone sans magasin d'applications.
5. **« Trouver mon école »** : on tape le code et on arrive sur sa Gestion. Les sites étudiés n'ont qu'un « Login » générique.
6. **Démonstration avec les classes et les frais de l'école** (espace d'essai, 4.15).
7. **Rien d'inventé** : ni logos de clients, ni chiffres, ni témoignages tant qu'ils n'existent pas.

## Ce qu'on ne reprend pas

Dégradés animés ou violets (Stripe), vidéo en lecture automatique (PowerSchool), murs de logos (aucun client connu, jamais de faux), « IA » dans le titre (Classe365, Toddle), pages de 14 000 px au téléphone, bandeau de cookies (seuls des cookies nécessaires).

## Décisions pour les maquettes (`maquettes/site/`)

- **Pages** : accueil, écoles (une page, une section par rôle : quatre pages presque vides se classeraient mal), parents, modules, démonstration et contact, « Trouver mon école », mentions et confidentialité (un gabarit, deux adresses).
- **Titres du site** : de 2 rem (téléphone) à 3,4 rem (ordinateur), seulement sur le site public ; le reste suit l'échelle de l'application.
- **Animations** (chacune décrite dans la maquette avec son rôle, coupées par `prefers-reduced-motion`) : captures qui s'enchaînent dans le héros (montrer le produit), pastille de synchronisation qui passe de « hors ligne » à « à jour » (expliquer le hors-ligne sans texte), sections qui apparaissent au défilement et frise de la journée qui s'allume (guider l'œil), chiffres qui montent (attirer l'œil sur un fait), cartes qui se soulèvent au survol (montrer qu'on peut cliquer), adresse qui se forme dans « Trouver mon école » (rassurer).
- **Images** : captures du produit (WEB.1b : `make apercu` sur les données de démonstration, en WebP) ; photos libres de droits (Wikimedia Commons, crédit dans les mentions) ou fournies par l'utilisateur, sans visage d'élève reconnaissable sans accord écrit ; aucune illustration générée.
- **Confidentialité** : texte proposé d'après le Code du numérique de la RDC (ordonnance-loi n° 23/010 du 13 mars 2023 ; droits d'information, de rectification, d'effacement, d'opposition — [Droit-Numérique.cd](https://droitnumerique.cd/), [Kodjo Ndukuma](https://kodjondukuma.com/assets/docs/tribunes/DroitDonnees.pdf)) ; l'Autorité de protection des données n'était pas encore en place en mai 2026. **À faire relire par un juriste** avant la mise en ligne.
