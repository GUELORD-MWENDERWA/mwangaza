---
name: design
description: Système de design Mwangaza (refonte du 2026-10-14 — bleu Kivu, nuit, lumière, Atkinson Hyperlegible Next, lignes de relief) — logo M-flamme, jetons de couleur, échelle de texte, thème Tailwind / shadcn, correspondance entre les classes des maquettes et les composants, adaptation à chaque taille d'écran (téléphone, tablette, ordinateur), graphiques, impression, formats des montants et des dates, accessibilité. À utiliser pour tout travail d'interface — thème, composant partagé, écran, impression — dans frontend/apps/gestion, frontend/apps/portail, frontend/apps/console ou frontend/packages/ui.
---

# Système de design Mwangaza

Sources de vérité, dans cet ordre : `maquettes/assets/styles.css` (bloc `:root`), `maquettes/README.md` § « Système de design », les captures `maquettes/captures/` (bureau 1440 px et téléphone 390 px, pour **les trois** applications). Recherche et raisons : `docs/claude/recherches/2026-10-14-refonte-design.md`. Ne pas inventer de couleur, de rayon ni de taille : les reprendre de ces fichiers ; un besoin non couvert → un jeton du thème, noté au « Journal des décisions » de `03`.

## Méthode (demande de l'utilisateur du 2026-10-14)

1. **Références d'abord** : avant de dessiner un écran nouveau (ou une page publique), regarder comment les grands logiciels font (Stripe, Linear, Shopify Polaris, GitHub, logiciels scolaires ; sites marketing actuels pour une page publique) et noter les sources dans `docs/claude/recherches/`.
2. **Maquette ensuite**, à 390 px **et** 1440 px (et l'état tablette dans la feuille de style), dans `maquettes/` — jamais une page codée sans maquette.
3. **Code**, puis `make apercu` (ou `ecran=…`) : regarder l'écran réel à 390, 820 et 1440 px, `rapport.json` vide.
4. Pages publiques (site de la plateforme WEB.1, sites des écoles) — maquettes : `maquettes/site/` + `assets/site.css` (WEB.1a : titres de 2 à 3,4 rem, seul ajout à l'échelle ; premier écran ≤ 150 Ko ; photos d'une vraie école ou libres, crédits dans `assets/photos/README.md`) : vrai design marketing aux normes actuelles — photos (écoles, intérieurs), animations sobres (`prefers-reduced-motion` respecté), pied de page complet (liens, contact, langues, mentions, « © DTMS. Tous droits réservés. »), l'auteur seulement en `<meta name="author">`. Code du site (WEB.1b) : gabarits Django `backend/apps/core/templates/core/site/` (un `base.html` commun), feuille `backend/apps/core/static/core/site/site.css` (tirée de `assets/site.css` : un changement de l'une se reporte dans l'autre), script `site.js` (animations, ≤ 5 Ko), balises `{% icon %}`, `{% capture %}` et `{% photo %}` (`core/templatetags/site_tags.py`) ; captures du produit refaites par `make captures-site`, pages vérifiées par `make apercu ecran=site`. **Seulement ce qui sert au visiteur** (règle de l'utilisateur, 2026-10-18) : jamais la technique (hébergeur, prestataires, logiciels, architecture), ni l'origine des photos, ni les accords avec une école, ni l'histoire du projet ; photos sans légende ; seule exception, le crédit qu'exige une licence (CC BY-SA) : une ligne dans les mentions légales.

## Intention

- **Nuit du Kivu** (bleu nuit) : barre latérale de la Gestion, en-tête et barre du haut du Portail, barre de la console, panneau des connexions — avec le motif de **lignes de relief** (volcans et collines du Kivu, `relief.svg`, classe `relief`) en filigrane.
- **Lumière** (jaune, *mwangaza*) : logo, repère de l'élément actif (barre de 4 px, icône active, soulignement de la barre du portail et de la console), compteurs, points d'attention. **Jamais en texte sur fond clair, jamais en grande surface, jamais comme couleur de série d'un graphique** (trop claire : 1,8:1).
- **Bleu Kivu** (lac et drapeau du Congo) : toutes les actions principales, liens, focus, onglet actif.
- Neutres **froids**, légèrement bleutés : jamais de beige, de crème ni de gris chauds (« look IA » refusé par l'utilisateur).
- Utilisateurs peu habitués à l'informatique, écrans de faible qualité : gros boutons, formulaires courts, texte lisible, contrastes ≥ 4,5:1.

## Jetons

`lake` et `lamp` (et leurs teintes) sont les valeurs de départ : les couleurs de la plateforme (`PlatformSettings`, défaut `#0B5FCC` / `#F2B632`, contraste vérifié par le serveur, l'accent contre la nuit `#0B1C35`) les remplacent à l'exécution (`applyPlatform`). Toujours passer par les jetons.

| Jeton | Valeur | Usage |
|---|---|---|
| `night` / `night-2` / `night-3` | `#0B1C35` / `#15294B` / `#213A63` | barres sombres / élément actif, encadré de l'école / bordures sur la nuit |
| `night-ink` / `night-soft` / `night-muted` | `#E6ECF5` / `#C3CFE0` / `#94A3BB` | texte sur la nuit (14:1) / entrées du menu, sous-titres / libellés de section |
| `lamp` / `lamp-soft` | `#F2B632` / `#FEF5DA` | lumière (voir Intention) / bandeau de marque, étiquette V1.x |
| `lake` / `lake-700` / `lake-100` / `lake-50` | `#0B5FCC` / `#08459A` / `#D4E3F9` / `#EAF1FC` | `primary` (5,96:1 sur blanc) / survol, texte sur `lake-50` / anneau de focus, sélection / ligne choisie, fond d'avatar |
| `ink` / `ink-2` / `ink-3` | `#101828` / `#475467` / `#5B677A` | texte / secondaire / tertiaire (≥ 5:1 sur `surface`) |
| `surface` / `card` / `table-head` | `#F3F5F9` / `#FFFFFF` / `#F7F9FC` | fond de page / cartes / en-tête et pied de tableau, pied de carte |
| `line` / `line-soft` / `gray-50` | `#E2E8F0` / `#EDF1F6` / `#EDF1F6` | bordures / séparateurs / fond neutre (piste du `Segmented`, étiquette) |
| `field` | `#7A8699` | bordure de champ, case (3,7:1 sur blanc) |
| `ok` / `due` / `warn` / `info` (+ `-50`, `-200`, `-900`) | `#127A48` / `#B42318` / `#985A06` / `#0B5FCC` | états, **toujours avec un texte** |
| `chart-1` / `chart-2` / `chart-grid` | `lake` / `#C47F00` / `#E2E8F0` | séries de graphique (validées par la skill `dataviz`) / grille |
| `--color-course-1` … `-10` | `lake`, `#7C3AED`, `#B45309`, `#DB2777`, `#16A34A`, `#0891B2`, `#EA580C`, `#CA8A04`, `#0F766E`, `#64748B` | couleur d'un cours dans l'emploi du temps (filet gauche de la carte, `colorOf(nom)`), dans `:root` hors `@theme` car lue par `style` |
| `scrim` | nuit à 55 % | voile sous un tiroir ou une fenêtre |

Rayons : cartes 14 px (`rounded-card`), fenêtres 16 px (`rounded-dialog`), champs et boutons 8 px, encadrés 10 px, pastilles 999 px. Ombres froides : `shadow-button` (boutons, champs), `shadow-card` (cartes : la bordure dessine, l'ombre décolle à peine), `shadow-raised` (survol, choix actif), `shadow-float` (fenêtres, tiroir, bulles). `apps/gestion/design.test.ts` refuse les couleurs et les tailles écrites en dur.

### Correspondance shadcn/ui

`--background` = surface · `--foreground` = ink · `--card` = card · `--border` = line · `--input` = field · `--primary` = lake · `--ring` = lake · `--accent` = lake-50 · `--accent-foreground` = lake-700 · `--muted-foreground` = ink-3 · `--destructive` = due · `--sidebar` = night · `--sidebar-foreground` = night-ink · `--sidebar-accent` = night-2 · `--sidebar-primary` = lamp. Le thème vit dans `frontend/packages/ui/src/styles.css`, partagé par les trois applications.

## Logo : le symbole M-flamme

Un M **bleu nuit** épais surmonté d'une flamme, dans un carré arrondi `lamp`. Forme pleine et fermée, lisible de 16 à 512 px. Fichiers : `maquettes/assets/logo/` (`symbole.svg`, `icone-application.svg`, `icone-maskable.svg`, `icone-apple.svg`) ; icônes des applications (`apps/*/public/icons/`, `backend/apps/core/static/core/site/`) rendues depuis ces SVG avec Chrome sans interface, à la taille exacte (M passé du basalte au bleu nuit le 2026-10-14).
- `BrandMark` / `PlatformMark` / `Brand` (`@mwangaza/ui`) : ne jamais redessiner le symbole ailleurs (seule copie : la page de vérification des reçus, servie par Django).
- Tailles : 36 px dans les barres, 48 px sur les connexions ; jamais sous 16 px ; zone de protection = un quart de sa largeur ; jamais déformé.

## Typographie

- **Atkinson Hyperlegible Next** (2025, OFL), embarquée (hors-ligne) : `fonts/atkinson-hyperlegible-next-latin-{400,600,700,800}-normal.woff2` dans `packages/ui`, les maquettes et `backend/apps/core/static/core/site/` ; repli `system-ui`. Les PDF l'intègrent aussi (`core/documents.py:print_fonts`).
- Graisses : 400 texte · **600** (`font-semibold`) boutons, onglets, libellés, entrées de menu · 700 titres · **800** (`font-extrabold`) grands nombres (KPI, montant en caisse).
- Base 15 px, interligne 1,45 ; titres `tracking-tight`. **Échelle, la seule autorisée** : `text-xs` .8 rem (12 px, rien en dessous) · `text-sm` .85 · `text-md` .92 · `text-base` 1 · `text-lg` 1,15 · `text-xl` 1,3 · `text-2xl` 1,6 · `text-3xl` 2. Impression : tailles en pt.
- **Chiffres** : `tabular-nums`, alignés à droite dans les tableaux, sans retour à la ligne (`num`).

## Composants (maquette → application)

Dans `frontend/packages/ui` (exportés par `@mwangaza/ui`), construits une fois, réutilisés partout : `Button`, `Input`, `PasswordInput`, `Textarea`, `Field`, `Checkbox` / `CheckboxField`, `Segmented`, `CodeInput`, `Card…`, `List`, `Banner`, `StatusPill`, `Tag`, `Steps`, `Code` / `CodeList`, `Sheet…`, `DialogRoot` / `DialogContent`, `DropdownMenu…`, `Avatar`, `Brand` / `PlatformMark` / `BrandMark`, `SchoolBadge`, `SyncIndicator`, `PageHeader`, `StateCard`, `Toast`, `Skeleton`, `Icon`, `Tabs…`, `Switch`, `Select`, `Table`, `ConfirmDialog`, `Kpi`, `WeekSchedule` / `toSchedule` (horaire publié en lecture : un jour à la fois, la semaine en colonnes avec `columns`, EDT.4b), `usePlatform()`, `LegalNotice`, `useMediaQuery` / `DESKTOP`.

| Maquette | Composant | Notes |
|---|---|---|
| `.card` `.hd` `.bd` `.ft` | `Card` / `CardHeader` / `CardContent` / `CardFooter` | en-tête séparé par `line-soft` ; pied sur `table-head` |
| `.kpi` (`.lbl` `.val` `.sub` `.chip`) | `Kpi` (`icon`, `chip`, `tone`, enfants : barre) | valeur `text-2xl` extra-grasse ; icône dans une pastille teintée en haut à droite |
| `.btn` `.primary` `.danger` `.dangerf` `.ghost` · `.sm` `.lg` `.xl` | `Button` `default`, `outline`, `destructive-outline`, `destructive`, `ghost` ; `sm` 32, `default` 40, `lg` 48, `xl` 60 px pleine largeur (caisse) | graisse 600, ombre légère, anneau de focus `lake-100` 4 px |
| `.inp` `.inp.big` `.focus` `.err` | `Input`, `AmountInput` | ≥ 40 px ; focus : bordure lac + anneau `lake-100` |
| `label.f` `.req` `.help` `.errtxt` | `Field` + react-hook-form + zod | erreur du serveur : `applyServerErrors` |
| `.seg` | `Segmented` | piste grise, choix actif en carte blanche (`shadow-raised`) |
| `.tbl` `tr.sel` `.errrow` `.warnrow` `tfoot` | `Table` ; `Table stacked` + `data-label` ; `Table freeze` (tableau à remplir : titres et 1re colonne figés, défilement dans la carte, NB.7) | en-tête `table-head` en `ink-3` ; survol de ligne ; **`stacked`** : au téléphone (< 600 px) une carte par ligne — pour les grandes listes consultées au téléphone (élèves, impayés ; maquettes : `.tbl.stack`) ; case à cocher : `td.stack-check` |
| `.pill` | `StatusPill` | point + texte, anneau intérieur `-200` |
| `.banner` | `Banner` | icône à gauche sur la 1re ligne, action à droite (au téléphone : sous le texte, aligné avec lui) |
| `.tabs` | `Tabs` | actif : texte lac, soulignement 2 px |
| `.side` `.nav a.on` `.navlabel` | coquille `AppShell` de la Gestion | 256 px, nuit + relief ; libellés de section en capitales `night-muted` ; entrée active : `night-2`, texte blanc, icône `lamp`, barre `lamp` |
| `.top` | barre du haut de la Gestion | 64 px, blanche translucide, recherche `Ctrl K`, `SyncIndicator` toujours visible |
| `.dtop` `.ptop` `.pbody` `.pgrid` `.pcards` `.pnav` | coquille du Portail (`PortalFrame`) | voir « Adaptation » ; `wide` : accueil et enfant sur deux colonnes |
| `.phone.pauth` / `.authgrid` | connexions du Portail / de la Gestion | panneau nuit + relief à gauche, formulaire à droite (≥ 1024 / 900 px) |
| `.ctop` `.cmain` | coquille de la console | barre nuit + relief, navigation dessous (repère lampe) |
| `.overlay` `.dialog` | `DialogRoot` + `DialogContent` | 16 px, `shadow-float`, pied sur `table-head` |
| `.drawer` `.scrim` | `Sheet` | menu tiroir nuit + relief |
| `.thermal` `.a4` `.a4.land` `.bul` | gabarits d'impression | voir « Impression » |
| `.note` | **rien** | règle métier, jamais affichée |

## Adaptation à chaque écran

Trois largeurs pour **chaque** application (Material 3 : compact / moyen / étendu) — le Portail n'est pas « que téléphone », la caisse et la console ne sont pas « que ordinateur » :

| | Téléphone < 600 px | Tablette 600–1023 px | Ordinateur ≥ 1024 px |
|---|---|---|---|
| Gestion | menu tiroir, une colonne, `Table stacked` pour les grandes listes, filtres repliés derrière « Filtres (n) », actions d'en-tête en deux colonnes | menu tiroir (barre latérale dès 900 px), grilles 2 colonnes | barre latérale, grilles `minmax(0, …)`, contenu jusqu'à 1 400 px |
| Portail | barre du bas, colonne de 640 px | colonne de 760 px, enfants deux par rangée | **barre du haut** (marque, navigation, cloche, déconnexion) à la place de la barre du bas, en-tête = titre de la page, contenu 1 120 px sur deux colonnes (accueil, enfant) ou 760 px pour lire ; connexions en deux panneaux |
| Console | navigation qui défile, cartes en 2 colonnes | | contenu 1 240 px |

- Un élément qui change entre téléphone et ordinateur (barre du portail) : `useMediaQuery(DESKTOP)` plutôt que deux copies cachées par CSS (les tests ne voient qu'une copie).
- Grilles : toujours `minmax(0, …)` ; un tableau large défile dans sa carte, jamais la page.
- Vérification : `make apercu` (390, 820, 1440 px, `rapport.json` vide) **et** regarder les captures (alignements, pas seulement débordements).

## Graphiques

Skill `dataviz` : séries `chart-1` (lac) puis `chart-2` (ambre), validées (daltonisme, luminosité, contraste ≥ 3:1) ; grille discrète `chart-grid` ; barres fines arrondies (4 px) posées sur la ligne de base, 2 px entre elles ; infobulle au survol ; tableau `sr-only` des valeurs ; légende neutre (point de couleur + texte, jamais `StatusPill` ni couleur d'état pour une série) ; jamais deux axes.

## Impression

**En-tête commun** (`core/_document_header.html`, exemplaire fourni le 2026-10-15) : logo de l'école à gauche, drapeau à droite, lignes centrées (République, ministère, école, adresse, service), filet épais, titre souligné avec N° de référence à compléter ; maquette `gestion/impression-options.html`. Panneau « Imprimer » (papier, sens, exemplaires) : `features/printing`. Aucun ajout sans maquette, regardé à 390 et 1440 px. Tableau très large (fiches de cotes, 8.3.6) : pas de texte vertical (`writing-mode` n'est pas fiable dans WeasyPrint), colonnes numérotées avec une légende dessous.

`core/print_base.html` (documents du serveur, WeasyPrint) : noir et gris d'abord (lisible photocopié), titres et filet sous l'en-tête de l'école en bleu nuit, police de la marque intégrée, tableaux à filets gris clair, marges ≥ 10 mm ; un gabarit qui a ses propres styles n'utilise que les gris de la palette (`#101828`, `#475467`, `#5B677A`, `#A9B4C4`, `#CBD5E1`, `#EDF1F6`), jamais de noir pur ni de gris chaud. Vérifier : `make apercu ecran=documents` (chaque document dans `frontend/apercu/captures/documents/`). Guides PDF (`frontend/guide/`, `make guide`) : jetons de la refonte dans `guide.css`, texte et captures mis à jour quand l'apparence ou les écrans changent. Reçus de caisse (`features/cash/receipt.css`) : noir et blanc, réglés au millimètre pour le ticket 58 / 80 mm et les feuilles A4 (A6, A5, petit format) — ne pas y ajouter de couleur.

## Formats d'affichage

Une seule fois (`frontend/packages/money`, `frontend/packages/i18n`) : USD `1 234,56 $` ; FC `1 260 000 FC` ; deux devises `20,00 $ + 30 000 FC` (jamais additionnées) ; dates `19/10/2026`, heures `10:42`, fuseau de l'école ; élève `NOM POST-NOM` + prénom.

## Accessibilité

Focus visible (bordure lac + anneau `lake-100`) ; erreur : bordure `due` + anneau `due-50` ; contrastes vérifiés (texte ≥ 4,5:1, bordure de champ ≥ 3:1) ; couleur d'état toujours avec un texte ; `prefers-reduced-motion` coupe les animations ; cibles ≥ 44 px au téléphone.
