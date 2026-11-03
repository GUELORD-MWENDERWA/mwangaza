# Équipements : sonnerie, lecteurs de présence et réseau (lot 16)

Décidé le 2026-11-03. Mwangaza englobe désormais deux projets existants : la **sirène automatique** (`sirene_automatique_pro_esp32` : firmware ESP32, planificateur, DS3231, relais, TFT, Firebase) et le **système de présences RFID ULPGL 001** (`gestion_presence_rfid_university_ulpgl_001` : lecteur ESP32 + RC522, séances, Firebase). On **reprend leur logique et leur matériel**, on **remplace Firebase** par l'API Mwangaza (multi-écoles, audit, permissions) et on ajoute un **réseau d'appareils** maîtrisé de bout en bout. Le code d'origine reste la référence ; rien n'est recopié sans être relu.

## 1. Principe produit : l'école achète des modules

| Module | Ce que l'école voit | Dépend de |
|---|---|---|
| `bell` — Sonnerie automatique | **Seulement** : Sonnerie (horaires, calendrier, sonner maintenant, journal) et Équipements. Aucun élève, aucune classe. | rien |
| `attendance` — Présences | Élèves, enseignants, cours, séances, cartes, lecteurs, justifications, rapports. Pas la sonnerie. | `students`, `academics` |
| les deux | les deux entrées, sur le **même** appareil | — |

- **Équipements** (liste, jumelage, état, réglages, journal) est un socle **dérivé** : visible dès qu'un des deux modules est pris, jamais vendu à part (`accounts/modules.py`, module interne `equipment`, sans case dans la console).
- **À la création d'une école**, la console propose des **forfaits de départ** (Sonnerie seule · Présences · Gestion complète · Sur mesure). Chaque module porte une fonction `setup(school)` (registre `MODULE_SETUP`) qui crée ses **réglages par défaut** (profil « Normal » et créneaux types pour `bell` ; seuils et retard toléré pour `attendance`). Activer un module plus tard l'appelle une fois ; le désactiver ne supprime rien (règle M.1).
- Le **premier écran après connexion** dépend des modules : une école « Sonnerie seule » arrive sur Sonnerie ; menus, recherche, tableau de bord, rôles proposés et permissions sont filtrés par module (déjà vrai côté serveur depuis M.2 ; à vérifier écran par écran).
- Rôles utiles pour `bell` : `bell_operator` (sonner, alerte), `bell_admin` (horaires) ; l'**administrateur principal** garde tout. Pas de rôle « enseignant » obligatoire pour une école sans élèves.

## 1 bis. Tout suit les modules choisis (décidé le 2026-11-03)

**Règle générale** : une école ne voit, ne remplit et ne configure que ce qui concerne ses modules **et les modules dont ils dépendent**. Ce qui n'en dépend pas n'apparaît ni dans les menus, ni dans les formulaires, ni dans les paramètres, ni dans les imports et exports, ni dans l'aide, ni dans les documents.

- **Registre unique** (`accounts/modules.py`) : chaque **champ**, **section de paramètres**, **règle**, **rôle**, **widget du tableau de bord**, **document** et **étape de première configuration** déclare le ou les modules qui en ont besoin. Un seul test (`school.applies(feature)`) décide partout : serveur (sérialiseurs, validations, imports, exports), `/me` (menus) et interface. Le front ne fait que masquer ; le serveur **n'exige jamais** un champ qui ne s'applique pas à l'école et refuse d'écrire ceux qui ne s'y appliquent pas.
- **Exemples** :

| Donnée | Demandée seulement si l'école a… |
|---|---|
| Nom, sexe, classe, photo, carte | `attendance` ou `students` (minimum d'une fiche élève) |
| Téléphone du parent (alertes d'absence) | `attendance` avec notifications, `portal`, `finance` |
| Numéro d'identification (EPST) et **numéro permanent**, lieu et date de naissance, nationalité, province d'origine | `academics` (en-tête du bulletin) |
| École précédente, pièces d'inscription | inscriptions (lot 14) |
| Barème des frais, devises, formats de reçu, caisses | `finance` |
| Barème des notes, périodes, règlement des études | `academics` |
| Grille horaire, salles | `timetable` (la **sonnerie** a ses propres créneaux et n'a besoin ni de classes ni d'élèves) |
| Années scolaires et classes | tout module qui touche des élèves (`students`, `attendance`…), **pas** `bell` seul |
| Horaires de sonnerie, zones, calendrier | `bell` |
| Seuils de présence, retard toléré, lecteurs | `attendance` |

- **Création d'une école (console)** : identité + forfait/modules, puis **seulement** les réglages de ces modules ; ajouter un module plus tard ouvre ses réglages et sa première configuration. Une **liste de première configuration** (à cocher) par module remplace la page de réglages générale : Sonnerie = horaires, calendrier, jumeler la console, essai de sonnerie ; Présences = année, classes, élèves, cartes, lecteurs, première séance.
- **Rôles proposés, tableau de bord, recherche, notifications, guides et articles d'aide** sont filtrés de la même façon. Premier écran après connexion : celui du module principal.
- **Données déjà saisies** : retirer un module ne supprime rien ; ses champs redeviennent visibles à la réactivation.
- **Tests** (une matrice, pas une pile) : pour chaque forfait (Sonnerie seule, Présences seules, Gestion complète) : menus de `/me`, création d'un élève avec le minimum de champs (aucun numéro permanent exigé en Présences seules), 403/404 sur les points d'API des autres modules, export sans colonnes hors module, isolation entre écoles.

## 2. Matériel

### 2.1 Trois familles d'appareils (une seule carte logicielle commune)

| Type (`Equipment.kind`) | Carte | Rôle |
|---|---|---|
| `console` (**principal**) | ESP32 (NodeMCU-32S) + **Arduino Uno + shield TFT tactile** + DS3231 + relais sirène + buzzer + RC522 | Appareil central de l'école : sonnerie autonome **et** lecteur de présence. Sert aussi de **passerelle** vers internet. |
| `reader` | ESP32 **ou** ESP8266 + RC522 + 4 LED + buzzer | Lecteur de présence dans une salle ; commande aussi un avertisseur local. |
| `sounder` | ESP32 ou ESP8266 + relais 220 V | Sirène déportée : sonne en même temps que la console (secondaire). |
| `relay` | ESP32 ou ESP8266 seul | Répéteur : prolonge la portée entre des bâtiments éloignés. Aucun capteur. |

Tout appareil est **configurable, paramétrable et gérable** (CRUD) depuis la Gestion : nom, salle, type, version du micrologiciel, dernière vue, qualité du signal, réglages (volume, couleurs, délais), état « actif / retiré ».

### 2.2 Console : ESP32 + Uno + shield TFT

- **ESP32 = cerveau** : horloge, planificateur, relais, RFID, réseau, stockage (LittleFS), OTA. **Autonome** : l'Uno éteint ou débranché ne change rien aux sonneries.
- **Uno + shield TFT = terminal d'affichage et de saisie** (« HMI ») : dessine l'écran et lit le tactile ; **lecteur de carte SD du shield utilisé** (jusqu'ici abandonné) pour :
  1. une **copie de secours** du planning, de la liste des étudiants attendus et des réglages (ré-injectée à l'ESP32 si sa mémoire est corrompue) ;
  2. le **journal circulaire** des événements et le **tampon des pointages** quand le réseau est coupé longtemps (l'ESP32 n'a que 384 Ko de LittleFS) ;
  3. les images (logo de l'école, 240×320) et, plus tard, des sons.
  Fichiers à écriture en ajout seulement, CRC par enregistrement, rotation par jour (`/J/2026-11-03.log`).
- **Liaison ESP32 ↔ Uno** : UART matériel (D0/D1 de l'Uno) à **57 600 bauds**, trames `STX | type | longueur | charge | CRC16 | ETX`, accusé de réception et renvoi ; l'ESP32 est **maître**. Adaptation de niveau obligatoire : Uno TX (5 V) → ESP32 RX par **pont diviseur ou module bidirectionnel** ; ESP32 TX (3,3 V) → Uno RX direct. L'Uno est alimenté en 5 V par la carte, l'ESP32 jamais en 5 V sur ses GPIO.
- **Contraintes de l'Uno à respecter (2 Ko de RAM, 32 Ko de flash)** : écrans décrits par **tables en flash** (`PROGMEM`), aucun `String`, une seule police, redessin partiel ; les données affichées viennent de l'ESP32 par trames courtes. Le shield occupe D2–D9 (bus 8 bits) et A0–A4 (commande, tactile) et la SD D10–D13 : **seul A5 reste libre** ; D0/D1 sont donc réservés à la liaison (débrancher le fil TX pendant le téléversement de l'Uno, ou téléverser avant de câbler).
- **Point à valider au banc (tâche 16.0 de la partie ③)** : le débit réel d'un redessin complet, l'écriture SD pendant un redessin (partage du SPI), la lisibilité en plein soleil. Si l'Uno est trop juste, repli prévu : écran piloté directement par l'ESP32 comme dans le projet d'origine (brochage 8 bits déjà documenté) — la couche `ui/` du firmware ne change pas, seul le « pilote d'écran » change.

### 2.3 Lecteur de salle

ESP32 ou ESP8266 + RC522 + LED (verte OK, orange déjà passé, rouge refus, bleue prêt/attente de carte) + buzzer, bouton (appui long = réglage). Signalisation reprise du projet ULPGL **et améliorée** : voir § 2.3 bis. **Il décide seul** à partir de la liste de la séance reçue ; un tap n'attend jamais le réseau.

### 2.3 bis Signalisation : LED et buzzer (reprise de ULPGL, améliorée)

Source : `rfid_attendance_Nth/src/main.cpp` (tableaux `Etape {leds, fréquence, durée}` joués sans `delay`, trois priorités). On **garde** ce principe et le vocabulaire (vert = OK, jaune = attention, rouge = refus, bleue = réseau) ; on **améliore** :

| Amélioration | Pourquoi |
|---|---|
| **Un seul catalogue de signaux** (`signals.h`), commun au lecteur, à la console et au sounder, avec le même code de sons ; il vit dans le dépôt, pas dupliqué par firmware | ULPGL avait ses tableaux dans un seul fichier ; ici trois appareils doivent sonner pareil |
| **Le rythme dit le sens, pas la couleur seule** (1 bip = OK, 2 bips = déjà passé, bip long = refus) | une personne daltonienne ou une salle en plein soleil reconnaissent encore le signal |
| **Volume et mode muet réglés depuis la Gestion** (par appareil, par plage : silencieux en examen, plus fort dans l'atelier) ; les alertes graves (serveur perdu, batterie faible) restent audibles sauf choix contraire | ULPGL : `SONS_ETAT` compilé en dur |
| **Sons d'état coupés la nuit** (plage « nuit et congés », § 2.5 bis) ; le résultat d'une carte et l'alerte gardent leur voyant | pas de bip de vie |
| **Priorités : alerte > résultat de carte > événement > état**, un signal en attente par niveau, un résultat de carte annule les événements en attente | ULPGL en avait trois ; on ajoute l'alerte (sirène manuelle, batterie, appareil perdu) |
| **Deux familles de refus** : « carte inconnue » (2 bips longs) et « pas dans cette séance » (1 bip long), toutes deux avec le **motif lisible à l'écran de la console** | l'élève comprend quoi faire |
| **Signal « sans séance ouverte »** (jaune + bip moyen) conservé ; **« séance fermée »** et **« séance ouverte »** par deux notes montantes/descendantes | repris tel quel |
| **Test de démarrage et mode « essai »** (appui long, depuis la console) : chaque LED et chaque note, pour vérifier le câblage sans ouvrir le boîtier | repris, rendu déclenchable à distance |
| **Pas de blocage** : seuls le démarrage et l'effacement utilisent des pauses ; un tap n'attend jamais un signal | repris |
| **Signal hors-ligne explicite** : jaune fixe + « tic » = carte gardée, envoi en attente ; vert = enregistrée et déjà synchronisée n'existe plus (le lecteur décide seul, § 2.3) | la décision locale remplace l'attente du serveur d'ULPGL |

Signaux de base (à confirmer au banc, fréquences d'ULPGL gardées) :

| Situation | LED | Son |
|---|---|---|
| Présence enregistrée | vert 1 s | 1 bip aigu (2 500 Hz, 180 ms) |
| Déjà passé | orange 1 s | 2 bips courts (1 800 Hz) |
| Séance non ouverte | orange 1 s | 1 bip moyen (1 200 Hz, 500 ms) |
| Carte inconnue | rouge 1 s | 2 bips longs (2 000 Hz, 300 ms) |
| Pas inscrit à cette séance | rouge 1 s | 1 bip long (1 500 Hz, 700 ms) |
| Console injoignable (secondaires) | rouge clignotant | 3 bips graves (1 000 Hz) |
| Lecteur RFID en panne | rouge/orange alternés | 2 bips graves (500 Hz) |
| Jumelage ouvert / réussi / refusé | bleu rapide / vert 1 s / rouge | 3 bips aigus / bip long / bip grave |
| Batterie faible, appareil perdu, sonnerie manuelle | selon l'événement | motif propre, jamais confondu avec un résultat de carte |

Les motifs sont des **données** (liste d'étapes `{leds, fréquence, durée}`) : un nouveau signal s'ajoute sans toucher à la logique. Le buzzer est un buzzer **passif** piloté en PWM (`ledcWriteTone`), comme ULPGL, pour pouvoir jouer des notes.

### 2.4 Lecteur de cartes (V1) et antennes

- **V1 : RC522 (MFRC522, 13,56 MHz)**, bibliothèque `MFRC522` déjà utilisée par le projet ULPGL. Il lit le numéro unique (UID) des cartes MIFARE et des NTAG215/216, ce qui suffit : la carte est une clé d'identité, rien n'est écrit dedans. PN532 seulement si un jour on veut écrire des données ou lire des téléphones (V2).
- **Antennes** : un module à antenne externe (ESP32 « U », connecteur U.FL, 3 à 5 dBi) augmente la portée de **chaque lien**, il ne supprime pas les relais : un mur de béton coûte 10 à 20 dB, une antenne en gagne 3 à 5. Effet réel : moins de relais, ou des liens plus fiables entre bâtiments. La puissance d'émission est réglable par appareil (économie de batterie quand le lien est bon). La portée se **mesure** sur le site (qualité du lien affichée dans Équipements) avant de décider d'un relais.
- **SD** : à tester d'abord **branchée directement sur l'ESP32** (broches SD du shield accessibles, SPI 3,3 V, sans protocole série) ; repli : via l'Uno.

### 2.5 Alimentation : secteur, batterie, ou les deux

Chaque appareil fonctionne **avec la batterie seule, avec l'adaptateur 5 V seul, ou avec les deux** (l'adaptateur alimente et charge, la batterie reprend sans coupure). Le système est **entièrement piloté** : l'ESP32 voit la source, la charge, la tension et la température, et commande la charge.

- **Chaîne** : adaptateur 5 V → **chargeur avec chemin de puissance** (type BQ24074 : l'appareil est alimenté pendant la charge, courant limité, thermistance, signaux d'état) → cellule Li-ion 1S (18650 protégée, BMS à protection surcharge, décharge profonde, court-circuit) → 3,3 V pour l'ESP32, le RC522 et l'horloge (convertisseur élévateur-abaisseur, bon rendement entre 3,0 et 4,2 V) et un **5 V commutable** pour l'Uno/écran et le relais. Un simple TP4056 sans chemin de puissance est refusé : il charge mal quand l'appareil consomme.
- **Pilotage par l'ESP32** : lecture de la tension (diviseur sur une entrée ADC1, filtrée) ; broche d'activation de la charge ; état de charge ; **arrêt de la charge à 4,1 V** (option « longue durée de vie », −10 % d'autonomie, cellule plus durable) ; **pas de charge sous 0 °C ni au-dessus de 45 °C** (Goma : boîtier au soleil = charge suspendue) ; coupure propre à 3,3 V (heure de coupure notée, relais ouvert, reprise automatique au retour du courant).
- **Économies** : écran (alimentation 5 V de l'Uno coupée par transistor, réveil au bouton ou à la carte) éteint après 30 s ; RC522 éveillé par courtes interrogations ; sur un **lecteur sur batterie**, l'ESP32 dort **hors des heures de séance** (réveil par l'horloge ; les séances viennent du planning) ; puissance radio réduite quand le lien est bon.
- **Autonomies attendues (estimations à mesurer au banc, cellule 3 000 mAh)** : console (radio toujours éveillée, écran éteint) ≈ 1 jour : **secteur recommandé, batterie = secours de plusieurs heures** ; lecteur sur batterie, éveillé 6 h par jour ≈ 1 semaine ; relais (toujours à l'écoute) ≈ 1,5 jour : secteur ou **petit panneau solaire 5 V** sur le même chargeur.
- **La sirène est alimentée en 220 V** (décidé le 2026-11-03) : le relais ne fait que **fermer un contact sec** sur son alimentation. Sans secteur elle est muette de toute façon : **une école « Sonnerie seule » n'a besoin d'aucune batterie** (adaptateur 5 V sur le même secteur ; la pile du DS3231 garde l'heure). La batterie est une **option** (secours pour les lecteurs et les relais, ou pour garder le journal et l'alerte « coupure » de la console). Au retour du courant, les sonneries **manquées ne sont pas rejouées** (tolérance de 30 s, ligne « manquée : coupure » au journal).
- **Sécurité 220 V** : contact sec d'un relais **250 V AC 10 A** ou d'un **contacteur** (sirène à moteur : courant d'appel, circuit RC en parallèle du contact), carte basse tension **séparée** du circuit secteur (isolation, distances de fuite, fusible, terre, boîtier fermé), câblage secteur par un électricien.
- **Remontée à la console** (`heartbeat`) : source (secteur / batterie), tension, pourcentage estimé, autonomie estimée, état de charge, température, nombre de coupures ; alertes « batterie faible », « sur batterie depuis X min », « défaut de charge » ; réglages (limite de charge, mise en veille) modifiables à distance. Tâche de banc : **mesure de consommation** de chaque type d'appareil (EQP.3).
- Sécurité de la cellule : fusible, protection contre l'inversion, cellule jamais chargée sans protection, boîtier ventilé ; alternative plus sûre et plus durable en chaleur : **LiFePO4** (3,2 V, 2 000 cycles), à comparer au banc.

#### Batterie 3S (BMS « 3S 10A » déjà disponible) et gestion de l'énergie

- **Console, relais, panneau solaire : pack 3S** (3 cellules 18650, 9 à 12,6 V, ≈ 33 Wh pour 3 × 3 000 mAh, trois fois la capacité d'une cellule seule) avec le BMS 3S 10A de l'utilisateur ; un abaisseur (type MP1584 / XL4015, 90 % de rendement) donne le 5 V, puis le 3,3 V. **Lecteurs sur batterie : une cellule 1S** (un pack 3S serait surdimensionné). Le pack 3S peut aussi alimenter une sirène 12 V.
- **À vérifier sur le module réel** (la plupart de ces cartes sont une *protection*, pas un chargeur) : sa charge demande une **source 12,6 V à courant limité** (un adaptateur 12 V ne charge pas à fond ; prévoir un chargeur 3S ou un 12 V + élévateur réglé à 12,6 V) ; fils d'équilibrage vers chaque cellule ; courant de décharge maxi 10 A, pas de courant de charge réglable ; pas de mesure de charge. Les cellules d'un pack sont de la même marque, du même lot et à la même tension à l'assemblage ; fusible sur le pack.
- **Pilotage ajouté par l'ESP32** (le BMS ne parle pas) : diviseur de tension sur une entrée ADC1 (12,6 V → < 3,3 V), capteur courant/tension **INA219** (I2C, intègre les mAh consommés → pourcentage et autonomie estimés), interrupteur MOSFET sur l'entrée de charge (suspendre la charge hors 0–45 °C ou à la limite choisie), thermistance sur le pack.
- **États d'énergie du micrologiciel** (machine d'états dans `lib/core`, testée sur PC) :

| État | Quand | Ce qui est éteint |
|---|---|---|
| `ACTIVE` | séance ou sonnerie en cours, interaction | rien |
| `IDLE` | rien à faire depuis 30 s | écran (alimentation 5 V de l'Uno coupée par transistor) ; radio en économie |
| `SCHEDULED_SLEEP` | lecteur sur batterie hors des heures de séance | tout sauf l'horloge ; réveil par l'alarme du DS3231 (broche SQW), un bouton, ou le RC522 (broche IRQ) ; **réveil de contrôle toutes les 5 min** pour recevoir les commandes (une radio en sommeil profond n'écoute pas) |
| `LOW_BATTERY` | < 20 % | écran, signalisation lumineuse réduite ; alerte envoyée ; la sonnerie continue |
| `SHUTDOWN` | < 3,3 V par cellule (< 9,9 V pour le pack) | tout ; heure de coupure notée ; reprise automatique au retour de l'adaptateur |

  Une console ne dort jamais profondément (elle est passerelle et sonnerie). **« Éteindre » depuis l'application** = veille jusqu'au prochain réveil planifié, car seul un interrupteur physique coupe vraiment l'alimentation.
- **Banc d'essai (EQP.3)** : consommation mesurée de chaque état et de chaque type d'appareil, avant de promettre une autonomie à une école.

### 2.5 bis Écran et voyants : ne rien consommer pour rien

L'écran du shield (rétroéclairage fixe, Uno et TFT ≈ 100 à 150 mA sous 5 V, soit plus que l'ESP32 au repos) est le premier poste à économiser. Règles du micrologiciel de la console :

- **Écran éteint par défaut.** Il s'allume sur un **réveil** et s'éteint après un délai : **30 s sur batterie, 2 min sur secteur** (réglable de 10 s à 10 min dans Réglages). Jamais éteint pendant un jumelage, une mise à jour ou une alerte qui demande une réponse.
- **Éteindre = couper le 5 V de l'Uno** par un transistor commandé par l'ESP32 (rétroéclairage non réglable sur ce shield, donc pas de « luminosité réduite »). Conséquence à connaître : **le toucher ne peut pas réveiller un Uno éteint**. Sources de réveil : un **bouton physique** (celui de la façade), la **présentation d'une carte** devant le lecteur de la console, un **événement** (alerte, sonnerie manuelle demandée depuis l'application, batterie faible, appareil perdu, jumelage demandé). Option plus économique à tester au banc : Uno en veille (≈ 5 mA) avec rétroéclairage coupé par un transistor ajouté sur la ligne LED du shield (modification matérielle légère), réveil au toucher ; retenue seulement si le banc le justifie.
- **Verrouillage avec l'écran** : le code PIN est redemandé après extinction ; aucune action sensible sans lui.
- **Dessin économe** : redessin **partiel** uniquement sur changement de donnée, aucune animation, aucune trame de rafraîchissement en continu ; l'ESP32 n'envoie à l'Uno que ce qui change et **n'envoie rien quand il est éteint** (pas de file d'attente d'écran). À l'allumage, un seul envoi de l'état complet.
- **Voyants** : une brève impulsion toutes les 5 s en veille (pas de LED fixe), éteints la nuit ; le signal d'une carte (vert, orange, rouge) reste complet ; le buzzer ne sonne que sur un événement (jamais de bip de vie).
- **Plage « nuit et congés »** (tirée du calendrier de l'école : soirs, fins de semaine, vacances) : écran et voyants éteints, synchronisation avec le serveur espacée (toutes les 5 min au lieu de 30 s), lecteurs en veille planifiée ; la sonnerie, elle, reste exacte.
- **Processeur et capteurs** : ESP32 à 80 MHz hors calcul lourd ; RC522 interrogé par courtes séquences avec l'antenne coupée entre deux ; capteurs de tension et de courant lus toutes les 10 s, pas en continu.
- **Mesure** (banc EQP.3) : consommation de la console écran allumé / éteint / Uno en veille, et gain réel de chaque règle ; on garde celles qui rapportent. Chaque appareil remonte à l'application le temps d'écran allumé et l'énergie estimée.

### 2.6 Alimentation et robustesse
Condensateur 470–1000 µF à l'entrée, relais sirène commandé par NPN avec tirage vers le bas (GPIO12 jamais haut au démarrage), watchdog, double copie des réglages avec CRC, mise à jour OTA avec retour arrière, autotest quotidien : repris tels quels de la sirène.

## 3. Réseau d'appareils (vue télécom / réseau / embarqué / logiciel)

### 3.1 Topologie

```
 Internet ── API Mwangaza (HTTPS) ── Routeur / WiFi de l'école ── PASSERELLE (console ESP32, mode STA)
                                                                      │ ESP-NOW (canal du routeur)
                                       ┌──────────────────────────────┼───────────────────────┐
                                    lecteur A                      RELAIS 1 ───────────── RELAIS 2 ── lecteur D
                                                                      │
                                                                  lecteur B
```

- **L'appareil principal (la console, avec l'écran) est la seule passerelle** de son site : seul à parler à l'API et seul à avoir une interface. Toute école a au moins une console ; un site éloigné peut avoir sa propre console (un autre *groupe*, vu séparément dans l'application). Pas de passerelle de secours automatique en V1.
- Les autres appareils parlent **ESP-NOW** (couche 2 du WiFi, sans point d'accès, portée ≈ 100–200 m en vue directe, plus avec antenne externe) vers leur **parent** (la passerelle, ou un relais). Pas d'internet côté capteur : pas de mot de passe WiFi à saisir sur chaque lecteur, un seul réglage WiFi par école.
- **Relais** : retransmet les trames d'un appareil éloigné (maillage multi-sauts, 4 sauts au plus). Un appareil choisit son parent selon la qualité du signal (RSSI) et le nombre de sauts jusqu'à la passerelle, et en change si le parent disparaît.
- **Repli sans routeur** : si la passerelle perd internet ou le WiFi, **le réseau local continue** (sonnerie, taps, séances ouvertes) ; les événements s'accumulent (§ 5) et partent au retour de la liaison.

### 3.2 Trame (couche liaison applicative)

`ver(1) | type(1) | école_courte(2) | src(4) | dst(4) | saut_restant(1) | seq(4) | charge(≤190) | tag(8)`
- **seq** par source, enregistré en mémoire non volatile par paquets de 16 ; **déduplication** par `(src, seq)` sur les relais et la passerelle (fenêtre de 64) : un renvoi ou deux chemins ne créent jamais de doublon.
- **Accusé de réception** de bout en bout pour les événements (pointage, journal) : l'appareil garde l'événement jusqu'à l'accusé de la passerelle, **après** l'accusé de l'API ; renvoi avec attente croissante.
- Types : `hello/join`, `heartbeat`, `event`, `ack`, `command`, `config`, `roster-chunk`, `ota-chunk`, `time`.
- Charges au-delà de 190 octets (liste d'une séance, firmware) : découpées en morceaux numérotés avec reprise des morceaux manquants.

### 3.3 Sécurité (le réseau est commercial : rien n'est « de confiance »)

- Chaque appareil a une **clé de 256 bits propre** (générée par le serveur au jumelage, jamais réutilisée, jamais journalisée, stockée en NVS) ; chiffrement et authentification des charges en **AES-128-GCM** (mbedTLS sur ESP32 ; bibliothèque légère équivalente sur ESP8266) avec **compteur anti-rejeu** ; une trame non authentifiée est ignorée sans réponse.
- La clé ESP-NOW native (limite de 10 pairs chiffrés) n'est **pas** utilisée : la sécurité est applicative, donc sans limite de pairs et indépendante du relais (un relais ne peut ni lire ni modifier ce qu'il transmet).
- **Jumelage (sans internet)** : sur l'écran de la console, « Ajouter un appareil » ouvre une fenêtre de 2 minutes ; sur l'appareil neuf, un appui long sur son bouton le met en jumelage. Les deux calculent un secret commun par échange de clés (X25519) et affichent le **même code à 6 chiffres** ; l'utilisateur le **compare et confirme sur l'écran** de la console. La console crée alors la clé de l'appareil et l'inscrit au serveur à la prochaine synchronisation. L'application web voit l'appareil et peut le renommer ou le retirer, mais **ne l'ajoute pas** à distance. Appareil retiré = clé révoquée, trames refusées.
- Passerelle ↔ API : HTTPS, jeton d'appareil + signature HMAC de chaque requête (horodatage, nonce) ; **toutes les écritures sont idempotentes** (règle 4) : chaque événement porte un **UUID v7 généré par l'appareil** (horloge DS3231 valide) ou, horloge douteuse, un UUID dérivé de `(appareil, seq)` marqué `clock_untrusted`.
- Toute commande envoyée à un appareil (sonner, alerte, réglage, mise à jour) a un **identifiant, une expiration** (une sonnerie de 10 min n'est pas exécutée à 14 h) et un **accusé** ; l'évacuation/alerte exige la permission dédiée et est journalisée.
- Micrologiciel : **signé** (clé publique de la plateforme dans l'appareil, ed25519), mise à jour par la passerelle puis relais en morceaux ; refus d'une version plus ancienne ; retour arrière si l'appareil ne confirme pas au démarrage.

### 3.4 Principal et secondaires (décidé le 2026-11-03)

L'utilisateur ne se connecte **qu'à la console**. Les appareils secondaires (`reader`, `relay`, `sounder`) n'ont **ni écran, ni page web, ni WiFi à régler, ni compte** : seulement un bouton (jumelage, appui long) et des voyants. Moins de code, moins de réglages sur le terrain, moins de surface d'attaque.

- **Tout passe par la console** : réglages, commandes, listes de séance, planning, mises à jour, remontée de l'état et des événements. L'application web agit sur les secondaires **par la console** (le serveur dépose la demande, la console l'exécute).
- **Mise à jour** : le serveur envoie le micrologiciel **signé** à la console (HTTPS), qui le **range sur la carte SD** (image de 1,3 Mo) puis le distribue aux secondaires en morceaux de 190 octets, chacun vérifié, signature contrôlée à la fin, partition de secours (A/B) et retour arrière. **Déploiement progressif** : un appareil d'abord, les autres quand il a confirmé ; progression visible à l'écran et dans l'application. **Mise à jour hors ligne** : fichier signé déposé sur la carte SD de la console. La console se met à jour elle-même de la même façon.
- **Fonctions locales de l'écran** (avec code PIN pour les actions sensibles : alerte, ajout ou retrait d'appareil, WiFi, mise à jour, avec blocage après essais ratés) : état de tous les appareils (signal, batterie, version), sonner maintenant, WiFi, jumelage, mise à jour.
- **Si la console est éteinte** : les secondaires continuent seuls (lecteurs : séance déjà reçue, événements gardés jusqu'à 2 000 en mémoire ; sonneries déportées : dernier planning reçu) et resynchronisent à son retour.
- **Type `sounder` (sirène déportée) : dans la V1**, voir § 3.6.

### 3.6 Sirène déportée (`sounder`, V1)

Un ESP32 (ou ESP8266) + un relais 250 V / 10 A (contact sec sur la sirène du bâtiment, même précautions 220 V qu'au § 2.5) + un DS3231 + deux voyants + un bouton de jumelage. Secondaire de la console (§ 3.4).
- **Synchronisation** : la console diffuse l'heure toutes les minutes (trame `time`, correction de la dérive à chaque trame, écart toléré < 1 s). Pour une sonnerie **immédiate** (« sonner maintenant », alerte), la console envoie « sonner à T + 300 ms » : la latence des sauts n'a plus d'effet, toutes les sirènes partent ensemble.
- **Autonome comme la console** : le sounder garde sa **copie du planning** et son propre DS3231 ; console éteinte ou hors de portée, il sonne seul à l'heure. Les sonneries manquées par coupure de courant ne sont pas rejouées (§ 2.5).
- **Zones** : chaque sounder a une zone (Bâtiment A, Atelier…). Un créneau de sonnerie cible « toutes les zones » (par défaut) ou certaines ; une alerte sonne partout. Réglé dans l'application (Sonnerie, créneau) et envoyé par la console.
- **Retour d'état** : accusé « sonnerie exécutée à HH:MM:SS » dans le journal des sonneries ; alerte « sirène déportée muette » si l'accusé manque ou si le sounder disparaît du réseau.
- Même mise à jour signée, même jumelage et même chiffrement que les autres secondaires. Un sounder sur secteur seul n'a pas besoin de batterie.

### 3.5 Hors V1 de la couche réseau
Passerelle de secours, bascule automatique entre deux consoles, 4G/GSM (V2).

## 4. Logiciel : serveur

Nouvelle application Django **`equipment`** (tout modèle d'école hérite de `TenantModel`) :

| Modèle | Rôle |
|---|---|
| `Equipment` | appareil : école, `kind`, nom, salle (`Room` de l'emploi du temps si présent), identifiant matériel, clé (chiffrée), version firmware, `last_seen`, RSSI, parent dans le maillage, `gateway`, `state` |
| `EquipmentPairing` | code de jumelage à usage unique avec expiration |
| `EquipmentCommand` | commande (type, charge, expiration, état : en attente / envoyée / exécutée / expirée) |
| `EquipmentEvent` | événement brut reçu (UUID v7, appareil, type, charge, heure appareil, `clock_untrusted`) ; table purgée après traitement selon S.7 |
| `FirmwareRelease` | version signée, canal (essai / stable), notes |
| `bell.*` | `BellProfile`, `BellSlot` (heure, durée, motif de son, jours), `BellException` (date → profil ou silence), `BellRing` (journal des sonneries réelles) |
| `attendance.*` | `AttendanceSession` (cours, salle, début/fin, liste figée), `AttendanceRecord` (élève, séance, heure, source : lecteur / téléphone / main), cartes (6.1) |

Principes :
- **API d'appareil** `/api/equipment/sync/` (une seule porte) : la passerelle envoie un lot `{events:[…]}` et reçoit `{commands:[…], config_rev, roster_changes:[…]}` ; réponse **delta par `rev`** comme la synchronisation de la Gestion (`/hors-ligne`). Pas de Firebase, pas de WebSocket permanent (charge serveur faible : un appel toutes les 10 à 30 s par passerelle, plus long si rien à dire).
- **Planning de la sonnerie** : source de vérité sur le serveur, **copie complète sur l'appareil** (JSON signé, versionné). Les créneaux peuvent venir de la **grille horaire de l'emploi du temps** (`TimeSlot`) quand l'école a ce module, ou être saisis seuls : une école « Sonnerie seule » n'a pas besoin de classes. Les jours fériés et congés viennent du **calendrier de l'école** (`SchoolEvent`), avec les jours fériés de la RDC en valeurs par défaut modifiables.
- **Présences** : le lecteur envoie le tap ; un service crée l'`AttendanceRecord` (idempotent par UUID), notifie les parents au besoin (lot 10), alimente les rapports. Une carte (6.1) est une clé d'identité unique par école ; les lecteurs et le pointage par téléphone (6.3) alimentent la **même** table.
- Tout changement d'appareil, de planning, de commande d'alerte ou de séance va dans l'`AuditLog` (règle 5). Isolation : un appareil ne lit et n'écrit que dans son école ; test dédié pour chaque point d'API.

## 5. Ce qui reste hors ligne (revue de développeur senior, 2026-11-03)

Le hors-ligne coûte cher : file d'opérations, conflits, stockage, tests. On ne le donne donc **que** là où il rapporte. Critères, dans l'ordre : (1) l'acte se fait à un **guichet, une porte ou une salle** où le réseau tombe ; (2) l'opération est un **ajout** (append-only) ou rejouable sans conflit (UUID v7, idempotente) ; (3) personne d'autre ne **dépend de son effet immédiat** ; (4) elle ne demande pas un **pouvoir central** (annulation, rôles, argent d'un tiers). Trois niveaux :

| Niveau | Contenu | Technique |
|---|---|---|
| **A. Écriture + lecture hors ligne** | actes de guichet et de porte, ajouts | file d'opérations (outbox) Dexie, UUID v7, rejouée sans doublon |
| **B. Lecture seule hors ligne** | consultation de ce qu'on a déjà ouvert ou du jour | cache de lecture, daté (« à jour depuis 14:02 ») |
| **C. En ligne seulement** | décisions centrales, tiers, calculs lourds | écran grisé avec explication, jamais de saisie perdue |

| Fonction (module) | Niveau | Décision et raison |
|---|---|---|
| Sonnerie (`bell`) | **A, sur l'appareil** | DS3231 + copie du planning ; ne dépend jamais du réseau |
| Pointage par lecteur (`attendance`) | **A, sur l'appareil** | séance reçue d'avance ; événements gardés (2 000) puis rejoués |
| Pointage par téléphone / tablette (`attendance`) | **A** | caméra QR/NFC ; même table que les lecteurs ; ajout seulement |
| Présence manuelle (appel en classe) | **A** | ajout ; une correction = nouvelle ligne au journal |
| Présence du personnel | **A** | même moteur que les élèves |
| Caisse : encaisser, reçu, clôture (`finance`) | **A** | **fait** (V1.0) ; numéro de reçu par appareil, signature du reçu |
| Frais, soldes d'un élève | **B** | lus au guichet ; recalculés au retour du réseau |
| **Annulation d'un paiement** | **C** | règle 3 : motif, permission dédiée, audit — jamais hors ligne |
| Dépenses, sorties de caisse (lot 7) | **A** | acte de guichet, ajout ; justificatif ajouté ensuite |
| Budget, rapports financiers | **B** | lourds ; lus si déjà ouverts |
| Fiches élèves, listes de classe (`students`) | **B** (+ **A** pour l'inscription d'un élève au guichet, lot 7) | la recherche d'un élève doit marcher partout |
| Modification d'une fiche (nom, famille) | **C** | risque de conflit entre deux postes ; peu urgent |
| Import Excel | **C** | gros fichier, aperçu serveur |
| Notes : saisie, conduite (`academics`) | **A** | l'enseignant saisit en salle ; une note = ajout versionné, dernière validée gagne, **validation et proclamation en ligne** |
| Bulletins, palmarès, délibération | **C** (lecture **B** d'un bulletin déjà ouvert) | calcul central ; PDF lourd |
| Emploi du temps : consulter (`timetable`) | **B** | l'horaire du jour de l'enseignant en cache |
| Emploi du temps : calcul, publication | **C** | optimisation serveur |
| Bibliothèque : prêt, retour, inventaire scanné (lot 11) | **A** | guichet ; ajouts ; conflit « livre déjà prêté » résolu au rejeu et signalé |
| Ateliers : sortie et retour d'outils (lot 11) | **A** | idem |
| Catalogue, acquisitions, fiches d'inventaire | **C** | bureau |
| Annonces, circulaires, convocations (`communication`) | **B** (lecture) | l'envoi est **C** (un tiers doit le recevoir) |
| Messagerie, rendez-vous, mérites, sanctions (lot 13) | **C** (brouillon gardé localement) | échange avec un tiers |
| Portail des parents / élèves | **B** | dernier état (frais, notes, bulletins) en cache ; pas d'écriture |
| Équipements : liste, état | **B** | écran de la console : état local en direct, sans serveur |
| Équipements : jumelage, commandes, mise à jour | **local sur la console**, **C** depuis l'application | l'écran de la console agit sans internet (§ 3.4) |
| Personnel, paie, contrats (lot 12) | **C** (lecture **B** de son dernier bulletin de paie) | calcul et argent d'un tiers |
| Rôles, comptes, paramètres de l'école | **C** | pouvoir central, audit |
| Mon abonnement, factures de la plateforme (lot 3) | **C** | rien d'urgent |
| Console de la plateforme, site public | **C** | équipe, toujours connectée |

**Règles qui en découlent**
1. **Un cache par module** : le premier chargement hors ligne (`snapshot`) ne contient que les données des **modules de l'école** et des droits du compte (une école « Présences seules » ne télécharge ni frais ni notes) : moins de stockage, moins de temps, moins de fuite. Taille visée : < 30 Mo par appareil pour 1 200 élèves.
2. **Conflits** : ajout seulement (A) = jamais de conflit ; une même donnée modifiée deux fois = la **dernière validée par le serveur gagne** et l'autre version reste au journal ; une opération refusée au rejeu (permission retirée, élève supprimé) va dans une **boîte « à revoir »** visible de l'utilisateur, jamais en silence.
3. **Jamais d'argent ni d'identité modifié hors ligne** en dehors de la caisse existante.
4. **Indicateur unique** (déjà en place) : en ligne / hors ligne / à synchroniser (n opérations) / à revoir ; chaque module hors ligne le réutilise, sans second mécanisme.
5. **Appareils (équipements)** : leur hors-ligne est celui de leur micrologiciel (§ 3.4) ; ils ne passent pas par la file Dexie.
6. **Tests** : un parcours Playwright réseau coupé par type d'acte (déjà : caisse ; à ajouter : pointage par téléphone, notes, prêt de livre) — pas un par écran.
7. **À ne pas faire** (décidé) : édition hors ligne des fiches, des paramètres et des rôles ; synchronisation de fichiers lourds (PDF, photos) hors ligne ; mode hors ligne du portail en écriture.

## 6. Écrans (maquettes à dessiner au début du lot, 390 et 1440 px)

Gestion : **Équipements** (liste + état, ajout par code/QR, fiche, réglages, commandes, carte du réseau, mise à jour), **Sonnerie** (aujourd'hui, profils, créneaux, exceptions, calendrier, sonner maintenant / alerte / arrêt, journal), **Présences** (déjà lot 10 ; ajout : lecteur d'une séance, état en direct). Les maquettes existantes des deux projets (`maquettes/` de la sirène, du lecteur, TFT) servent de **point de départ** : on les reprend avec le système de design de Mwangaza (jetons, composants). Écrans du TFT : accueil, planning, sonnerie manuelle, réglages, journal, atelier, alerte (maquettes `maquettes/tft/*` du projet sirène).

## 7. Firmware dans le dépôt

```
firmware/
  lib/core/          logique pure testée sur PC : civil, planificateur, machine d'états, trames, déduplication, CRC
  lib/proto/         trames ESP-NOW, UART Uno, chiffrement, découpage
  console/           ESP32 : sonnerie + RFID + passerelle + liaison Uno
  reader/            ESP32 / ESP8266 : RFID + signalisation
  relay/             ESP32 / ESP8266 : répéteur
  uno-hmi/           sketch de l'Uno (écran, tactile, SD)
  tools/             signature, génération de clés, banc d'essai série
```
`make firmware` compile les environnements ; `make firmware-test` lance les tests natifs (CI). Aucun identifiant dans le code. Pas de nouvelle dépendance **de l'application** : les bibliothèques sont celles des deux projets (ArduinoJson, RTClib, MFRC522, Adafruit GFX/TouchScreen pour l'Uno) ; la mention « Firebase » disparaît.

## 8. Risques et décisions

- **Hors équipe** : aucun matériel n'est attendu d'un tiers ; le serveur simule appareils et lecteurs pour les tests (`make demo` crée une console et deux lecteurs fictifs). Les essais au banc (Uno, SD, portée ESP-NOW) se font avec le matériel de l'utilisateur ; chaque écart devient une tâche 16.x.
- **ESP8266** : pas d'AES matériel, RAM faible, pas de LittleFS confortable → il tient le rôle `reader`/`relay` simple (liste de séance bornée à 600 cartes) ; la console reste ESP32.
- **Portée ESP-NOW** non garantie entre bâtiments : on la mesure (qualité du lien affichée dans « Équipements »), les relais s'ajoutent au besoin.
- **Écriture SD** : jamais dans la boucle de dessin ; en ajout, par blocs de 512 octets, avec CRC ; le journal est aussi gardé par l'ESP32 (double copie).
- **Revoir si trop juste** : Uno → écran direct sur l'ESP32 (repli décrit en 2.2).
- **Hors V1** : écran de couleur autre que le shield 2.4–2.8″, son MP3, synthèse vocale, batterie avec mesure de charge, passerelle 4G/GSM (envisagée pour les écoles sans WiFi, V2).

## 9. Site, aide et documents à mettre à jour avec ces modules

- **Site de la plateforme** : page Modules (Sonnerie automatique, Présences par lecteur : icônes et points dans `MODULE_ICONS` / `MODULE_FEATURES`), **nouvelle page Équipements** (la console, les lecteurs, la sirène déportée, comment ils se parlent, l'autonomie, ce que l'école reçoit), accueil et page Écoles (« une école, un module ou tous »), page des prix (abonnement par module **et** matériel), démonstration (une console fictive), `llms.txt` et `sitemap.xml`, français et anglais. Photos du **vrai** matériel de l'utilisateur ; rien de technique pour le visiteur.
- **Aide** (lot 6) : un article par module, affiché seulement aux écoles qui l'ont ; guide de montage du matériel (schéma, pièces, jumelage, dépannage) en PDF.
- **Documents internes** à garder à jour avec le lot : `02`, `03`, `04` (modèle de données), `07`, `reference.md`, `A-FAIRE.md`, guide de présentation, skills.
