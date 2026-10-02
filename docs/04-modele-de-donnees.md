# Modèle de données

Conventions : toutes les clés primaires sont des UUID v7 (`id`). Tous les modèles ont `created_at`, `updated_at`, `created_by` (rempli par les services ; vide pour ce que crée le système). **[T]** = hérite de `TenantModel` (champ `school`). **[G]** = global. **[I]** = immuable après création.

## 1. Plateforme et comptes

**School [G]** — `code` (sous-domaine, unique), `name`, `official_name`, `logo`, `logo_monochrome` (optionnel : logo noir et blanc pour les reçus thermiques ; sans lui, le logo s'imprime en niveaux de gris), `primary_color`, `timezone` (défaut `Africa/Lubumbashi`, Goma est en UTC+2), `enabled_currencies` (ex : `["USD","CDF"]`, au moins une), `default_currency` (parmi elles), `matricule_format`, `status` (`trial`, `active`, `suspended`), `plan` (offre, saisie à la main en V1.0), `trial_ends_on` (fin de l'essai), `paid_until` (payé jusqu'au), `network` (FK optionnelle vers `SchoolNetwork`), `settings` (JSON : règles configurables, dont les réglages du reçu).

Tout ce qui est propre à une école se règle ici, jamais dans le code (l'ITIG n'est que l'école d'exemple) :
- **Couleur** (`primary_color`, décision Q8) : choisie par l'école ; défaut = couleur Mwangaza `#0E5C6B` (`lake`). La couleur du texte posé dessus (blanc ou encre `#1A2233`, le plus contrasté des deux) est choisie automatiquement pour un contraste d'au moins 4,5 : 1 ; une couleur sur laquelle aucun des deux n'est lisible est refusée, avec une teinte voisine proposée (`apps/schools/colors.py`).
- **Logo** (`logo`) : PNG, JPEG ou SVG sans script, 1 Mo au plus ; servi par `GET /api/school/logo/`.
- **Fuseau horaire** (`timezone`) : appliqué à chaque requête sur l'adresse de l'école.
- **Suspendue** : plus personne ne se connecte à son adresse (ni le support), rien n'est supprimé ; elle reste visible, grisée, dans le choix de l'école (M2). Une école ne se supprime jamais.
- Changés par l'école (`school.configure`, M5) : noms, couleur, logo, fuseau, devises ; par le super-admin seulement : code, statut, abonnement. Création, identité, logo, suspension et réactivation vont dans le journal de l'école ; l'abonnement non.
- **Matricule** (`matricule_format`, C3, 1.7) : texte avec des variables — `{AAAA}` année de début de l'année scolaire, `{AA}` ses deux derniers chiffres, `{0000}` numéro (3 à 6 zéros = nombre de chiffres), `{OPT}` code de l'option de la classe ; hors des variables : lettres sans accent, chiffres, `-` `/` `.` `_` ; 60 caractères au plus. **Une année et un numéro obligatoires** : la séquence repart à 1 chaque année, sans l'année deux élèves auraient le même matricule. Classe sans option : `{OPT}` disparaît avec un séparateur voisin (`ITIG-{OPT}-{AAAA}-{0000}` → `ITIG-2026-0001`). Nouvelle école : `{CODE}-{AAAA}-{0000}` avec son code en majuscules. Changé avec `classes.manage` (écran « Organisation scolaire ») : vaut pour les matricules donnés ensuite, jamais pour les anciens ; noté au journal (`apps/schools/matricule.py`).
- **Reçu** (`settings.receipt`) : imprimante `thermal_58`, `thermal_80` ou `sheet` (imprimante ordinaire, feuille A4) ; sur feuille A4, taille du reçu `a6` (4 par feuille), `a5` (2 par feuille) ou `small` (≈ 10 × 7 cm, 8 par feuille), avec traits de découpe (but : un petit reçu à coller dans le cahier de l'élève) ; exemplaires : 1 (élève) ou 2 (élève + souche pour l'école) ; lignes d'en-tête `header` (adresse, téléphone, e-mail ; 5 au plus) et mention `footer`. Clés `printer`, `sheet_size`, `copies`, `header`, `footer` ; valeurs par défaut dans `apps/schools/receipts.py` ; changements au journal de l'école (3.2.1).

**PlatformSettings [G]** — identité de la plateforme (5.1), une seule ligne (clé 1) : `name`, `short_name` (sous l'icône de l'écran d'accueil), `logo` (comme le logo d'une école ; sans lui : la lampe), `icon` (PNG carré ≥ 512 px ; sans elle : l'icône de la lampe), `primary_color` (boutons et liens : contraste ≥ 4,5 : 1 avec sa teinte claire), `accent_color` (sur le menu sombre : contraste ≥ 4,5 : 1 avec le basalte), `support_phone`, `support_email`, `legal_notice`. Publique (écrans de connexion, manifestes, PDF). Modifiée par le super-admin seulement. Aucun texte ni gabarit n'écrit le nom de la plateforme.

**SchoolNetwork [G]** — promoteur ou coordination : `name`, `kind` (`promoter`, `religious_coordination`).

**User [G]** — `phone` (unique, format E.164, identifiant principal ; saisi aussi sous la forme nationale `0971234567`, indicatif par défaut 243), `email` (optionnel, unique — avec son usage), `last_name` (nom), `middle_name` (post-nom), `first_name` (prénom), `password`, `language`, `is_active`, `is_platform_admin` (super-admin : administration Django, double authentification toujours exigée ; aucun droit dans une école sans y avoir de rôle, hors session support « en tant qu'école »), `must_change_password` (mot de passe provisoire donné par l'école, à remplacer à la connexion), `totp_secret` (clé de double authentification, chiffrée avec une clé dérivée de `DJANGO_SECRET_KEY`), `totp_enabled_at` (vide = double authentification pas activée ; `totp_enabled` en est déduit), `totp_last_step` (dernière période de 30 s utilisée : un code ne sert qu'une fois). Double authentification exigée (B4) si le compte a, dans une appartenance active, un rôle portant l'un des droits `school.configure`, `roles.manage`, `audit.view` ou `finance.*` (§ 8). Une école gère l'appartenance ; elle ne modifie le compte lui-même (noms, téléphone, nouveau mot de passe provisoire, réinitialisation de la double authentification) que s'il ne sert dans aucune autre école et n'est pas celui d'un super-admin ; sinon, c'est le support de la plateforme (1.3).

**RecoveryCode [G]** — `user`, `digest` (empreinte HMAC-SHA256 avec la clé du serveur, unique : le code lui-même n'est pas gardé), `used_at`. 8 par compte, à usage unique, format `7KQ4-M2XP` ; remplacés tous ensemble quand la personne en demande de nouveaux ou change de téléphone.

**LoginFailure [G]** — `phone` (numéro tapé, au format E.164 s'il est valable), `ip`. Essais ratés (mot de passe, code de double authentification, mot de passe actuel) : 5 pour un numéro en 15 minutes → numéro bloqué 15 minutes ; 30 d'une même adresse IP → adresse bloquée 15 minutes. Effacés à la connexion réussie, purgés au bout d'un jour.

**Membership [G]** — `user`, `school`, `roles` (M2M `Role`, seulement des rôles de la même école : refusé aussi par la base de code), `is_active` (désactivé : plus aucun accès à cette école, le compte reste valable ailleurs), `last_login_at` (dernière connexion à l'adresse de cette école : l'école ne voit pas celles des autres). Unique (`user`, `school`). On ne supprime pas une appartenance, on la désactive. Une école ne voit jamais les autres écoles d'une personne.

**Role [T]** — `code` (rôle système : `head`, `cashier`… ; vide pour un rôle créé par l'école), `name` (vide pour un rôle système : l'interface affiche son nom traduit ; l'école peut le renommer, ex. « Préfet des études » ; obligatoire pour un rôle de l'école ; unique dans l'école), `is_system` (= a un `code` ; non supprimable), `permissions` (liste de codes du § 8). Les 9 rôles système (§ 8) sont copiés à la création de l'école. Un rôle de l'école ne se supprime que s'il n'est plus donné à personne. Aucun changement (permissions d'un rôle, rôles ou désactivation d'une personne) ne peut laisser l'école sans compte actif ayant `roles.manage`. Plusieurs personnes peuvent avoir le même rôle (l'ITIG a 2 directeurs des études). Un rôle propre à l'école (ex : « chef d'atelier » en attendant le module ateliers de la V2) est un rôle personnalisé créé par l'école (B2).

**Device [T]** (app `sync`) — `user`, `kind` (`browser`, `reader`), `label` (système et navigateur, ex : `Windows · Edge`), `prefix` (donné par le serveur : `P1`, `P2`…, unique dans l'école, jamais redonné, jamais égal au code d'une caisse), `cash_register` (FK optionnelle), `public_key` (clé publique ECDSA P-256 de l'appareil, SPKI en base64, pour vérifier la signature des reçus émis hors ligne), `session_key` (session fermée à la révocation), `last_seen_at`, `last_receipt_seq`, `revoked_at`. Créé par « Se souvenir de cet appareil » ; chacun voit et déconnecte les siens (M4) ; un responsable (`roles.manage`) voit et révoque ceux de l'école (« Appareils et synchro », 3.7.2). `last_seen_at` : chaque synchronisation le met à jour. Jamais effacé.

**AuditLog [T]** **[I]** — `actor` (vide pour une action du système), `action` (code `<domaine>.<événement>`, liste dans `apps/audit/actions.py`), `entity_type` (`accounts.role`…), `entity_id`, `entity_label` (nom de l'objet au moment de l'action ; vide pour un rôle système sans nom propre), `before`, `after` (JSON : seulement les champs changés, jamais de mot de passe, de code ni de clé), `ip`, `user_agent` (navigateur), `impersonated_by` (super-admin en session support « en tant qu'école » dans cette école, A3 ; il est aussi `actor` des actions de la session), `device` (appareil de caisse, ajouté en 3.3 avec `Device`, avec l'heure de l'appareil pour une action faite hors ligne). Ni modifiable ni effaçable, jusque dans la base (déclencheur PostgreSQL). Une action dans une école va dans son journal (connexion : école de l'adresse) ; un changement du compte d'une personne (mot de passe, double authentification) va dans le journal de chaque école où elle est active, sans dire où il a été fait. Lu avec `audit.view`.

## 2. Organisation scolaire

Changée avec `classes.manage` (directeur, directeur des études), en ligne seulement ; services dans `apps/schools/organisation.py`, chaque changement noté au journal (domaine `organisation`). On ne supprime que ce qui ne sert plus : la base protège ce qui est utilisé.

**AcademicYear [T]** — `name` (« 2026-2027 », unique dans l'école, par défaut d'après les dates), `starts_on` < `ends_on`, `is_current` (**une seule** année en cours par école, contrainte en base : celle des inscriptions et des écrans par défaut ; la première créée l'est d'office), `status` (`open`, `closed` : clôture avec la délibération, V1.2). Créée depuis un **modèle de découpage** (C1) : `secondary` (secondaire RDC : 2 semestres, chacun 2 périodes + examens), `trimesters` (3 trimestres, chacun 2 périodes + examens), `empty` ; en option, avec **les classes d'une autre année** (niveau, option, section, capacité ; pas les titulaires) — les barèmes en 2.5. Supprimée seulement si elle n'est pas en cours et n'a aucune classe (son découpage part avec elle). Dates changées : le découpage doit rester dans l'année.

**Term [T]** — `academic_year`, `kind` (`semester`, `trimester`, `period`, `exam`), `parent` (semestre ou trimestre, seulement pour une période ou des examens), `order` (place dans l'année, tous niveaux confondus ; unique par année, vérifiée à la fin de la transaction), `name` (**vide = nom traduit par l'interface** d'après le genre et la place : « Semestre 2 », « 3e période », « Examens du 1er semestre » ; l'école peut renommer), `starts_on`, `ends_on` (vides tant que l'école ne les a pas saisis ; dans l'année, début ≤ fin, dans leur semestre ou trimestre). Le découpage se remplace d'un seul envoi (`PUT …/terms/`) : 40 éléments au plus.

**Level [T]** — `name` (« 7e EB », « 3e », unique dans l'école sans tenir compte des majuscules), `cycle` (`primary`, `basic`, `secondary_general`, `secondary_technical`, `higher`, `vocational`), `order` (ordre choisi par l'école ; un nouveau niveau va à la fin).

**Track [T]** — option : `name` (« Électricité », unique), `code` (`ELEC` : 1 à 10 majuscules ou chiffres, unique ; sert au matricule `{OPT}`).

**ClassGroup [T]** — `academic_year`, `level`, `track` (optionnel), `section` (« A », en majuscules, vide s'il n'y a qu'une classe), `name` calculé (« 3e Électricité A », « 7e EB B »), `capacity` (1 à 1000, optionnelle), `homeroom_teacher` (FK `User`, optionnel : **une personne du personnel actif de l'école**, jamais un compte d'une autre). Unique (année, niveau, option, section), même sans option. Supprimée seulement sans élève (les inscriptions la protègent, 2.1). Un niveau ou une option utilisés par une classe ne se suppriment pas.

## 3. Élèves et familles

Décision Q10 (2026-09-26) : **chaque école a sa propre copie** de l'élève et de sa famille. Une correction faite par une école ne touche pas les autres, et une école ne voit jamais qu'un élève ou une famille existe aussi ailleurs.

**Student [T]** — identité de l'élève dans cette école : `last_name`, `middle_name`, `first_name`, `sex`, `birth_date`, `birth_place`, `nationality`, `origin_province`, `origin_territory`, `address` (JSON : commune, quartier, avenue, numéro), `photo`, `photo_consent`, `previous_school` (texte), `family`, `matricule` (unique dans l'école, donné à sa **première** inscription et **gardé toute sa scolarité** — décision du 2026-09-27 ; vide tant qu'il n'est pas inscrit ; corrigeable à la main).
Champs V1.3 (7.6) : `blood_group`, `allergies`, `special_needs`, `religion`, `official_id`.

**Family [T]** — `code` (code famille à 8 caractères, sans caractères ambigus, **unique sur toute la plateforme** : le portail le retrouve sans connaître l'école), `primary_user` (FK `User`, rempli à l'activation), `activated_at`. État du portail calculé, pas stocké (4.9) : suspendu (`portal_suspended_at`), sinon activé (`activated_at`), sinon numéro manquant (tuteur principal sans téléphone : activation impossible), code expiré (`code_expires_at` passé), sinon « pas encore activé » — seul cet état reçoit une lettre ou un message d'invitation.

**Guardian [T]** — contact d'une famille : `family`, `full_name`, `relationship` (`father`, `mother`, `guardian`, `grandparent`, `sibling`, `other`), `phone` (E.164), `email`, `is_primary` (**un seul** par famille : le premier si aucun n'est choisi), `is_emergency_contact`. Les tuteurs d'une famille se remplacent d'un seul envoi (10 au plus).

**Enrollment [T]** — inscription d'un élève pour une année : `student`, `academic_year`, `class_group` (de la même année ; `PROTECT` : une classe qui a des élèves ne se supprime pas), `status` (`active`, `transferred`, `dropped`, `excluded`, `graduated`), `enrolled_on`, `left_on` (rempli au départ, effacé au retour en `active`). **Une** par élève et par année. L'effectif d'une classe compte ses inscriptions `active`.

**MatriculeSequence [T]** — `academic_year`, `last_number` : dernier numéro de matricule donné dans l'année ; l'année est verrouillée pendant l'inscription (jamais deux fois le même numéro).

**StudentImport [T]** — import d'une liste (D1, 2.3) : `academic_year` (année des classes), `file_name`, `sheet_name`, `headers`, `rows` (lignes du fichier en texte ; **le fichier n'est pas gardé**, les lignes sont effacées à la fin de l'import), `mapping` (champ → colonne), `class_mapping` (classe du fichier → classe choisie à la main), `status` (`analysed`, `importing`, `done`, `failed`), `report` (totaux, classes du fichier, état de chaque ligne ; après l'import, seulement les lignes non importées), `created_count`, `finished_at`. Une analyse abandonnée est effacée après 2 jours.

Règles :
- Import (D1) : chaque ligne est prête, en avertissement (importée, à vérifier : doublon dans le fichier, date de naissance manquante, téléphone illisible) ou en erreur (pas importée : nom, sexe ou classe manquants ou inconnus, date impossible, matricule déjà pris ou répété, **élève déjà dans l'école** — un fichier importé deux fois ne crée aucun doublon). Les lignes au même tuteur (même nom et même téléphone) forment une famille ; jamais de rattachement automatique à une famille déjà dans l'école. Matricule du fichier gardé, sinon donné par la séquence de l'année. Journal : une entrée `students.student_imported` par élève.
- Doublon potentiel (dans l'école) : même `last_name` + `first_name` + `birth_date` (sans tenir compte des majuscules) → avertissement, pas de blocage : 409 `possible_duplicate`, puis nouvel envoi avec `allow_duplicate` après confirmation.
- Le matricule est généré à la **première** `Enrollment` de l'élève selon `School.matricule_format` : `{AAAA}` / `{AA}` = année de début de l'année scolaire, `{OPT}` = code de l'option de la classe, numéro = séquence par école et par année ; un numéro déjà pris (saisi à la main ou importé) est sauté. Réinscription : l'élève garde son matricule.
- Élève et inscription acceptent un `id` donné par l'appareil (UUID v7) : le même envoi rejoué renvoie ce qui existe (200) ; un `id` qui sert déjà ailleurs : 409 `id_taken`.
- Journal : domaine `students` (famille créée / modifiée, élève créé / modifié, inscrit, inscription modifiée).
- Un parent voit un élève si `student.family.primary_user == user`.
- **Parent avec des enfants dans plusieurs écoles** : un seul compte (`User`), relié à une famille par école. Il active son compte avec le code famille d'une école, puis ajoute chaque autre école avec le code famille qu'elle lui a remis (« Ajouter un enfant d'une autre école »). Jamais de rattachement automatique par numéro de téléphone : un numéro mal saisi par une école montrerait ses enfants à un inconnu. Le portail lit, pour ce compte seulement, les familles de chaque école et leurs données.
- Coordonnées changées par le parent dans le portail (H5) : une demande par école où il a une famille ; chaque secrétariat l'applique à sa propre copie.
- Transfert vers une autre école de la plateforme (8.7, V1.4) : l'école d'arrivée reçoit une copie du dossier ; les deux dossiers restent ensuite indépendants.

## 4. Finances

**Currency** — constantes (`USD` : 2 décimales, `CDF` : 0 décimale utile).

**ExchangeRate [T]** **[I]** — taux de l'année scolaire, saisi par le comptable et **fixe toute l'année** : `academic_year`, `from_currency` (`USD`), `to_currency` (`CDF`), `rate` (décimal, 6 chiffres après la virgule, tel que saisi : francs pour 1 dollar), `reason` (obligatoire pour une correction) ; qui et quand : `created_by`, `created_at`. Le taux en vigueur est la dernière ligne de l'année. Une correction en cours d'année ajoute une ligne : l'historique (qui, quand, ancien et nouveau taux) se lit dans la table et dans l'audit. Les paiements déjà faits gardent leur `rate_used`.

**FeeType [T]** — `name`, `category` (`tuition`, `registration`, `operating`, `ancillary`, `uniform`, `transport`, `canteen`, `extracurricular`, `official_exam`, `custom`), `funds_teacher_bonus` (bool), `accounting_code` (compte SYSCOHADA, optionnel), `is_active`. Pas de devise ici : elle est choisie dans chaque barème.

**FeeRule [T]** — barème : `academic_year`, `fee_type`, portée (`school`, `level`, `track`, `class_group` — un seul rempli ou aucun = toute l'école), `currency` (`USD` ou `CDF`, au choix pour chaque barème), `total_amount_minor`, `schedule_kind` (`installments`, `monthly`, `single`). Au plus un barème par type de frais et par portée dans l'année ; pour un élève, le barème applicable est le plus précis (classe, puis niveau, puis option, puis toute l'école). Au moins une tranche, somme des tranches = total (unique : une seule ; mensuel : une par mois, proposée par l'écran).

**InstallmentTemplate [T]** — tranches d'un barème : `fee_rule`, `label` (« 1re tranche »), `amount_minor`, `due_on`, `order`.

**StudentCharge [T]** — ce que doit un élève, créé automatiquement à partir des barèmes applicables quand il est inscrit (et recalculé si le barème change, tant qu'aucun paiement n'est affecté) : `enrollment`, `fee_type`, `label`, `amount_minor`, `currency`, `due_on`, `source` (`rule`, `custom`), `installment_template` (optionnel).

**Discount [T]** — `enrollment`, `fee_type` (optionnel = tous les frais, pourcentage seulement), `kind` (`amount`, `percent`), `percent` (entier de 1 à 100) ou `amount_minor` + `currency` (devise du frais, jamais plus que le frais), `reason_code` (`staff_child`, `sibling`, `scholarship`, `waiver`, `other`), `reason` (motif obligatoire) ; qui et quand : `created_by`, `created_at` ; retrait : `revoked_at`, `revoked_by`, `revoke_reason` (jamais effacée). Son effet n'est pas stocké : réparti à la demande sur les frais dus actifs (règles ci-dessous).

**CashRegister [T]** — caisse : `name`, `code` (`C1` : lettres majuscules et chiffres, unique dans l'école, fixé à la création car il entre dans les numéros de reçus), `is_active` (désactivée, jamais effacée).

**CashSession [T]** — ouverture d'une caisse par un caissier : `cash_register`, `cashier`, `device` (ouverte hors ligne), `opened_at`, `closed_at`. Une seule session ouverte par caisse et par caissier, sauf ouverture hors ligne, jamais refusée (3.8.2).

**Payment [T]** **[I]** — `id` (UUID client), `enrollment`, `cash_session`, `device` (appareil qui l'a encaissé hors ligne ; l'opération d'origine est dans `SyncOperation`), `cashier`, `received_amount_minor`, `received_currency`, `rate_used` (taux USD → CDF en vigueur à l'encaissement), `paid_at` (heure de l'appareil), `synced_at` (arrivée au serveur d'un paiement hors ligne), `receipt_number` (unique dans l'école ; en ligne, donné par le serveur : `{ÉCOLE}-{CAISSE}-{AA}-{séquence}`, AA = année scolaire de l'inscription ; hors ligne, préfixe de l'appareil, 3.3), `method` (`cash` en V1 ; `mobile_money`, `bank` plus tard), `note`. Le reçu n'est pas un modèle : c'est une vue imprimable du paiement (décision Q2).

**PaymentAllocation [T]** **[I]** — répartition d'un paiement : `payment`, `student_charge`, `received_minor` (part du montant reçu, dans la devise reçue ; somme des parts = montant reçu, sauf un paiement hors ligne qui dépasse ce que l'élève doit à son arrivée : le surplus n'est affecté à rien : il devient un `StudentCredit`), `amount_minor` (dans la devise de la charge, converti depuis `received_minor`).

**CancellationRequest [T]** — `payment`, `reason`, `requested_by`, `requested_at` (heure de l'appareil hors ligne), `device`, `status` (`pending`, `approved`, `rejected`), `decided_by`, `decided_at`, `decision_note`. Une seule demande en attente par paiement ; le paiement compte jusqu'à la décision (3.8.1).

**PaymentCancellation [T]** **[I]** — `payment` (unique), `receipt_number` (`ITIG-AN-26-000007`, série de l'école par année scolaire), `reason`, `requested_by`, `approved_by`, `approved_at`. Une ligne = une annulation validée (demande validée par un autre compte) ; le reçu d'annulation est sa vue imprimable.

**StudentCredit [T]** — argent reçu en trop (M14, 3.6.1) : `enrollment`, `origin` (`offline_surplus` : surplus d'un paiement hors ligne, `source_payment` ; `discount` : trop-payé qu'une réduction fait apparaître sur des échéances payées, `source_discount`), `amount_minor`, `currency` (celle de l'argent reçu ou du frais), `voided_at` / `voided_by` (réduction retirée : jamais effacé). Pas de `used_by_payment` : utiliser un crédit ne crée pas de paiement (décision du 2026-09-29).

**CreditAllocation [T]** **[I]** — part d'un crédit utilisée : `credit`, `student_charge` (même devise que le crédit), `amount_minor` ; qui et quand : `created_by`, `created_at`.

**CashClosing [T]** **[I]** — `cash_session`, une ligne par devise : `currency`, `expected_minor` (paiements de la session pas annulés à l'heure de clôture, calculé par le serveur), `counted_minor`, `difference_minor` (compté − attendu), `note` (explication, obligatoire en ligne s'il y a un écart), `closed_by`, `closed_at` (heure de l'appareil si hors ligne), `device`.

Règles :
- Reste dû d'une charge = `amount_minor` − réductions applicables − allocations de paiements non annulés − parts de crédits non annulés. Le payé d'une charge s'arrête à ce qu'elle doit : le reste (réduction accordée après paiement) est le crédit de l'élève ; payé + crédits = argent reçu.
- Crédit (M14) : créé au serveur quand un paiement hors ligne dépasse ce que doit l'élève, ou quand une réduction augmente le trop-payé (seulement l'écart, par devise) ; retirer la réduction annule ses crédits (ce qu'ils ont payé redevient dû). Le comptable (`finance.approve_cancellation`), ou le caissier au prochain paiement de l'élève (`finance.collect_payment`, 3.6.2 ; hors ligne : opération `credit.use`, répartie à nouveau par le serveur à l'arrivée), l'utilise sur les échéances de sa devise les plus anciennes (même ordre que la caisse), sans paiement ni reçu ; ce qui dépasse ce que doit l'élève reste à traiter (rien n'est converti) ; il peut aussi faire rendre l'argent par l'annulation du paiement d'origine (3.8). Jamais transféré à un autre élève en V1.0.
- Réductions d'un élève (E3) : par type de frais et devise, elles s'additionnent (pourcentage du total arrondi demi supérieur, montant dans la même devise), plafonnées au total, puis se répartissent au prorata des échéances actives (écart d'arrondi sur les dernières) ; elles suivent donc changement de classe, barème modifié et échéancier particulier.
- Répartition par défaut : charges non soldées dans la devise reçue d'abord (l'autre devise seulement si le caissier le demande), triées par `due_on` puis `fee_type`. Le caissier peut modifier avant validation (parts dans la devise reçue, chacune au plus le reste de sa charge). En ligne, un montant supérieur à ce que doit l'élève est refusé (le caissier rend la monnaie).
- Frais déjà payés, même en partie (paiement non annulé) : ils ne bougent plus (barème modifié, changement de classe, échéancier particulier). Au changement de classe, une tranche payée tient la place de la tranche de même rang et de même devise de la nouvelle classe, qui n'est pas ajoutée (décision du 2026-09-28).
- Un paiement dans une devise différente de la charge (décision Q4) : `rate_used` est toujours dans le sens USD → CDF, tel que saisi. Dollars vers francs : `allocation = received × rate_used` ; francs vers dollars : `allocation = received ÷ rate_used`, division en `Decimal` (jamais `× 1/rate`). Arrondi demi supérieur à l'unité de la devise de la charge (centime pour USD, franc pour CDF).
- Échéancier particulier d'un élève (E4, décision Q1) : pas de modèle `PaymentSchedule` ; ce sont des `StudentCharge` avec `source=custom`.
- En retard : `due_on` < aujourd'hui et reste dû > 0.
- Aucune suppression physique dans ce module.

## 5. Notifications et annonces

**Announcement [T]** — `title`, `body`, `audience` (`all_families`, `class_groups` ; `staff` avec 5.8), `class_groups` (une ou plusieurs classes de l'année en cours), `attachment` (PDF, 5 Mo, jamais public), `published_at`, `archived_at`, `archived_by`. Publiée dès sa création, jamais modifiée ensuite (des familles l'ont peut-être lue) : on l'archive (retirée du portail) et on en publie une autre. Familles touchées : celles qui ont un enfant inscrit (actif) cette année dans les classes visées ; une fratrie compte une fois (4.3). Le portail montre à une famille les annonces non archivées qui la visent, publiées après la fin de l'année scolaire précédente (4.4.4).

**AnnouncementRead [T]** — `announcement`, `family`, unique ensemble ; `created_at` = lue le. Écrite quand l'annonce s'affiche dans le portail ; « lue par N familles » dans la Gestion (4.4.4).

**PushSubscription [G]** — `user`, `endpoint`, `keys`, `user_agent`, `created_at`.

## 6. Synchronisation

**SyncOperation [T]** — `op_id` (unique dans l'école), `device`, `type` (`payment.create`, `cash_session.open`, `payment.reprint`, `credit.use`, `cancellation.request` ; clôture en 3.8.2), `payload`, `status` (`applied`, `rejected`), `result` (résultat ou erreur, rendu tel quel au second envoi), `created_at` (arrivée).

**ChangeLog [T]** — une ligne par entité, sa dernière modification : `seq` (croissant par école, donné à la lecture sous verrou, jamais repris), `pending` (changement en attente de son numéro), `entity_type` (`enrollment` : élève, classe, frais dus, paiements de l'année ; `config` : école, reçus, année, classes, types de frais, caisses, taux), `entity_id`, `operation` (`upsert`, `delete`), `updated_at` (heure du changement). Écrit par signaux Django, et explicitement après une écriture en masse (`apps/sync/changes.py`).

## 7. Paie — V1.3 (aperçu)

**Employee [T]** — `user` (optionnel), identité, `function`, `hired_on`, `secope_number`, `secope_status` (`mechanized`, `new_unit`, `unpaid`), `qualifications`.
**Contract [T]** — `employee`, `kind`, `starts_on`, `ends_on`, `base_salary_minor`, `currency`.
**PayrollPeriod [T]** — `month`, `status` (`draft`, `validated`, `paid`).
**PayrollLine [T]** — `period`, `employee`, `base_minor`, `bonuses` (JSON), `teacher_bonus_minor`, `advances_deducted_minor`, `other_deductions` (JSON), `net_minor`, `currency`.
**SalaryAdvance [T]** — `employee`, `amount_minor`, `granted_on`, `repayment_plan`.

## 8. Permissions V1.0

9 rôles système (décision Q3) : `head` (directeur), `study_director` (directeur des études), `discipline_master` (directeur de discipline / surveillant), `accountant` (comptable), `cashier` (caissier), `secretary` (secrétaire), `promoter` (promoteur), `teacher` (enseignant), `parent`. Chaque école peut modifier les permissions de ses rôles et en créer d'autres (B2).

| Code | Directeur | Dir. des études | Dir. de discipline | Comptable | Caissier | Secrétaire | Promoteur |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `school.configure` (nom, logo, couleur, devises, reçus) | ✔ | | | | | | |
| `classes.manage` (année, périodes, niveaux, options, classes, matricule) | ✔ | ✔ | | | | | |
| `roles.manage` (rôles et comptes du personnel) | ✔ | | | | | | |
| `students.view` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `students.edit` | ✔ | ✔ | | | | ✔ | |
| `students.import` | ✔ | | | | | ✔ | |
| `finance.configure_fees` | ✔ | | | ✔ | | | |
| `finance.set_exchange_rate` | ✔ | | | ✔ | | | |
| `finance.grant_discount` | ✔ | | | ✔ | | | |
| `finance.collect_payment` | | | | ✔ | ✔ | | |
| `finance.request_cancellation` | | | | ✔ | ✔ | | |
| `finance.approve_cancellation` | ✔ | | | ✔ | | | |
| `finance.close_register` | | | | ✔ | ✔ | | |
| `finance.view_reports` | ✔ | | | ✔ | | | ✔ |
| `announcements.publish` | ✔ | ✔ | ✔ | | | ✔ | |
| `audit.view` | ✔ | | | | | | ✔ |

- Codes et rôles système dans `backend/apps/accounts/roles.py` ; un test compare ce tableau au code. Vérification par le serveur sur chaque point d'API (`HasSchoolPermission`) : compte actif, appartenance active dans l'école de l'adresse, un rôle qui porte le code, et une session passée par la double authentification si les droits dans cette école l'exigent. Le super-admin n'a aucun droit dans une école hors session support « en tant qu'école » (1.5 : motif, une heure au plus, droits de l'école sauf `finance.collect_payment`, `finance.request_cancellation`, `finance.approve_cancellation`, `finance.close_register`, chaque action notée dans le journal de l'école).
- **Double authentification** (B4) : exigée pour qui a, dans une école, l'un des droits `school.configure`, `roles.manage`, `audit.view` ou `finance.*` (`TOTP_PERMISSIONS` dans `roles.py`). Par défaut : directeur, comptable, caissier, promoteur (un test le vérifie) ; un rôle créé par l'école avec l'un de ces droits l'exige aussi. Nouveau droit sensible (ex. `grades.validate`, V1.2) : l'ajouter à cette liste.
- **Enseignant** : aucune permission en V1.0 (B1). **Parent** : aucune permission dans la Gestion ; le portail lui montre ses enfants (§ 3).
- Permissions des deux rôles ajoutés le 2026-09-26 (proposition de Claude, validée par la fusion de la PR) : en V1.0, le directeur des études s'occupe des classes et des inscriptions, le directeur de discipline consulte les élèves ; aucun des deux ne touche à l'argent. Prévu ensuite : `attendance.manage` (pointage, V1.1–V1.2) et `discipline.manage` (V1.2) pour le directeur de discipline ; `courses.configure`, `grades.validate`, `report_cards.publish` et `deliberation.manage` (V1.2) pour le directeur des études, avec double authentification obligatoire dès qu'il valide des notes.
