# Maquettes Mwangaza

Référence visuelle et fonctionnelle de chaque écran. **Toutes les données sont fictives** (noms, montants, taux, dates). Le jour simulé est le lundi 19 octobre 2026.

- `index.html` : galerie de tous les écrans (ouvrir dans un navigateur).
- `gestion/*.html` et `portail/*.html` : maquettes HTML statiques, lisibles comme code de référence.
- `captures/desktop/*.png` (1440 px) et `captures/mobile/*.png` (390 px) : captures d'écran.
- `assets/styles.css` : le système de design (couleurs, typographie, composants).

## Comment Claude Code doit s'en servir

1. Avant de construire un écran, ouvrir **la capture PNG** (pour l'aspect) et **le fichier HTML** (pour la structure exacte, les libellés et les notes).
2. Reproduire l'écran en React + Tailwind + shadcn/ui, **pas** copier le HTML tel quel. Les maquettes ne contiennent aucune logique.
3. Les encadrés jaunes pointillés (`.note`) sont des **règles métier et critères d'acceptation** : les appliquer, ne pas les afficher dans l'application.
4. Les bandeaux « V1.1 » ou « V1.2 » signalent un écran ou un élément à **ne pas coder en V1.0**. Dans le menu V1.0, ces entrées sont masquées.
5. Libellés : reprendre ceux des maquettes dans les fichiers de traduction `fr` (puis traduire en `en`).
6. Si une maquette contredit `docs/02-perimetre-v1.md` ou `docs/04-modele-de-donnees.md`, **les documents font foi** ; signaler l'écart.

## Inventaire

### Application Gestion (personnel) — `{code}.mwangaza.cd/app`

| Écran | Fichier | Lot | Réf. |
|---|---|---|---|
| Connexion | `gestion/connexion.html` | V1.0 | B4 |
| Double authentification | `gestion/connexion-double-authentification.html` | V1.0 | B4 |
| Déverrouillage PIN hors-ligne | `gestion/deverrouillage-pin.html` | V1.0 | B5 |
| Tableau de bord directeur | `gestion/tableau-de-bord.html` | V1.0 | G3 |
| Liste des élèves | `gestion/eleves-liste.html` | V1.0 | D2 |
| Fiche élève (onglet Finances) | `gestion/eleve-fiche.html` | V1.0 | D2–D4 |
| Inscrire un élève | `gestion/eleve-nouveau.html` | V1.0 | D3–D4 |
| Import Excel | `gestion/eleves-import.html` | V1.0 | D1 |
| Frais, barèmes, taux | `gestion/frais-baremes.html` | V1.0 | E1–E5 |
| **Caisse — encaissement** | `gestion/caisse-encaissement.html` | V1.0 | F1–F5 |
| Reçu 80 mm et A4 | `gestion/recu.html` | V1.0 | F3–F6 |
| Clôture de caisse | `gestion/caisse-cloture.html` | V1.0 | F8 |
| Annulations | `gestion/annulations.html` | V1.0 | F7 |
| Impayés | `gestion/impayes.html` | V1.0 | G1–G2 |
| Annonces | `gestion/annonces.html` | V1.0 | H4 |
| Organisation scolaire | `gestion/organisation-scolaire.html` | V1.0 | C1–C3 |
| Rôles et permissions | `gestion/roles-permissions.html` | V1.0 | B1–B2 |
| Appareils et synchronisation | `gestion/appareils-synchro.html` | V1.0 | F5, B5 |
| Super-admin — écoles (`admin.mwangaza.cd`) | `gestion/superadmin-ecoles.html` | V1.0 | A1–A3 |
| Paie | `gestion/paie.html` | V1.1 | 5.3 |
| Pointage QR | `gestion/presences-pointage-qr.html` | V1.1 | 5.5 |
| Saisie des notes | `gestion/notes-saisie.html` | V1.2 | 6.2 |
| Bulletin (gabarit provisoire) | `gestion/bulletin.html` | V1.2 | 6.3 |

Captures mobiles aussi fournies pour : caisse, pointage, saisie des notes (la Gestion doit rester utilisable sur tablette et téléphone Android).

### Portail familles — `parents.mwangaza.cd` (mobile d'abord)

| Écran | Fichier | Lot | Réf. |
|---|---|---|---|
| Activation du compte famille | `portail/activation.html` | V1.0 | H1 |
| Accueil — mes enfants (multi-écoles) | `portail/accueil.html` | V1.0 | H2 |
| Paiements d'un enfant | `portail/enfant-paiements.html` | V1.0 | H3 |
| Annonces | `portail/annonces.html` | V1.0 | H4 |
| Profil et coordonnées | `portail/profil.html` | V1.0 | H5 |
| Vérification publique d'un reçu (`/v/{id}`) | `portail/verification-recu.html` | V1.0 | F4 |
| Scolarité d'un enfant | `portail/enfant-scolarite.html` | V1.2 | 6.8 |

## Système de design

### Intention

- **Basalte** (pierre volcanique de Goma) pour la barre latérale et l'en-tête du portail : sobre, lisible, ancré localement.
- **Lampe** (jaune) = *mwangaza*, la lumière. Utilisée avec parcimonie : repère de l'élément actif, logo, points d'attention. Jamais en fond de page.
- **Lac** (bleu-vert du lac Kivu) pour toutes les actions principales.
- Police **Atkinson Hyperlegible** (fournie dans `assets/fonts/`, à embarquer dans l'application pour le hors-ligne) : conçue pour la lisibilité, adaptée à des utilisateurs peu habitués à l'informatique et aux écrans de faible qualité.
- Chiffres toujours en **tabulaires** (`font-variant-numeric: tabular-nums`) et alignés à droite.

### Couleurs (à reporter dans le thème Tailwind / variables shadcn)

| Jeton | Valeur | Usage |
|---|---|---|
| `basalt` | `#2B2724` | barre latérale, en-tête portail |
| `basalt-2` | `#3A3531` | élément actif sur basalte |
| `lamp` | `#F2B632` | repère actif, logo, accent rare |
| `lamp-soft` | `#FDF3D8` | bandeaux d'information de marque |
| `lake` | `#0E5C6B` | bouton principal, liens, focus (= `primary`) |
| `lake-50` | `#E6F0F2` | sélection, fond de focus |
| `ink` | `#1A2233` | texte |
| `ink-2` / `ink-3` | `#4A5568` / `#77818F` | texte secondaire / tertiaire |
| `surface` | `#F3F5F6` | fond de page |
| `line` | `#DDE3E6` | bordures |
| `ok` / `ok-50` | `#1F7A4D` / `#E5F3EB` | payé, à jour, succès |
| `due` / `due-50` | `#B42318` / `#FBE9E7` | en retard, erreur, danger |
| `warn` / `warn-50` | `#9A5B00` / `#FFF1D6` | partiel, hors-ligne, avertissement |

### Formes et tailles

- Rayons : cartes 12 px, champs et boutons 8 px, pastilles d'état arrondies.
- Hauteur minimale des champs : 40 px ; boutons principaux de caisse : très grands (60 px et plus).
- Base 15 px ; titres de page 1,6 rem.

### Composants récurrents

Carte (en-tête / corps / pied), KPI, tableau, pastille d'état (`ok`, `due`, `warn`, `info`, `gray`), bandeau (`info`, `warn`, `due`, `ok`, `lampb`), segmenté, interrupteur, case à cocher, étapes, barre de progression, indicateur de synchronisation (toujours visible en haut de la Gestion).

### Formats d'affichage

- USD : `1 234,56 $` (espace insécable pour les milliers, virgule décimale).
- FC : `1 260 000 FC` (sans décimales).
- Dates : `19/10/2026` ; heures : `10:42`.
- Noms d'élèves : NOM POST-NOM en majuscules, prénom en casse normale.
