---
name: design
description: Système de design Mwangaza (basalte, lampe, lac Kivu, Atkinson Hyperlegible) — logo lampe-tempête, jetons de couleur, échelle de texte, thème Tailwind / shadcn, correspondance entre les classes des maquettes et les composants, formats des montants et des dates, règles d'accessibilité et de mise en page. À utiliser pour tout travail d'interface — thème, composant partagé, écran, impression — dans frontend/apps/gestion, frontend/apps/portail ou frontend/packages/ui.
---

# Système de design Mwangaza

Sources de vérité, dans cet ordre : `maquettes/assets/styles.css` (bloc `:root`), `maquettes/README.md` § « Système de design », les captures `maquettes/captures/`. Ne pas inventer de couleur, de rayon ni de taille : les reprendre de ces fichiers. Si un besoin n'y est pas couvert, proposer une valeur cohérente et la noter (`/noter`).

## Intention

- **Basalte** (pierre volcanique de Goma) : barre latérale de la Gestion, en-tête du Portail, barre du haut de la console (pastille « Console » en lampe).
- **Lampe** (jaune, *mwangaza* = lumière) : repère de l'élément actif, logo, points d'attention. **Jamais en fond de page ni de grande surface.**
- **Lac** (bleu-vert du lac Kivu) : toutes les actions principales, liens, focus.
- Utilisateurs peu habitués à l'informatique, écrans de faible qualité : gros boutons, formulaires courts, texte lisible.

## Jetons

Les valeurs de `lake` et `lamp` (et leurs teintes `lake-700`, `lake-50`, `lamp-soft`, `info`) sont celles de départ : depuis la 5.1, les couleurs de la plateforme (`PlatformSettings`, contraste vérifié par le serveur) les remplacent à l'exécution (`applyPlatform` de `@mwangaza/ui`, teintes en `color-mix`). Toujours passer par ces jetons, jamais leur valeur en dur.

| Jeton | Valeur | Usage |
|---|---|---|
| `basalt` | `#2B2724` | barre latérale, en-tête portail |
| `basalt-2` | `#3A3531` | élément actif / encart école sur basalte |
| `basalt-ink` | `#EDE8E3` | texte sur basalte |
| `lamp` | `#F2B632` | repère actif (barre 4 px à gauche), logo, compteur |
| `lamp-soft` | `#FDF3D8` | bandeau d'information de marque (`lampb`), étiquette V1.x |
| `lake` | `#0E5C6B` | `primary` : bouton principal, lien, focus, onglet actif |
| `lake-700` | `#0A4652` | survol / texte sur `lake-50` |
| `lake-50` | `#E6F0F2` | ligne sélectionnée, anneau de focus, fond avatar |
| `ink` / `ink-2` / `ink-3` | `#211D1A` / `#554D46` / `#6E655D` | texte / secondaire / tertiaire (≥ 4,5:1 sur `surface`) |
| `surface` | `#F4F2EF` | fond de page |
| `card` | `#FFFFFF` | cartes |
| `line` / `line-soft` | `#E2DCD5` / `#EDE9E4` | bordures / séparateurs de lignes |
| `field` | `#958A80` | bordure de champ, case à cocher (≥ 3:1 sur blanc) |
| `table-head` | `#F8F6F3` | en-tête et pied de tableau |
| `scrim` | basalte à 50 % | voile sous un tiroir ou une fenêtre |
| `ok` / `ok-50` | `#1F7A4D` / `#E5F3EB` | payé, soldé, à jour, en ligne, succès |
| `due` / `due-50` | `#B42318` / `#FBE9E7` | en retard, erreur, danger, annulé |
| `warn` / `warn-50` | `#9A5B00` / `#FFF1D6` | partiel, hors-ligne, avertissement |
| `info` / `info-50` | `#0E5C6B` / `#E6F0F2` | information |
| `*-200` / `*-900` (`ok`, `due`, `warn`, `info`, `lamp`) | voir `packages/ui/src/styles.css` | bordure / texte d'un `Banner`, bordure du bouton « danger » |

**Neutres tirés du basalte** (2026-10-14) : gris chauds de la pierre de Goma, jamais les gris bleutés par défaut de Tailwind ou shadcn (`slate`, `gray`, `#1A2233`…). Une couleur qui manque devient un jeton du thème, jamais une valeur `-[#…]` dans une classe : `apps/gestion/design.test.ts` refuse les couleurs et les tailles écrites en dur.

Rayons : cartes 12 px, champs et boutons 8 px, pastilles 999 px. Ombre des cartes : `0 1px 2px rgba(26,34,51,.06), 0 4px 12px rgba(26,34,51,.05)`.

### Correspondance shadcn/ui

`--background` = surface · `--foreground` = ink · `--card` = card · `--border` = line · `--input` = field · `--primary` = lake · `--primary-foreground` = blanc · `--ring` = lake · `--accent` = lake-50 · `--accent-foreground` = lake-700 · `--muted-foreground` = ink-3 · `--destructive` = due · `--radius` = 8px (cartes : 12px) · `--sidebar` = basalt · `--sidebar-foreground` = basalt-ink · `--sidebar-accent` = basalt-2 · `--sidebar-primary` = lamp.
Ajouter `ok`, `due`, `warn`, `info` (et leurs `-50`), `lamp`, `lamp-soft`, `basalt*`, `ink-2`, `ink-3` comme couleurs du thème Tailwind. Le thème vit dans `frontend/packages/ui` et est partagé par les deux applications.

## Logo : la lampe-tempête

La lampe sous laquelle les élèves étudient le soir (*mwangaza* = la lumière) ; même nom que le jeton `lamp`. Fichiers : `maquettes/assets/logo/` (`lampe-sur-sombre.svg`, `lampe-sur-clair.svg`, `icone-application.svg`, `icone-maskable.svg`) ; icônes PNG des applications (`apps/*/public/icons/`) rendues depuis ces SVG.
- Composant `BrandMark` (`@mwangaza/ui`) : le cadre prend la couleur du texte autour (clair sur basalte, sombre sur fond clair), le verre suit `lamp` (donc l'accent de la plateforme). Ne jamais redessiner la lampe ailleurs : utiliser `Brand` / `PlatformMark` / `BrandMark`.
- Un logo de plateforme téléversé (`PlatformSettings`) remplace la lampe ; la lampe reste le défaut.
- Taille mini 16 px (favicon) ; zone de protection = un quart de sa largeur ; jamais déformée, jamais sur une photo.

## Typographie

- **Atkinson Hyperlegible** 400 et 700, fichiers `maquettes/assets/fonts/*.woff2` **embarqués dans l'application** (pas de Google Fonts : hors-ligne), `font-display: swap`, repli `system-ui, sans-serif`.
- Base 15 px, interligne 1,45. `h1` 1,6 rem, `h2` 1,15 rem, `h3` 1 rem.
- **Échelle, la seule autorisée** : `text-xs` .8 rem (12 px, étiquettes ; rien en dessous) · `text-sm` .85 · `text-md` .92 (menu, tableaux denses) · `text-base` 1 · `text-lg` 1,15 · `text-xl` 1,3 · `text-2xl` 1,6 · `text-3xl` 2. Jamais `text-[…rem]` (refusé par `design.test.ts`) ; dans les maquettes, `font-size` en rem prend une de ces valeurs. Les gabarits d'impression (reçu thermique, A4, bulletin) gardent leurs tailles en pt / px.
- **Chiffres** : toujours `tabular-nums`, alignés à droite dans les tableaux, sans retour à la ligne (classe utilitaire `num`).

## Composants (maquette → application)

Les composants partagés vont dans `frontend/packages/ui` (exportés par `@mwangaza/ui`). Les construire une fois, les réutiliser partout. **Déjà construits (1.6)** : `Button`, `Input`, `PasswordInput`, `Textarea`, `Field`, `Checkbox` / `CheckboxField`, `Segmented`, `CodeInput`, `Card…`, `List`, `Banner`, `StatusPill`, `Tag`, `Steps`, `Code` / `CodeList`, `Sheet…`, `DialogRoot` / `DialogContent`, `DropdownMenu…`, `Avatar`, `Brand` (logo de la plateforme ou lampe, et son nom) / `PlatformMark` / `BrandMark` (lampe seule), `SchoolBadge`, `SyncIndicator`, `PageHeader`, `StateCard`, `Toast`, `Skeleton`, `Icon` (icônes des maquettes) ; **1.7** : `Tabs` / `TabsList` / `TabsTrigger` / `TabsContent`, `Switch`, `Select` (liste native stylée), `Table`, `ConfirmDialog` ; **5.1** : `usePlatform()` (identité de la plateforme : nom, logo, icône, couleurs, support, mentions légales), `LegalNotice` (lien et fenêtre des mentions légales) ; les autres noms du tableau sont à créer avec leur premier écran.

| Maquette | Composant | Notes |
|---|---|---|
| `.card` `.hd` `.bd` `.ft` | `Card` / `CardHeader` / `CardContent` / `CardFooter` | |
| `.kpi` (`.lbl` `.val` `.sub` `.up` `.down`) | `Kpi` | valeur `text-2xl` (1,6 rem) gras, tabulaire |
| `.btn` `.primary` `.danger` `.dangerf` `.ghost` · `.sm` `.lg` `.xl` | `Button` variantes `default`, `outline`, `destructive-outline`, `destructive`, `ghost` ; tailles `sm`, `lg`, `xl` | `xl` = pleine largeur, ≥ 60 px (caisse) ; raccourci clavier affiché en `.k` |
| `.inp` `.inp.big` `.focus` `.err` | `Input`, `AmountInput` | hauteur ≥ 40 px ; `big` = saisie du montant en caisse (`text-3xl`, ≥ 64 px) |
| `label.f` `.req` `.help` `.errtxt` | `Field` (le champ reçoit `id`, `aria-invalid`, `aria-describedby` : `{(control) => <Input {...control} />}`) ; react-hook-form + zod | astérisque rouge pour obligatoire ; erreur du serveur sous le champ : `applyServerErrors` (`src/lib/errors.ts`) |
| `.box` | `Checkbox` | |
| `.seg` | `Segmented` (choix unique, sur le `ToggleGroup` de Radix) | ex. USD / FC, Français / English |
| `.toggle` | `Switch` | |
| `.tbl` `tr.sel` `.errrow` `.warnrow` `tfoot` | `Table` | en-tête `#F8FAFA` ; ligne sélectionnée `lake-50` |
| `.pill` `ok` `due` `warn` `info` `gray` | `StatusPill` | point de couleur devant le texte |
| `.tag` `.tag.v` | `Tag` | `v` = marqueur de version (V1.1…) |
| `.banner` `info` `warn` `due` `ok` `lampb` | `Banner` (Alert) | icône à gauche |
| `.tabs` (`>span`, `>a`) | `Tabs` | onglet actif : texte et soulignement 3 px `lake` ; onglets de la fiche élève = liens (une URL par onglet) |
| `.steps` `.done` `.on` | `Steps` | fait = `ok` avec ✓ ; en cours = `lake` |
| `.bar` `i.ok` `i.warn` `i.due` | `Progress` | |
| `.avatar` `.who` | `Avatar`, `PersonCell` | initiales sur `lake-50` |
| `.sync.online` / `.sync.offline` | `SyncIndicator` | **toujours visible** dans la barre du haut de la Gestion |
| `.keypad` `.pins` | `PinPad` | déverrouillage PIN |
| `.side` `.brand` `.school` `.navlabel` `.nav a.on` `.soon` `.count` | coquille `AppShell` de la Gestion | 248 px ; groupes Pilotage / Scolarité / Finances / Communication / Paramètres ; entrée active = fond `basalt-2` + barre `lamp` ; entrées V1.1 / V1.2 **masquées** en V1.0 ; entrées filtrées par permission |
| `.top` `.search` `.kbd` `.user` | barre du haut | recherche globale `Ctrl K` |
| `.ptop` `.pnav` `.phone` | coquille du Portail | en-tête basalte, navigation basse à 4 entrées, largeur max 430 px |
| `.ctop` `.cmain` (`maquettes/console/`) | coquille de la console (`frontend/apps/console`, `ConsoleShell`) | pas de menu latéral : barre du haut basalte, marque + pastille « Console », navigation dessous (repère lampe), contenu clair jusqu'à 1 240 px ; connexion : carte blanche sur fond basalte |
| `.thermal` | gabarit reçu thermique | `@page { size: 80mm auto; margin: 0 }` ou `58mm auto` selon le réglage de l'école ; reçus A6 / A5 / petit format sur A4 avec traits de découpe : à dessiner en 3.2 |
| `.a4` | gabarit A4 | |
| `.authgrid` `.authside` `.authmain` | coquille des écrans hors application | connexion, activation 2FA, choix de l'école ; une colonne sous 900 px |
| `.overlay` `.dialog` | `DialogRoot` + `DialogContent` (titre, description, pied) | ex. réduction ; fermeture Échap, focus piégé |
| `.tl` (`.ok` `.due` `.warn` `.lamp`) | `Timeline` | historique de l'élève, plus récent en haut |
| `.codes` `.code` | `CodeList`, `Code` (police à chasse fixe) | codes de secours, code famille, clé TOTP ; code à 6 cases : `CodeInput` |
| `.frame` `.drawer` `.scrim` | `Sheet` (shadcn) côté gauche | menu de la Gestion sous 900 px (`frame` = présentation seulement) |
| `.spot` `.coach` | `Tour` (guide de première connexion) | élément réel mis en avant, reste assombri |
| `.toast` | `Toast` | ex. nouvelle version prête |
| `.a4.land` | gabarit A4 à l'italienne | export des impayés |
| `.bul` `.idbox` `tr.mx` `td.grey` | gabarit bulletin officiel (V1.2) | mise en page du formulaire EPST, voir `docs/claude/recherches/2026-09-26-bulletins-rdc.md` |
| `.pagehead` `.crumbs` | `PageHeader` | titre, sous-titre, fil d'Ariane, actions |
| pages d'état (M8) | `StateCard` | icône ronde, titre, texte, étiquette, actions |
| `.note` | **rien** | règle métier / critère d'acceptation, jamais affichée |

## Formats d'affichage

À implémenter une seule fois (`frontend/packages/money` et `frontend/packages/i18n`), jamais à la main dans un écran.

- USD : `1 234,56 $` — séparateur de milliers insécable, virgule décimale, symbole après.
- FC : `1 260 000 FC` — sans décimales.
- Montants dans deux devises : `20,00 $ + 30 000 FC`.
- Dates `19/10/2026`, heures `10:42`, fuseau de l'école (`Africa/Lubumbashi` par défaut).
- Élève : `NOM POST-NOM` en majuscules, prénom en casse normale (`KAMBALE MUHINDO Josué`).
- Anglais : mêmes règles de devise, formats de date selon la langue via i18next.

## Mise en page et accessibilité

- Page : contenu `padding 24px`, largeur max 1360 px, espacement vertical 20 px.
- En-tête de page : fil d'Ariane (`.crumbs`), titre, sous-titre `ink-2`, actions à droite.
- Grilles des écrans : colonnes `minmax(0, …)` (ex. `grid-cols-[minmax(0,1fr)] min-[1200px]:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]`) : sinon un tableau large élargit toute la page ; le tableau défile dans sa carte.
- Sous 900 px : barre latérale cachée (menu tiroir), grilles sur une colonne, recherche du haut masquée, rangées de boutons et pieds de carte qui passent à la ligne, tableau qui défile dans sa carte, barre d'onglets qui défile. **Chaque écran existe à 390 px (app) et à 1440 px (logiciel)** : `node maquettes/outils/captures.mjs` capture les deux et sort en erreur si un élément dépasse de l'écran.
- Focus visible : bordure `lake` + anneau 3 px `lake-50`. Erreur : bordure `due` + anneau `due-50`.
- Contraste : texte `ink` sur `surface` / `card` ; ne pas écrire en `ink-3` un texte important.
- Couleurs d'état **toujours** accompagnées d'un texte (« 5 j de retard », « soldé »), jamais la couleur seule.
- Personnalisation par école (`School.primary_color`, logo) : prévue via variables CSS ; elle ne remplace jamais les couleurs d'état.
