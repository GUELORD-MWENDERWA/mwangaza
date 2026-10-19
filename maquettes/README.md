# Maquettes Mwangaza

Référence visuelle et fonctionnelle de chaque écran. **Toutes les données sont fictives** (noms, montants, taux, dates). Le jour simulé est le lundi 19 octobre 2026.

- `index.html` : galerie de tous les écrans (ouvrir dans un navigateur).
- `gestion/*.html` et `portail/*.html` : maquettes HTML statiques, lisibles comme code de référence.
- `captures/desktop/*.png` (1440 px) et `captures/mobile/*.png` (390 px) : captures d'écran.
- `assets/styles.css` : le système de design (couleurs, typographie, composants).
- `site/*.html` (site public de la plateforme, WEB.1a) : feuille `assets/site.css` en plus, photos dans `assets/photos/` (crédits dans son `README.md`), captures aussi à 820 px dans `captures/tablet/`, en **WebP** (les photos rendraient chaque PNG trop lourd pour Git).

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
| Préparer le hors-ligne (bandeau du code PIN, page hors ligne qui explique) | `gestion/hors-ligne-preparer.html` | V1.0 | B5 | dessinée 2026-10-17 (L.6), codée |
| Mon compte | `gestion/mon-compte.html` | V1.0 | B4–B5 · M4 | à valider |
| Tableau de bord directeur | `gestion/tableau-de-bord.html` | V1.0 | G3 | fournie — codé en 4.2 sans sélecteur de période ni export (hors G3) |
| Mise en route d'une école neuve | `gestion/mise-en-route.html` | V1.0 | C4 | à valider — dessinée par Claude en 4.20.1 d'après `tableau-de-bord` ; codée en 4.20.1 (carte en haut du tableau de bord ; « Terminer la mise en route » dans le pied de la carte quand l'école peut encaisser) ; la même carte est aussi sur l'accueil d'après connexion (4.20.2, sans maquette propre) |
| Menu sur téléphone et tablette | `gestion/menu-mobile.html` | V1.0 | § 9.4 · M7 | à valider |
| Notifications : centre et réglages (cloche de la barre du haut) | `gestion/notifications.html` | V1.1 | 5.5 | dessinée par Claude en 5.5.1 d'après `console/annonces` et `mon-compte` (à valider) ; codée en 5.5.1 : `/app/notifications`, réglages sur la même page (pas dans « Mon compte »), aperçu du téléphone non reproduit (c'est le système qui l'affiche) ; 5.6.1 : alertes « Annulation à valider » et « Écart de caisse », offertes selon les droits ; 5.6.2 : « Caisse encore ouverte » |
| Pages d'état et d'erreur (Gestion et Portail) | `gestion/pages-etat.html` | V1.0 | M8 | à valider |
| Guide de première connexion (caissier, comptable) | `gestion/guide-premiere-connexion.html` | V1.0 | I3 · M20 | à valider — codé en 4.5.1 : « Guide du caissier » (pas de féminin fixe) ; 1re étape du comptable « Vérifiez le taux de change » (taux fixe pour l'année, `04`) ; élément absent (ex. montant avant le choix d'un élève) : carte en bas, sans assombrir ; croix = fermé jusqu'à la prochaine ouverture ; donné d'après les droits du compte, pas le nom de son rôle (M.3.1 : comptable = règle les frais sans régler l'école, caisse = encaisse) |
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
| Options d'impression et en-tête des documents (papier, sens, exemplaires ; logo, drapeau, filet, titre avec N°) | `gestion/impression-options.html` | V1.2 | IMP.1 · 8.3.4 | à valider — dessinée par Claude le 2026-10-15 d'après l'exemplaire d'en-tête fourni ; s'applique à tous les documents imprimés |
| Invitations au portail (suivi par classe, message à partager) | `gestion/invitations-portail.html` | V1.0 | H7 | à valider — dessinée par Claude en 4.9 |
| Lettre d'invitation au portail (2 par A4) | `gestion/lettre-invitation.html` | V1.0 | H7 | à valider — dessinée par Claude en 4.9 |
| Frais, barèmes, taux | `gestion/frais-baremes.html` | V1.0 | E1–E5 | fournie |
| Accorder une réduction | `gestion/eleve-reduction.html` | V1.0 | E3 · M12 | à valider |
| Reprise en cours d'année | `gestion/reprise-paiements.html` | V1.0 | E6 | à valider — dessinée par Claude en 4.19 d'après `eleves-import` ; écran codé : les étapes « Fichier » et « Enregistré » reprennent la même page (carte du fichier, puis bandeau vert et mêmes tableaux) |
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
| Impayés | `gestion/impayes.html` | V1.0 | G1–G2 | fournie ; écart : pas de bouton « Envoyer une relance » (relances automatiques, 5.6.2) |
| Situation financière imprimable | `gestion/situation-financiere.html` | V1.0 | G2 · M17 | à valider |
| Export des impayés (PDF par classe, Excel) | `gestion/impayes-export.html` | V1.0 | G1 · M17 | à valider |
| Registre des reçus (PDF, Excel) | `gestion/registre-recus.html` | V1.0 | DOC.3 | à valider (dessinée d'après l'export des impayés ; pas de capture PNG) |
| Annonces | `gestion/annonces.html` | V1.0 | H4 | fournie |
| Annonces au personnel | `gestion/annonces-personnel.html` | V1.1 | 5.7 | dessinée par Claude en 5.7 d'après `console/annonces` (à valider) ; codée en 5.7 |
| Calendrier de l'école | `gestion/calendrier.html` | V1.1 | 5.7 | dessinée par Claude en 5.7 d'après `gestion/annonces` (à valider) ; codée en 5.7 — écart : le formulaire s'ouvre dans une fenêtre, pas dans une colonne |
| Convocations des parents | `gestion/convocations.html` | V1.1 | 5.7 | dessinée par Claude en 5.7 d'après `gestion/annonces` (à valider) ; codée en 5.7 |
| Demandes des parents (changements de coordonnées) | `gestion/changements-coordonnees.html` | V1.0 | H5 · M18 | à valider — codée en 4.4.5 : le secrétariat **applique** la demande (rien ne change sans lui, `02` H5 et `04` priment sur la note « déjà enregistré ») |
| Paramètres de l'école | `gestion/parametres-ecole.html` | V1.0 | A1, § 8.1 · M5 | à valider ; 5.6.2 : carte « Relances aux parents » dessinée par Claude d'après « Alertes au directeur » et codée ; DOC.1 : carte « Cachet et signature » codée sans maquette dédiée (même gabarit de carte), et signature dans « Mon compte » ; 8.4.0 : carte « Saisie des points » (deux choix) dessinée dans la maquette et codée |
| Organisation scolaire | `gestion/organisation-scolaire.html` | V1.0 | C1–C3 | fournie — écart (4.13) : interrupteur « Attribuer un matricule automatiquement » en haut de la carte « Format du matricule » ; sur non, le modèle est grisé |
| Comptes du personnel | `gestion/personnel-comptes.html` | V1.0 | B1–B3 · M3 | à valider |
| Rôles et permissions | `gestion/roles-permissions.html` | V1.0 | B1–B2 | fournie — écarts : note d'information sur tout rôle sans aucune permission cochée (M.3.1) ; plus de mention « prédéfini / personnalisé », nom obligatoire et bouton « Supprimer » pour tous les rôles (M.3.2) |
| Appareils et synchronisation | `gestion/appareils-synchro.html` | V1.0 | F5, B5 | fournie |
| Journal d'audit | `gestion/journal-audit.html` | V1.0 | I1 · M6 | à valider |
| Super-admin — écoles (`admin.mwangaza.school`) | `gestion/superadmin-ecoles.html` | V1.0 (fonctions dans l'administration Django, 1.5) ; remplacée par `console/ecoles` (5.3) | A1–A3 | fournie |
| Session support « en tant qu'école » (ouverture avec le motif, bandeau rouge) | `gestion/session-support.html` | V1.0 | A3 | validée par l'utilisateur le 2026-09-26 (dessinée pour la tâche 1.6) |
| Paie | `gestion/paie.html` | V1.7 | 7.3 | fournie |
| Pointage QR (carte unique : puce ou QR) | `gestion/presences-pointage-qr.html` | V1.5 | 6.3 | fournie |
| Saisie des notes | `gestion/notes-saisie.html` | V1.2 | 8.2.1 → 8.2.3 | fournie, complétée par Claude en 8.2.1 (à valider) : rangée « Évaluations » (ajouter, renommer, retirer, chacune avec son maximum), boîte « Évaluation », une carte par élève au téléphone ; codée en 8.2.1 sans le bandeau de date limite ni « Envoyer pour validation » (8.2.2), ni « Enregistré sur l'appareil · synchronisé » (8.2.3) ; pied de la carte collé en bas de l'écran (longue page au téléphone) ; 8.4.0 : sans devoirs, la rangée « Évaluations » disparaît et la feuille n'a qu'une colonne « Total » (codé sans maquette dédiée : même tableau) ; colonne « Saisie » ajoutée à « Cours et maxima » (liste : selon l'école, devoirs détaillés, total de la période) ; NB.1 : « Envoyer et signer » (boîte de confirmation) au lieu de « Envoyer pour validation », bandeau « Fiche renvoyée » avec les remarques du directeur des études, plus de « Valider » ni « Rouvrir » ici ; seuls les cours de l'enseignant (ou tous en total pour le secrétariat) |
| Suivi des notes (directeur des études) | `gestion/notes-validation.html` | V1.2 | 8.2.2, NB.2 | dessinée par Claude en 8.2.2, redessinée en NB.2 (à valider) d'après la validation existante et le circuit des cotes (`docs/claude/recherches/2026-10-18-notes-deliberation-rdc.md`) : par période, chiffres (classes complètes, à valider, pas encore envoyées, renvoyées), classes avec barre des fiches validées, états des cours, filtres, rappel en un geste (par cours, par classe, tous), tableau synthétique, palmarès, bulletins d'une classe complète, dates limites ; codée telle quelle (`/grade-validation`), sauf : chiffres en quatre cartes (`Kpi`, deux par deux au téléphone) au lieu d'une seule, la carte « Une classe complète » n'est qu'un exemple (la classe est dans la liste, filtre « Complètes ») ; « Ouvrir » mène à la fiche de cotes (`notes-fiche-cotes`) |
| Fiche de cotes reçue | `gestion/notes-fiche-cotes.html` | V1.2 | NB.1 | dessinée par Claude en NB.1 (à valider) d'après la validation et la fiche imprimée : un total par élève (numéro devant le nom), résumé (moyenne, plus haute, plus basse, sous la moitié), historique, « Valider » et « Renvoyer avec remarques » pour le directeur des études, lecture seule pour le titulaire et le secrétariat ; codée telle quelle (`/grade-sheets/totals`), « Imprimer » ouvre « Fiches de cotes » sur le cours |
| Fiches de cotes | `gestion/notes-fiches.html` | V1.2 | 8.3.6 | dessinée par Claude en 8.3.6 (à valider) d'après le bulletin et la liste de classe : choix du document (un cours, vierge, classe), classe, cours ou colonne, colonnes, papier et sens ; codée telle quelle, au téléphone l'aperçu passe sous les réglages ; le tableau de la classe numérote ses cours (légende dessous) car le texte vertical n'est pas fiable en PDF ; NB.2 : quatrième document, le **palmarès** (place, ex æquo, total, %, mention, non classés à la fin, signature du directeur des études, portrait), « tableau de la classe » renommé « tableau synthétique » ; l'écran s'ouvre avec la classe, le document et la période choisis (`?class=&kind=&column=`) |
| Conduite : attribuer une infraction | `gestion/conduite-incidents.html` | V1.2 | 8.5.1a | dessinée par Claude en 8.5.1a (à valider) d'après la saisie des notes : classe, élève, infraction avec ses points, date, note ; historique de l'élève avec points et cote par période, annulation avec motif, « Corriger » la cote avec motif (8.5.1b) ; codée telle quelle (au téléphone, le formulaire passe au-dessus de l'historique) |
| Barème de conduite | `gestion/conduite-bareme.html` | V1.2 | 8.5.1a | dessinée par Claude en 8.5.1a (à valider) : liste des infractions (ajouter, modifier, retirer, liste proposée) et seuils des cinq cotes ; codée telle quelle |
| Examens de repêchage | `gestion/repechage.html` | V1.2 | 8.4.1 | dessinée par Claude en 8.4.1 (à valider) d'après l'Application : classe, élèves avec cours échoués, note de repêchage saisie (signée), issue proposée ; cartes « Réussite et repêchage » et « Règles par niveau » (7e, 3e… : critères propres, repêchés au plus) ajoutées à `parametres-ecole.html`, colonne « Repêchage » (interrupteur) de la grille des cours (codée sans maquette dédiée) ; cartes sur téléphone |
| Délibération d'une classe | `gestion/deliberation.html` | V1.2 | 8.4.2 | dessinée par Claude en 8.4.2 (à valider) d'après le Repêchage : date, compteurs par décision, tableau proposé / décision / motif de l'écart, boutons « Prendre les propositions » et « Proclamer », liens vers Conduite et Application ; carte « classe proclamée » avec réouverture motivée ; cartes sur téléphone |
| Situations de fin d'année | `gestion/situations.html` | V1.2 | 8.4.4 | dessinée par Claude en 8.4.4 (à valider) d'après les fiches de cotes : document (classe ou école), classe, critère (règles de la classe ou moyenne seule), parties (par cours, palmarès, matricule, écarts), impression ; aperçu des deux documents ; codée telle quelle (au téléphone, l'aperçu passe sous les réglages) ; situation de l'école en paysage par défaut, sous-total d'un niveau seulement s'il a une classe proclamée |
| Reprise des résultats | `gestion/reprise-resultats.html` | V1.2 | 8.4.7 | dessinée par Claude en 8.4.7 (à valider) d'après la reprise des paiements : modèle Excel, étapes, compteurs, lignes à corriger, premières lignes prêtes ; l'année est celle en cours (pas de choix) ; la délibération gagne le champ « % repris » et la pastille « Sans note » pour un élève sans aucune note, et le lien « Importer des résultats repris » |
| Passage de classe | `gestion/passage-classe.html` | V1.2 | 8.4.5 | dessinée par Claude en 8.4.5 (à valider) d'après les logiciels de réinscription (`docs/claude/recherches/2026-10-17-passage-de-classe.md`) : classes de l'année finie (défile au téléphone), élèves d'une classe avec décision, place proposée, réponse du parent, état ; trois actions en lot ; codée sans écart |
| Application : cote par période | `gestion/application.html` | V1.2 | 8.5.1c | dessinée par Claude en 8.5.1c (à valider) d'après le tableau de la conduite : classe, élèves × périodes avec cote et pourcentage, « Corriger » (motif) pour le titulaire ; cartes sur téléphone |
| Cours et maxima par classe | `gestion/cours-maxima.html` | V1.2 | 8.1 | à valider — codée en 8.1 avec des écarts : colonnes « Domaine » et « H / sem. » en plus, cours ajoutés et retirés dans la grille ; regroupements par maximum (lignes MAXIMA) dans la carte « Contrôle » et non dans la grille (les lignes sauteraient pendant la saisie) ; « Contrôle » et « Modèles officiels » au-dessus d'une grille en pleine largeur (sinon heures et enseignant sortent de la carte à 1440 px) ; pas de « Modèle appliqué » retenu (rien n'est stocké) |
| Charges des enseignants | `gestion/charges-enseignants.html` | V1.2 | 8.1 | à valider — dessinée par Claude en 8.1 ; codée sans écart (au téléphone, colonne « Cours » masquée) |
| Bulletin officiel — humanités techniques (formulaire IGE/P.S/100) | `gestion/bulletin.html` | V1.2 | 8.3 | codé (8.3.3) fidèle au scan de la 3e HT (colonnes à 0,2 mm) : un gabarit pour toutes les classes, bloc Examen d'État pour la dernière année ; province, ville, commune, N° ID et N° permanent viennent des paramètres de l'école et de la fiche de l'élève ; armoiries remplacées par le QR code ; bloc « Impression » (notes seules, calage, toute la classe) ajouté en 8.3.5 ; bas rempli par la délibération proclamée en 8.4.3 (note ajoutée à la maquette, mentions biffées, date, repêchage) |
| Bulletin officiel — 7e–8e EB (formulaire IGE/P.S/005) | `gestion/bulletin-education-de-base.html` | V1.2 | 8.3 | à valider |

Captures mobiles aussi fournies pour : caisse (encaissement, ouverture), pointage, saisie des notes, menu mobile, guide de première connexion (la Gestion doit rester utilisable sur tablette et téléphone Android).

Bulletins : structure et maxima repris des formulaires officiels trouvés en ligne — détail et sources dans `docs/claude/recherches/2026-09-26-bulletins-rdc.md`. À confirmer avec les bulletins réels de l'ITIG (I15).

### Portail familles — `parents.mwangaza.school` (mobile d'abord)

| Écran | Fichier | Lot | Réf. | État |
|---|---|---|---|---|
| Activation du compte famille | `portail/activation.html` | V1.0 | H1 | fournie |
| Se connecter | `portail/connexion.html` | V1.0 | H1 · M19 | à valider — écart (4.12) : après une session finie, bandeau « Votre session est terminée » au-dessus du numéro, déjà rempli |
| Mot de passe oublié (nouveau code famille) | `portail/mot-de-passe-oublie.html` | V1.0 | H1 · M19 | à valider |
| Installer l'application | `portail/installer.html` | V1.0 | H6 · M19 | à valider (la Gestion a un écran d'installation obligatoire sans maquette, 4.24, dessiné d'après `StandaloneStatus` ; capture 390 px non gardée) |
| Guide de première connexion (parent) | `portail/guide.html` | V1.0 | I3 · M20 | à valider — codé en 4.5.1 avec des exemples neutres (pas de numéro de reçu d'une école) ; relancé : « L'essentiel du portail en 3 étapes » au lieu de « compte activé » |
| Accueil — mes enfants (multi-écoles) | `portail/accueil.html` | V1.0 | H2 | fournie ; carte « Places pour l'année prochaine » ajoutée par Claude en 8.4.5 (à valider) |
| Paiements d'un enfant | `portail/enfant-paiements.html` | V1.0 | H3 | fournie |
| Annonces | `portail/annonces.html` | V1.0 | H4 | fournie |
| Calendrier et convocations | `portail/calendrier.html` | V1.1 | 5.7 | dessinée par Claude en 5.7 d'après `portail/annonces` (à valider) ; codée en 5.7 ; la barre du bas a cinq entrées (Calendrier) |
| Notifications (cloche de l'en-tête) | `portail/notifications.html` | V1.1 | 5.5.2 | dessinée par Claude en 5.5.2 d'après `gestion/notifications` et `portail/annonces` (à valider) ; codée en 5.5.2 : `/notifications`. Écart : dans la barre du bas, « Annonces » prend le porte-voix (la cloche est celle des notifications) — les autres maquettes du portail montrent encore une cloche ; 5.6.1 : bloc « Que recevoir sur l'écran » en bas (paiement reçu, annonces de l'école) ; 5.6.2 : « Échéance proche » et « Retard de paiement » |
| Profil et coordonnées | `portail/profil.html` | V1.0 | H5 | fournie — codé en 4.4.5 avec le contact d'urgence à la place du « Téléphone secondaire » (pas de champ au modèle) |
| Vérification publique d'un reçu (`/v/{id}`) | `portail/verification-recu.html` | V1.0 | F4 | fournie |
| Scolarité d'un enfant | `portail/enfant-scolarite.html` | V1.2 | 8.8 | fournie |

### Console de la plateforme — `admin.mwangaza.school` (super-admin, son propre design)

Pas de menu latéral comme la Gestion : barre du haut bleu nuit (lignes de relief) (marque, pastille « Console », menu du compte), navigation dessous avec le repère lampe, contenu clair et large (styles de la coquille dans la page : `.ctop`, `.cmain`). Connexion : carte blanche sur fond bleu nuit, mêmes étapes que la Gestion (`gestion/connexion`, `gestion/connexion-double-authentification`), sans « Se souvenir de cet appareil ».

| Écran | Fichier | Lot | Réf. | État |
|---|---|---|---|---|
| Tableau de bord | `console/tableau-de-bord.html` | V1.1 | 5.2 | dessinée par Claude en 5.2.1 (à valider) ; codée en 5.2.1 ; carte « Plateforme » dessinée en PERF.5b (rôle des conteneurs, « Ce que ça veut dire », lien du guide) (menu réduit au tableau de bord, la santé du serveur en pastille dans l'en-tête de la page au lieu de la barre du haut) |
| Identité de la plateforme | `console/identite-plateforme.html` | V1.1 | 5.2.2 | dessinée par Claude en 5.2.2 (à valider) ; codée en 5.2.2, sans écart (sur téléphone, l'aperçu et les modifications passent sous le formulaire) ; champ « Nom pour la recherche » ajouté en WEB.1c (maquette d'abord, codé sans écart) ; carte « Adresse et réseaux sociaux » ajoutée en WEB.1d (maquette d'abord, codée sans écart) |
| Écoles | `console/ecoles.html` | V1.1 | 5.3 | dessinée par Claude en 5.3 d'après `gestion/superadmin-ecoles` (à valider) ; carte « Fonctions de l'école » (modules, M.1) dessinée après coup le 2026-10-13 ; codée en 5.3 en trois écrans (liste, `/schools/new`, fiche `/schools/<id>`) ; « Créer l'école » donne un mot de passe provisoire affiché une seule fois au lieu d'un lien d'activation (pas de SMS en V1) ; mise à jour en 4.15 (à valider) : onglets Réels · Essai · Démonstration, type d'espace à la création et sur la fiche, état « Arrêtée », « Arrêter » avec motif et « Relancer », filtre par état en liste déroulante (cinq états ne tiennent pas en boutons sur téléphone), chiffres sur l'onglet « Réels » seulement ; mise à jour en 4.16 (à valider) : « Supprimer » sur la fiche d'un espace d'essai ou de démonstration, confirmation en retapant le code, état « Suppression en cours » ; complétée en 4.17.2 (à valider) : formulaire court du type « Démonstration », avancement du remplissage, carte « Démonstration » (fiche d'accès, remettre à zéro) et fiche d'accès `/schools/<id>/access` — codées sans écart ; la fiche d'accès est le document du serveur montré dans la page |
| Comptes | `console/comptes.html` | V1.1 | 5.4.1 | dessinée par Claude en 5.4.1 d'après `console/ecoles` (à valider) ; codée en 5.4.1 en deux écrans (liste `/accounts`, fiche `/accounts/<id>`) ; les familles du portail ont leur propre carte au lieu de partager celle des écoles |
| Annonces aux écoles (et bandeau, liste dans la Gestion) | `console/annonces.html` | V1.1 | 5.4.3 | dessinée par Claude en 5.4.3 d'après `gestion/annonces` (à valider) ; codée en 5.4.3 : console `/announcements`, Gestion bandeau en haut du contenu et liste `/app/platform-news` (lien en bas du menu) ; pas de bouton « Aperçu » dans la console (le bandeau de la Gestion reprend le titre et la première ligne) ; choix des écoles par une recherche au lieu d'une liste |
| Appareils | `console/appareils.html` | V1.1 | 5.4.2 | dessinée par Claude en 5.4.2 d'après `console/comptes` (à valider) ; codée en 5.4.2 (`/devices`) ; sans compteur d'appareils sous la liste |
| Demandes de démonstration (site public) | `console/demandes.html` | Lancement | WEB.1d | dessinée par Claude en WEB.1d d'après `console/annonces` (à valider) ; codée en WEB.1d (`/demo-requests`) sans écart ; pied de liste : nombre de demandes, « Précédent / Suivant » seulement s'il y a plusieurs pages |
| Journal et sessions support | `console/journal.html` | V1.1 | 5.4.2 | dessinée par Claude en 5.4.2 (à valider) ; codée en 5.4.2 en deux onglets (`/journal`, `/journal/support`) ; sans compteur d'entrées sous la liste ; S.3.2 : carte « Alertes sur cet appareil » ajoutée au-dessus des onglets (pas dans la maquette), filtre « Type » complété (« Annonces », « Accès du super-admin ») |

### Site public de la plateforme — domaine nu (WEB.1a, 2026-10-17)

Dessiné par Claude d'après l'étude de 13 sites (`docs/claude/recherches/2026-10-17-site-public.md`) ; à valider. En-tête nuit collé en haut (menu par public, « Trouver mon école », « Demander une démo », menu `<details>` sous 1 024 px), pied nuit complet (contact, liens, langues, « © DTMS »), tous deux réécrits par `maquettes.py site`. Chaque animation est décrite dans un `.note` avec son rôle.

| Page | Fichier | Lot | Réf. | État |
|---|---|---|---|---|
| Accueil (+ bulletin officiel animé au nom de l'ITIG et carte « École pilote », 2026-10-18) | `site/accueil.html` | Lancement | WEB.1a | codé (WEB.1b) ; à valider |
| Pour les écoles (direction, comptable, caissier, enseignant ; mise en route) | `site/ecoles.html` | Lancement | WEB.1a | codé (WEB.1b) ; à valider |
| Pour les parents (ce qu'ils voient, activation, installation) | `site/parents.html` | Lancement | WEB.1a | codé (WEB.1b) ; à valider |
| Modules (catalogue, socle, prochainement) | `site/modules.html` | Lancement | WEB.1a | codé (WEB.1b) ; à valider |
| Démonstration et contact (formulaire, état « envoyée ») | `site/demonstration.html` | Lancement | WEB.1a | formulaire codé en WEB.1d sans écart (libellés : « Fonction », champs à 16 px pour que le téléphone ne zoome pas) ; « Suivez-nous » et réseaux du pied de page (WEB.1d) : cachés tant que l'identité n'a aucun lien |
| Trouver mon école | `site/trouver-mon-ecole.html` | Lancement | WEB.1a | codé (WEB.1b) ; à valider |
| Mentions légales et confidentialité | `site/mentions.html` | Lancement | WEB.1a | codé (WEB.1b) : une seule adresse, `/confidentialite/` y mène ; texte dans les traductions, pas dans la console ; à faire relire par un juriste |
| Images de partage (WhatsApp, Facebook, LinkedIn ; 1200 × 630, une par page et par langue) | `site/partage.html` | Lancement | WEB.1c | dessinée par Claude (à valider) ; codée en WEB.1c (Pillow, `core/share.py`), sans écart |

### Menu de la Gestion

Depuis le 2026-10-12 (5.7), la section Communication du menu compte trois entrées de plus (**Annonces au personnel**, **Calendrier**, **Convocations**) et la barre du portail une (**Calendrier**) ; `gestion/annonces` a le destinataire « Personnel » et « Circulaire à imprimer ». Le HTML de toutes les maquettes est à jour ; les captures PNG n'ont été refaites que pour les écrans nouveaux ou changés (les autres gardent l'ancien menu jusqu'à un passage complet de `node maquettes/outils/captures.mjs`). Depuis le 2026-09-26, le menu latéral compte 5 entrées de plus, pour les nouveaux écrans : **Crédits d'élèves** (Finances), **Demandes des parents** (Communication), **Paramètres de l'école**, **Comptes du personnel** et **Journal d'audit** (Paramètres). Le menu est identique sur toutes les maquettes (voir « Outils »). Le super-admin garde son propre menu.

## Outils (`maquettes/outils/`)

Aucune dépendance à installer (Python 3, Node 22 et Google Chrome de la machine).

| Commande | Effet |
|---|---|
| `python3 maquettes/outils/maquettes.py menu` | réécrit le menu latéral de toutes les pages Gestion depuis `MENU` (à lancer après avoir ajouté une entrée) |
| `python3 maquettes/outils/maquettes.py index` | régénère `index.html` depuis le catalogue `GESTION` / `PORTAIL` / `CONSOLE` / `SITE` |
| `python3 maquettes/outils/maquettes.py site` | réécrit l'en-tête (`<header class="sh">`), le pied (`<footer class="sf">`) et les icônes (`<svg data-ic="…"></svg>`) de chaque page `site/` |
| `node maquettes/outils/captures.mjs [fichier.html …]` | refait les captures PNG (téléphone 390 px et bureau 1440 px, pour les trois applications — le portail aussi depuis le 2026-10-14 ; tablette 820 px en plus pour le site public, en WebP) et **sort en erreur si un élément dépasse de l'écran** ; sans argument : toutes |

Pour dessiner un nouvel écran : d'abord regarder comment les grands logiciels font (skill `design`, « Méthode ») ; écrire la page avec la même coquille (`page_gestion`, `page_auth`, `page_portail` et `ic` dans `maquettes.py` ; une page du portail porte aussi la barre d'ordinateur `.dtop`), l'ajouter au catalogue, puis `index` et `captures`, et regarder les deux captures.

## Système de design

### Intention (refonte du 2026-10-14)

Recherche, références et raisons : `docs/claude/recherches/2026-10-14-refonte-design.md`. L'ancienne palette (basalte, beige, gris chauds) « ressemblait à l'IA » : l'identité est maintenant tirée du **lac Kivu** et du **drapeau du Congo**.

- **Nuit du Kivu** (bleu nuit) : barre latérale de la Gestion, en-tête et barre du haut du portail, barre de la console, panneau des connexions ; avec, en filigrane, les **lignes de relief** des volcans et des collines du Kivu (`assets/relief.svg`) : la signature de la marque.
- **Lumière** (jaune) = *mwangaza* : logo, repère de l'élément actif, compteurs, points d'attention. Jamais en texte sur fond clair ni en grande surface.
- **Bleu Kivu** : toutes les actions principales, liens, focus.
- Neutres froids, légèrement bleutés ; jamais de beige ni de gris chaud.
- Police **Atkinson Hyperlegible Next** (`assets/fonts/`, 400 · 600 · 700 · 800, embarquée pour le hors-ligne) : lisibilité pour des utilisateurs peu habitués à l'informatique et des écrans de faible qualité.
- Chiffres toujours **tabulaires** et alignés à droite.

### Couleurs (reportées dans le thème Tailwind / variables shadcn)

Le nom « Mwangaza », le symbole M-flamme et les couleurs `lamp` / `lake` sont les valeurs **de départ** de l'identité de la plateforme (5.1) : l'application lit le nom, le logo, l'icône et ces deux couleurs dans ses paramètres (défaut `#0B5FCC` / `#F2B632`, migré le 2026-10-14). Ajouts sans maquette : lien « Mentions légales » après les langues sous les connexions ; téléphone et e-mail du support sous « École suspendue » et « Aucune école à cette adresse ».

| Jeton | Valeur | Usage |
|---|---|---|
| `night` / `night-2` / `night-3` | `#0B1C35` / `#15294B` / `#213A63` | barres sombres / élément actif, encadré de l'école / bordures sur la nuit |
| `night-ink` / `night-soft` / `night-muted` | `#E6ECF5` / `#C3CFE0` / `#94A3BB` | texte sur la nuit / entrées du menu / libellés de section |
| `lamp` / `lamp-soft` | `#F2B632` / `#FEF5DA` | lumière / bandeaux de marque |
| `lake` / `lake-700` / `lake-100` / `lake-50` | `#0B5FCC` / `#08459A` / `#D4E3F9` / `#EAF1FC` | bouton principal, liens, focus (= `primary`) / survol / anneau de focus / sélection |
| `ink` / `ink-2` / `ink-3` | `#101828` / `#475467` / `#5B677A` | texte / secondaire / tertiaire (≥ 5:1) |
| `surface` / `card` / `table-head` | `#F3F5F9` / `#FFFFFF` / `#F7F9FC` | fond de page / cartes / en-têtes de tableau, pieds de carte |
| `line` / `line-soft` | `#E2E8F0` / `#EDF1F6` | bordures / séparateurs |
| `field` | `#7A8699` | bordure de champ (3,7:1 sur blanc) |
| `ok` / `ok-50` | `#127A48` / `#E8F6EE` | payé, à jour, succès |
| `due` / `due-50` | `#B42318` / `#FDECEA` | en retard, erreur, danger |
| `warn` / `warn-50` | `#985A06` / `#FEF3DC` | partiel, hors-ligne, avertissement |
| `chart-1` / `chart-2` | `lake` / `#C47F00` | séries d'un graphique (validées : daltonisme, contraste) |

### Formes et tailles

- Rayons : cartes 14 px, fenêtres 16 px, champs et boutons 8 px, pastilles arrondies. Ombres froides et discrètes (la bordure dessine la carte).
- Champs ≥ 40 px ; boutons 32 / 40 / 48 px, boutons de caisse 60 px et plus ; graisse 600 pour les boutons, onglets et libellés, 800 pour les grands nombres.
- Base 15 px ; titres de page 1,6 rem. Échelle de texte (rem) : .8 · .85 · .92 · 1 · 1,15 · 1,3 · 1,6 · 2 — aucune autre taille à l'écran, rien sous 12 px (impression : pt / px).

### Logo

Symbole **M-flamme** (*mwangaza* = la lumière) : un M **bleu nuit** épais (basalte jusqu'au 2026-10-14) surmonté d'une flamme, dans un carré arrondi jaune `lamp`. Forme pleine et fermée, lisible de 16 px (favicon) à 512 px (icône installée), la même sur fond sombre ou clair. Fichiers dans `assets/logo/` : `symbole.svg` (écrans, favicon ; classe `.mark`), `icone-application.svg` (icône installée), `icone-maskable.svg` (Android, plein cadre), `icone-apple.svg` (iPhone). Tailles : 36 px dans les barres (`.mark`), 48 px sur les connexions (`.brand.lg` + `.mark.lg`), 28 px dans une carte (`.mark.sm`).

### Adaptation à chaque écran

Chaque application a sa mise en page à trois largeurs (2026-10-14 : le portail n'est pas « que téléphone ») :

- **Téléphone (< 600 px)** : une colonne ; rangées et pieds de carte qui passent à la ligne ; grandes listes en **tableau empilé** (`.tbl.stack` + `data-label` : une carte par ligne — élèves, impayés) ; autres tableaux qui défilent dans leur carte (`data-wrap` pour un texte long) ; onglets qui défilent ; documents A4 en aperçu réduit ; actions de l'en-tête en deux colonnes ; portail avec sa barre du bas.
- **Tablette (600–1023 px)** : Gestion avec menu tiroir sous 900 px, grilles à deux colonnes ; portail élargi à 760 px, enfants deux par rangée.
- **Ordinateur (≥ 1024 px)** : Gestion avec barre latérale ; **portail avec barre du haut** (`.dtop` : marque, navigation, cloche, compte), en-tête = titre de la page, contenu jusqu'à 1 120 px sur deux colonnes (`.pgrid` ; `.pgrid.left` : résumé à gauche), 760 px pour lire (`.pbody.narrow`) ; connexions du portail en deux panneaux (`.phone.pauth`).
- Grilles : toujours `minmax(0, …)`. Dans l'application : `make apercu` (390, 820, 1440 px).

### Composants récurrents

Carte (en-tête / corps / pied sur fond gris clair), KPI (avec pastille d'icône `.chip`), tableau, pastille d'état (`ok`, `due`, `warn`, `info`, `gray`), bandeau (`info`, `warn`, `due`, `ok`, `lampb`), segmenté (piste grise, choix actif blanc), interrupteur, case à cocher, étapes, barre de progression, indicateur de synchronisation (toujours visible en haut de la Gestion).

Ajoutés le 2026-09-26 (fin de `assets/styles.css`) : écran hors application (`authgrid`), fenêtre de dialogue (`overlay` + `dialog`), frise chronologique (`tl`), codes à recopier (`codes`, `code`), cadre de téléphone et menu coulissant (`frame`, `drawer`, `scrim`), mise en avant du guide (`spot`, `coach`), notification passagère (`toast`), pastille de couleur (`swatch`), A4 à l'italienne (`a4 land`), bulletin officiel (`bul`, `idbox`), onglets-liens (`.tabs>a`). Ajoutés le 2026-10-14 : barre d'ordinateur du portail (`dtop`), colonnes du portail (`pgrid`, `pcards`), connexions du portail en deux panneaux (`pauth`), tableau empilé (`tbl.stack`), motif de relief (`relief`).

### Formats d'affichage

- USD : `1 234,56 $` (espace insécable pour les milliers, virgule décimale).
- FC : `1 260 000 FC` (sans décimales).
- Dates : `19/10/2026` ; heures : `10:42`.
- Noms d'élèves : NOM POST-NOM en majuscules, prénom en casse normale.
