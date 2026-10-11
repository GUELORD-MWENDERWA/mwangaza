# Maquettes Mwangaza

Référence visuelle et fonctionnelle de chaque écran. **Toutes les données sont fictives** (noms, montants, taux, dates). Le jour simulé est le lundi 19 octobre 2026.

- `index.html` : galerie de tous les écrans (ouvrir dans un navigateur).
- `gestion/*.html` et `portail/*.html` : maquettes HTML statiques, lisibles comme code de référence.
- `captures/desktop/*.png` (1440 px) et `captures/mobile/*.png` (390 px) : captures d'écran.
- `assets/styles.css` : le système de design (couleurs, typographie, composants).

Domaine retenu le 2026-09-26 : `mwangaza.school`. Les maquettes affichent encore `mwangaza.cd` : lire `mwangaza.school`.

## Comment Claude Code doit s'en servir

1. Avant de construire un écran, ouvrir **la capture PNG** (pour l'aspect) et **le fichier HTML** (pour la structure exacte, les libellés et les notes).
2. Reproduire l'écran en React + Tailwind + shadcn/ui, **pas** copier le HTML tel quel. Les maquettes ne contiennent aucune logique.
3. Les encadrés jaunes pointillés (`.note`) sont des **règles métier et critères d'acceptation** : les appliquer, ne pas les afficher dans l'application.
4. Les bandeaux « V1.1 » ou « V1.2 » signalent un écran ou un élément d'une version suivante, à **ne pas coder avant sa tâche** ; dans le menu, ces entrées sont masquées. Ils datent de l'ancien découpage : depuis le 2026-10-02, la version qui compte est celle de `docs/05-plan-de-travail.md` et du tableau ci-dessous (ex. paie : V1.3, pointage : V1.2, notes : V1.4).
5. Libellés : reprendre ceux des maquettes dans les fichiers de traduction `fr` (puis traduire en `en`).
6. Si une maquette contredit `docs/02-perimetre-v1.md` ou `docs/04-modele-de-donnees.md`, **les documents font foi** ; signaler l'écart.

## Inventaire

État : **fournie** (maquette d'origine) ou **à valider** (dessinée par Claude le 2026-09-26 dans ce système de design, à partir des maquettes existantes et des documents ; la fusion de la PR vaut validation, les remarques se font en commentaire de PR). Numéros M1–M20 : `docs/07-a-fournir.md`.

### Application Gestion (personnel) — `{code}.mwangaza.school/app`

| Écran | Fichier | Lot | Réf. | État |
|---|---|---|---|---|
| Connexion | `gestion/connexion.html` | V1.0 | B4 | fournie |
| Double authentification | `gestion/connexion-double-authentification.html` | V1.0 | B4 | fournie |
| Activer la double authentification (QR + codes de secours) | `gestion/double-authentification-activation.html` | V1.0 | B4 · M1 | à valider — écart (4.6.2) : sur téléphone, bouton « Ajouter à mon application » (lien `otpauth://`, on ne peut pas scanner son propre écran) au-dessus du QR, et « Copier la clé » sous la clé |
| Choisir l'école (compte dans plusieurs écoles) | `gestion/choix-ecole.html` | V1.0 | B3 · M2 | à valider |
| Déverrouillage PIN hors-ligne | `gestion/deverrouillage-pin.html` | V1.0 | B5 | fournie |
| Mon compte | `gestion/mon-compte.html` | V1.0 | B4–B5 · M4 | à valider |
| Tableau de bord directeur | `gestion/tableau-de-bord.html` | V1.0 | G3 | fournie — codé en 4.2 sans sélecteur de période ni export (hors G3) |
| Menu sur téléphone et tablette | `gestion/menu-mobile.html` | V1.0 | § 9.4 · M7 | à valider |
| Notifications : centre et réglages (cloche de la barre du haut) | `gestion/notifications.html` | V1.1 | 5.5 | dessinée par Claude en 5.5.1 d'après `console/annonces` et `mon-compte` (à valider) ; codée en 5.5.1 : `/app/notifications`, réglages sur la même page (pas dans « Mon compte »), aperçu du téléphone non reproduit (c'est le système qui l'affiche) |
| Pages d'état et d'erreur (Gestion et Portail) | `gestion/pages-etat.html` | V1.0 | M8 | à valider |
| Guide de première connexion (caissier, comptable) | `gestion/guide-premiere-connexion.html` | V1.0 | I3 · M20 | à valider — codé en 4.5.1 : « Guide du caissier » (pas de féminin fixe) ; 1re étape du comptable « Vérifiez le taux de change » (taux fixe pour l'année, `04`) ; élément absent (ex. montant avant le choix d'un élève) : carte en bas, sans assombrir ; croix = fermé jusqu'à la prochaine ouverture |
| Liste des élèves | `gestion/eleves-liste.html` | V1.0 | D2 | fournie |
| Fiche élève, onglet Identité | `gestion/eleve-fiche-identite.html` | V1.0 | D2–D3 · M9 | à valider |
| Fiche élève, onglet Famille | `gestion/eleve-fiche-famille.html` | V1.0 | D4 · M9 | à valider |
| Fiche élève, onglet Finances | `gestion/eleve-fiche.html` | V1.0 | D2–D4 | fournie |
| Fiche élève, onglet Historique | `gestion/eleve-fiche-historique.html` | V1.0 | I1 · M9 | à valider |
| Inscrire un élève | `gestion/eleve-nouveau.html` | V1.0 | D3–D4 | fournie |
| Import Excel | `gestion/eleves-import.html` | V1.0 | D1 | fournie — écart (4.13) : une colonne facultative non choisie affiche « Facultatif » (au lieu de « Non utilisé »), aussi sur téléphone |
| Annuler un import | `gestion/eleves-import-annulation.html` | V1.0 | D6 | à valider — dessinée par Claude en 4.14 d'après `eleves-import` et `demande-annulation` ; écart : la carte « Imports précédents » n'apparaît que s'il y a au moins un import fini |
| Fiche famille | `gestion/famille-fiche.html` | V1.0 | D4, H1 · M10 | à valider |
| Fiche d'inscription (A4, code famille) | `gestion/fiche-inscription.html` | V1.0 | D5 · M11 | à valider |
| Liste de classe (PDF, Excel) | `gestion/liste-classe.html` | V1.0 | D5 · M11 | à valider |
| Invitations au portail (suivi par classe, message à partager) | `gestion/invitations-portail.html` | V1.0 | H7 | à valider — dessinée par Claude en 4.9 |
| Lettre d'invitation au portail (2 par A4) | `gestion/lettre-invitation.html` | V1.0 | H7 | à valider — dessinée par Claude en 4.9 |
| Frais, barèmes, taux | `gestion/frais-baremes.html` | V1.0 | E1–E5 | fournie |
| Accorder une réduction | `gestion/eleve-reduction.html` | V1.0 | E3 · M12 | à valider |
| Échéancier particulier | `gestion/eleve-echeancier.html` | V1.0 | E4 · M12 | à valider |
| Ouvrir une session de caisse | `gestion/caisse-ouverture.html` | V1.0 | F1 · M13 | à valider |
| Caisse : paiements du jour, recherche et réimpression d'un reçu | `gestion/caisse-accueil.html` | V1.0 | F1, F6 · M13 | à valider |
| **Caisse — encaissement** | `gestion/caisse-encaissement.html` | V1.0 | F1–F5 | fournie |
| Reçu 80 mm et A4 | `gestion/recu.html` | V1.0 | F3–F6 | fournie |
| Demander une annulation (dialogue de la caisse) | `gestion/demande-annulation.html` | V1.0 | F7 | à valider — dessinée par Claude en 3.8.1 d'après `caisse-accueil` et `eleve-reduction` |
| Annulations | `gestion/annulations.html` | V1.0 | F7 | fournie |
| Reçu d'annulation (80 mm et A4) | `gestion/recu-annulation.html` | V1.0 | F7 · M15 | à valider |
| Clôture de caisse (caissier) | `gestion/caisse-cloture.html` | V1.0 | F8 | fournie |
| Clôtures de caisse (comptable) | `gestion/clotures-caisse.html` | V1.0 | F8 · M16 | à valider |
| Crédits d'élèves (surpaiements) | `gestion/credits-eleves.html` | V1.0 | 3.6 · M14 | à valider — codée en 3.6.1 sans l'origine « Barème modifié » (un frais payé ne change plus, `04`) |
| Impayés | `gestion/impayes.html` | V1.0 | G1–G2 | fournie |
| Situation financière imprimable | `gestion/situation-financiere.html` | V1.0 | G2 · M17 | à valider |
| Export des impayés (PDF par classe, Excel) | `gestion/impayes-export.html` | V1.0 | G1 · M17 | à valider |
| Annonces | `gestion/annonces.html` | V1.0 | H4 | fournie |
| Demandes des parents (changements de coordonnées) | `gestion/changements-coordonnees.html` | V1.0 | H5 · M18 | à valider — codée en 4.4.5 : le secrétariat **applique** la demande (rien ne change sans lui, `02` H5 et `04` priment sur la note « déjà enregistré ») |
| Paramètres de l'école | `gestion/parametres-ecole.html` | V1.0 | A1, § 8.1 · M5 | à valider |
| Organisation scolaire | `gestion/organisation-scolaire.html` | V1.0 | C1–C3 | fournie — écart (4.13) : interrupteur « Attribuer un matricule automatiquement » en haut de la carte « Format du matricule » ; sur non, le modèle est grisé |
| Comptes du personnel | `gestion/personnel-comptes.html` | V1.0 | B1–B3 · M3 | à valider |
| Rôles et permissions | `gestion/roles-permissions.html` | V1.0 | B1–B2 | fournie |
| Appareils et synchronisation | `gestion/appareils-synchro.html` | V1.0 | F5, B5 | fournie |
| Journal d'audit | `gestion/journal-audit.html` | V1.0 | I1 · M6 | à valider |
| Super-admin — écoles (`admin.mwangaza.school`) | `gestion/superadmin-ecoles.html` | V1.0 (fonctions dans l'administration Django, 1.5) ; remplacée par `console/ecoles` (5.3) | A1–A3 | fournie |
| Session support « en tant qu'école » (ouverture avec le motif, bandeau rouge) | `gestion/session-support.html` | V1.0 | A3 | validée par l'utilisateur le 2026-09-26 (dessinée pour la tâche 1.6) |
| Paie | `gestion/paie.html` | V1.3 | 7.3 | fournie |
| Pointage QR (carte unique : puce ou QR) | `gestion/presences-pointage-qr.html` | V1.2 | 6.3 | fournie |
| Saisie des notes | `gestion/notes-saisie.html` | V1.4 | 8.2 | fournie |
| Cours et maxima par classe | `gestion/cours-maxima.html` | V1.4 | 8.1 | à valider |
| Bulletin officiel — humanités techniques (formulaire IGE/P.S/100) | `gestion/bulletin.html` | V1.4 | 8.3 | à valider (remplace le gabarit provisoire) |
| Bulletin officiel — 7e–8e EB (formulaire IGE/P.S/005) | `gestion/bulletin-education-de-base.html` | V1.4 | 8.3 | à valider |

Captures mobiles aussi fournies pour : caisse (encaissement, ouverture), pointage, saisie des notes, menu mobile, guide de première connexion (la Gestion doit rester utilisable sur tablette et téléphone Android).

Bulletins : structure et maxima repris des formulaires officiels trouvés en ligne — détail et sources dans `docs/claude/recherches/2026-09-26-bulletins-rdc.md`. À confirmer avec les bulletins réels de l'ITIG (I15).

### Portail familles — `parents.mwangaza.school` (mobile d'abord)

| Écran | Fichier | Lot | Réf. | État |
|---|---|---|---|---|
| Activation du compte famille | `portail/activation.html` | V1.0 | H1 | fournie |
| Se connecter | `portail/connexion.html` | V1.0 | H1 · M19 | à valider — écart (4.12) : après une session finie, bandeau « Votre session est terminée » au-dessus du numéro, déjà rempli |
| Mot de passe oublié (nouveau code famille) | `portail/mot-de-passe-oublie.html` | V1.0 | H1 · M19 | à valider |
| Installer l'application | `portail/installer.html` | V1.0 | H6 · M19 | à valider |
| Guide de première connexion (parent) | `portail/guide.html` | V1.0 | I3 · M20 | à valider — codé en 4.5.1 avec des exemples neutres (pas de numéro de reçu d'une école) ; relancé : « L'essentiel du portail en 3 étapes » au lieu de « compte activé » |
| Accueil — mes enfants (multi-écoles) | `portail/accueil.html` | V1.0 | H2 | fournie |
| Paiements d'un enfant | `portail/enfant-paiements.html` | V1.0 | H3 | fournie |
| Annonces | `portail/annonces.html` | V1.0 | H4 | fournie |
| Profil et coordonnées | `portail/profil.html` | V1.0 | H5 | fournie — codé en 4.4.5 avec le contact d'urgence à la place du « Téléphone secondaire » (pas de champ au modèle) |
| Vérification publique d'un reçu (`/v/{id}`) | `portail/verification-recu.html` | V1.0 | F4 | fournie |
| Scolarité d'un enfant | `portail/enfant-scolarite.html` | V1.4 | 8.8 | fournie |

### Console de la plateforme — `admin.mwangaza.school` (super-admin, son propre design)

Pas de menu latéral comme la Gestion : barre du haut en basalte (marque, pastille « Console », menu du compte), navigation dessous avec le repère lampe, contenu clair et large (styles de la coquille dans la page : `.ctop`, `.cmain`). Connexion : carte blanche sur fond basalte, mêmes étapes que la Gestion (`gestion/connexion`, `gestion/connexion-double-authentification`), sans « Se souvenir de cet appareil ».

| Écran | Fichier | Lot | Réf. | État |
|---|---|---|---|---|
| Tableau de bord | `console/tableau-de-bord.html` | V1.1 | 5.2 | dessinée par Claude en 5.2.1 (à valider) ; codée en 5.2.1 (menu réduit au tableau de bord, la santé du serveur en pastille dans l'en-tête de la page au lieu de la barre du haut) |
| Identité de la plateforme | `console/identite-plateforme.html` | V1.1 | 5.2.2 | dessinée par Claude en 5.2.2 (à valider) ; codée en 5.2.2, sans écart (sur téléphone, l'aperçu et les modifications passent sous le formulaire) |
| Écoles | `console/ecoles.html` | V1.1 | 5.3 | dessinée par Claude en 5.3 d'après `gestion/superadmin-ecoles` (à valider) ; codée en 5.3 en trois écrans (liste, `/schools/new`, fiche `/schools/<id>`) ; « Créer l'école » donne un mot de passe provisoire affiché une seule fois au lieu d'un lien d'activation (pas de SMS en V1) |
| Comptes | `console/comptes.html` | V1.1 | 5.4.1 | dessinée par Claude en 5.4.1 d'après `console/ecoles` (à valider) ; codée en 5.4.1 en deux écrans (liste `/accounts`, fiche `/accounts/<id>`) ; les familles du portail ont leur propre carte au lieu de partager celle des écoles |
| Annonces aux écoles (et bandeau, liste dans la Gestion) | `console/annonces.html` | V1.1 | 5.4.3 | dessinée par Claude en 5.4.3 d'après `gestion/annonces` (à valider) ; codée en 5.4.3 : console `/announcements`, Gestion bandeau en haut du contenu et liste `/app/platform-news` (lien en bas du menu) ; pas de bouton « Aperçu » dans la console (le bandeau de la Gestion reprend le titre et la première ligne) ; choix des écoles par une recherche au lieu d'une liste |
| Appareils | `console/appareils.html` | V1.1 | 5.4.2 | dessinée par Claude en 5.4.2 d'après `console/comptes` (à valider) ; codée en 5.4.2 (`/devices`) ; sans compteur d'appareils sous la liste |
| Journal et sessions support | `console/journal.html` | V1.1 | 5.4.2 | dessinée par Claude en 5.4.2 (à valider) ; codée en 5.4.2 en deux onglets (`/journal`, `/journal/support`) ; sans compteur d'entrées sous la liste |

### Menu de la Gestion

Depuis le 2026-09-26, le menu latéral compte 5 entrées de plus, pour les nouveaux écrans : **Crédits d'élèves** (Finances), **Demandes des parents** (Communication), **Paramètres de l'école**, **Comptes du personnel** et **Journal d'audit** (Paramètres). Le menu est identique sur toutes les maquettes (voir « Outils »). Le super-admin garde son propre menu.

## Outils (`maquettes/outils/`)

Aucune dépendance à installer (Python 3, Node 22 et Google Chrome de la machine).

| Commande | Effet |
|---|---|
| `python3 maquettes/outils/maquettes.py menu` | réécrit le menu latéral de toutes les pages Gestion depuis `MENU` (à lancer après avoir ajouté une entrée) |
| `python3 maquettes/outils/maquettes.py index` | régénère `index.html` depuis le catalogue `GESTION` / `PORTAIL` / `CONSOLE` |
| `node maquettes/outils/captures.mjs [fichier.html …]` | refait les captures PNG (bureau 1440 px, mobile 390 px × 2 ; console : les deux) ; sans argument : toutes |

Pour dessiner un nouvel écran : écrire la page avec la même coquille (`page_gestion`, `page_auth`, `page_portail` et `ic` dans `maquettes.py`), l'ajouter au catalogue, puis `index` et `captures`.

## Système de design

### Intention

- **Basalte** (pierre volcanique de Goma) pour la barre latérale et l'en-tête du portail : sobre, lisible, ancré localement.
- **Lampe** (jaune) = *mwangaza*, la lumière. Utilisée avec parcimonie : repère de l'élément actif, logo, points d'attention. Jamais en fond de page.
- **Lac** (bleu-vert du lac Kivu) pour toutes les actions principales.
- Police **Atkinson Hyperlegible** (fournie dans `assets/fonts/`, à embarquer dans l'application pour le hors-ligne) : conçue pour la lisibilité, adaptée à des utilisateurs peu habitués à l'informatique et aux écrans de faible qualité.
- Chiffres toujours en **tabulaires** (`font-variant-numeric: tabular-nums`) et alignés à droite.

### Couleurs (à reporter dans le thème Tailwind / variables shadcn)

Depuis la 5.1, le nom « Mwangaza », la lampe et les couleurs `lamp` / `lake` des maquettes sont les valeurs **de départ** de l'identité de la plateforme : l'application lit le nom, le logo (sinon la lampe), l'icône et ces deux couleurs dans ses paramètres. Ajouts sans maquette : lien « Mentions légales » à la suite des langues sous les connexions (Gestion et Portail, s'il y a un texte) ; téléphone et e-mail du support sous « École suspendue » et « Aucune école à cette adresse ».

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

Ajoutés le 2026-09-26 (fin de `assets/styles.css`) : écran hors application (`authgrid`), fenêtre de dialogue (`overlay` + `dialog`), frise chronologique (`tl`), codes à recopier (`codes`, `code`), cadre de téléphone et menu coulissant (`frame`, `drawer`, `scrim`), mise en avant du guide (`spot`, `coach`), notification passagère (`toast`), pastille de couleur (`swatch`), A4 à l'italienne (`a4 land`), bulletin officiel (`bul`, `idbox`), onglets-liens (`.tabs>a`).

### Formats d'affichage

- USD : `1 234,56 $` (espace insécable pour les milliers, virgule décimale).
- FC : `1 260 000 FC` (sans décimales).
- Dates : `19/10/2026` ; heures : `10:42`.
- Noms d'élèves : NOM POST-NOM en majuscules, prénom en casse normale.
