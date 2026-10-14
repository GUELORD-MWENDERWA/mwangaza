# Refonte du design — recherche du 2026-10-14

Demande de l'utilisateur (2026-10-14, PR #247) : la palette « ressemble à l'IA », le portail ne s'adapte pas à l'ordinateur, des pages ont été faites sans maquette ; revoir tout le design d'après ce que font les grands logiciels, puis l'appliquer partout.

## Ce qui a été regardé

| Référence | Ce qu'on en retient |
|---|---|
| Linear, refonte de l'interface (2024) | Chrome neutre et « intemporel », peu de couleur dans les gris ; hiérarchie d'abord en niveaux de gris, puis la couleur ; contraste réglable ; titres plus expressifs que le texte courant. |
| Shopify Polaris (jetons de couleur) | Jetons **sémantiques** (`bg`, `bg-surface`, `text-secondary`, `border`) plutôt que des couleurs nommées dans les écrans : fond de page gris très clair, cartes blanches, texte secondaire pour les métadonnées. |
| Guides de palettes de tableaux de bord (60-30-10) | Contenu clair (60 %), barre latérale et navigation sombres (30 %, souvent un bleu nuit), accent réservé aux actions et à l'élément actif (10 %) ; couleurs d'état constantes, jamais en grandes surfaces ; texte de la barre sombre ≥ 7:1. |
| Material Design 3, classes de largeur | Compact < 600 px : barre de navigation en bas ; moyen 600–839 : rail ou tiroir ; étendu ≥ 840 : navigation latérale ou en haut. Une application « mobile d'abord » doit avoir une vraie mise en page étendue, pas une colonne de téléphone au milieu de l'écran. |
| Flutterwave (identité Verve), MFS Africa | Les fintechs africaines évitent le vert / bleu « froid et corporate » par défaut ; MFS Africa : **jaune vif + anthracite** (optimisme + sérieux). |
| Étude des marques universitaires (2020) | Le jaune est la couleur la plus fréquente, mais **jamais seule** : accent sur une base sombre ; bleu = compétence, jaune = énergie. |
| Stripe, bonnes pratiques d'encaissement sur mobile | Une colonne, cibles ≥ 44 px, actions principales en bas à portée du pouce, rien qui distrait pendant le paiement. |
| Guides de factures et reçus | Hiérarchie : total et date d'abord, puis identités et numéro, puis détail ; par la taille et la graisse, pas la couleur (lisible en noir et blanc) ; marges A4 ≥ 10 mm (les imprimantes coupent près du bord). |

## Décisions (appliquées le 2026-10-14)

- **Couleurs** : fini le beige et les gris chauds (« look IA »). Identité tirée du lac Kivu et du drapeau du Congo : **bleu Kivu** `#0B5FCC` (actions, liens, focus), **nuit du Kivu** `#0B1C35` (barre latérale, en-tête du portail, barre de la console, panneau des connexions), **lumière** `#F2B632` (logo, repère actif, points d'attention ; jamais en texte sur blanc). Neutres froids légèrement bleutés (fond `#F3F5F9`, bordures `#E2E8F0`, texte `#101828`). Contrastes vérifiés : texte tertiaire 5,25:1, bleu sur blanc 5,96:1, texte de la barre 14:1.
- **Signature** : motif de **lignes de relief** (volcans et collines du Kivu) en filigrane sur les surfaces nuit (connexions, en-tête du portail, barre latérale) : reconnaissable sans être criard.
- **Police** : **Atkinson Hyperlegible Next** (2025, licence OFL, mêmes principes de lisibilité, cinq graisses embarquées 400–800) : 600 pour les boutons, onglets et libellés, 700–800 pour les titres et les grands nombres.
- **Adaptation à l'écran** (pour chaque application) : téléphone < 600 px, tablette 600–1023, ordinateur ≥ 1024. Portail : en-tête avec navigation en haut et contenu sur deux colonnes à partir de 1024 px, barre du bas seulement au téléphone. Gestion : barre latérale dès 1024 px. Console : navigation en haut partout.
- **Impression** : noir et gris d'abord, une seule touche de bleu nuit pour les titres et filets ; total en gros ; marges ≥ 12 mm.

## Sources

- Linear — How we redesigned the Linear UI : https://linear.app/now/how-we-redesigned-the-linear-ui
- Shopify Polaris — Color tokens : https://polaris.shopify.com/design/colors/color-tokens
- sixtythirtyten — SaaS Dashboard Color Palette (60-30-10) : https://www.sixtythirtyten.co/blog/saas-dashboard-color-palette-css-tailwind
- AdminLTE — Best Admin Dashboard Color Schemes : https://adminlte.io/blog/best-admin-dashboard-color-schemes/
- Window size classes (compact / medium / expanded) : https://dev.to/tkuenneth/about-window-size-class-libraries-5c5m
- Flutterwave, nouvelle identité (Verve) : https://www.printmag.com/branding-identity-design/flutterwave/
- MFS Africa, nouvelle identité : https://onafriq.com/view/a-new-look-for-a-bolder-mfs-africa
- Progress — Color psychology for education web design : https://www.progress.com/blogs/using-color-psychology-education-web-design
- Stripe — Mobile checkout UI best practices : https://stripe.com/en-cn/resources/more/mobile-checkout-ui
- Invoice design guide : https://invoicequickly.com/guides/invoice-design-guide
- Atkinson Hyperlegible Next (Fontsource, OFL-1.1) : https://fontsource.org/fonts/atkinson-hyperlegible-next
