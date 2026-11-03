# Équipements : sonnerie, lecteurs de présence et réseau (lot 16)

Décidé le 2026-11-03. Mwangaza englobe désormais deux projets existants : la **sirène automatique** (`sirene_automatique_pro_esp32` : firmware ESP32, planificateur, DS3231, relais, TFT, Firebase) et le **système de présences RFID ULPGL 001** (`gestion_presence_rfid_university_ulpgl_001` : lecteur ESP32 + RC522, séances, Firebase). On **reprend leur logique et leur matériel**, on **remplace Firebase** par l'API Mwangaza (multi-écoles, audit, permissions) et on ajoute un **réseau d'appareils** maîtrisé de bout en bout. Le code d'origine reste la référence ; rien n'est recopié sans être relu.

## 1. Principe produit : l'école achète des modules

| Module | Ce que l'école voit | Dépend de |
|---|---|---|
| `bell` — Sonnerie automatique | **Seulement** : Sonnerie (horaires, calendrier, sonner maintenant, journal) et Équipements. Aucun élève, aucune classe. | rien |
| `attendance` — Présences | Élèves, enseignants, cours, séances, cartes, lecteurs, justifications, rapports. Pas la sonnerie. | `students`, `academics` |
| les deux | les deux entrées, sur le **même** appareil | — |

- **Équipements** (liste, jumelage, état, réglages, journal) est un socle **dérivé** : visible dès qu'un des deux modules est pris, jamais vendu à part (`accounts/modules.py`, module interne `devices`, sans case dans la console).
- **À la création d'une école**, la console propose des **forfaits de départ** (Sonnerie seule · Présences · Gestion complète · Sur mesure). Chaque module porte une fonction `setup(school)` (registre `MODULE_SETUP`) qui crée ses **réglages par défaut** (profil « Normal » et créneaux types pour `bell` ; seuils et retard toléré pour `attendance`). Activer un module plus tard l'appelle une fois ; le désactiver ne supprime rien (règle M.1).
- Le **premier écran après connexion** dépend des modules : une école « Sonnerie seule » arrive sur Sonnerie ; menus, recherche, tableau de bord, rôles proposés et permissions sont filtrés par module (déjà vrai côté serveur depuis M.2 ; à vérifier écran par écran).
- Rôles utiles pour `bell` : `bell_operator` (sonner, alerte), `bell_admin` (horaires) ; l'**administrateur principal** garde tout. Pas de rôle « enseignant » obligatoire pour une école sans élèves.

## 2. Matériel

### 2.1 Trois familles d'appareils (une seule carte logicielle commune)

| Type (`Device.kind`) | Carte | Rôle |
|---|---|---|
| `console` | ESP32 (NodeMCU-32S) + **Arduino Uno + shield TFT tactile** + DS3231 + relais sirène + buzzer + RC522 | Appareil central de l'école : sonnerie autonome **et** lecteur de présence. Sert aussi de **passerelle** vers internet. |
| `reader` | ESP32 **ou** ESP8266 + RC522 + 4 LED + buzzer | Lecteur de présence dans une salle ; commande aussi un avertisseur local. |
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

ESP32 ou ESP8266 + RC522 + LED (verte OK, orange déjà passé, rouge refus, bleue prêt/attente de carte) + buzzer, bouton (appui long = réglage). Signalisation identique à celle du projet ULPGL (vert + 1 bip, orange + 2 bips, rouge + bip long). **Il décide seul** à partir de la liste de la séance reçue ; un tap n'attend jamais le réseau.

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
- **La sirène n'est pas alimentée par cette batterie** : le relais ne fait que **fermer un contact sec** ; la sirène a sa propre alimentation. Sans courant, la sirène ne sonne donc pas, même si l'appareil tient l'heure (à signaler à l'école ; sirène sur batterie 12 V possible plus tard).
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

- **Une passerelle par école** (au moins) : seul appareil à parler à l'API. Elle peut être la console, ou un `reader`/`relay` désigné `gateway` si l'école n'a pas de console. Une école plus grande peut avoir **deux passerelles** (reprise automatique).
- Les autres appareils parlent **ESP-NOW** (couche 2 du WiFi, sans point d'accès, portée ≈ 100–200 m en vue directe, plus avec antenne externe) vers leur **parent** (la passerelle, ou un relais). Pas d'internet côté capteur : pas de mot de passe WiFi à saisir sur chaque lecteur, un seul réglage WiFi par école.
- **Relais** : retransmet les trames d'un appareil éloigné (maillage multi-sauts, 4 sauts au plus). Un appareil choisit son parent selon la qualité du signal (RSSI) et le nombre de sauts jusqu'à la passerelle, et en change si le parent disparaît.
- **Repli sans routeur** : si la passerelle perd internet ou le WiFi, **le réseau local continue** (sonnerie, taps, séances ouvertes) ; les événements s'accumulent (§ 5) et partent au retour de la liaison.
- Un appareil sans portée vers un parent mais avec un WiFi connu peut se déclarer lui-même passerelle (option « autonome »).

### 3.2 Trame (couche liaison applicative)

`ver(1) | type(1) | école_courte(2) | src(4) | dst(4) | saut_restant(1) | seq(4) | charge(≤190) | tag(8)`
- **seq** par source, enregistré en mémoire non volatile par paquets de 16 ; **déduplication** par `(src, seq)` sur les relais et la passerelle (fenêtre de 64) : un renvoi ou deux chemins ne créent jamais de doublon.
- **Accusé de réception** de bout en bout pour les événements (pointage, journal) : l'appareil garde l'événement jusqu'à l'accusé de la passerelle, **après** l'accusé de l'API ; renvoi avec attente croissante.
- Types : `hello/join`, `heartbeat`, `event`, `ack`, `command`, `config`, `roster-chunk`, `ota-chunk`, `time`.
- Charges au-delà de 190 octets (liste d'une séance, firmware) : découpées en morceaux numérotés avec reprise des morceaux manquants.

### 3.3 Sécurité (le réseau est commercial : rien n'est « de confiance »)

- Chaque appareil a une **clé de 256 bits propre** (générée par le serveur au jumelage, jamais réutilisée, jamais journalisée, stockée en NVS) ; chiffrement et authentification des charges en **AES-128-GCM** (mbedTLS sur ESP32 ; bibliothèque légère équivalente sur ESP8266) avec **compteur anti-rejeu** ; une trame non authentifiée est ignorée sans réponse.
- La clé ESP-NOW native (limite de 10 pairs chiffrés) n'est **pas** utilisée : la sécurité est applicative, donc sans limite de pairs et indépendante du relais (un relais ne peut ni lire ni modifier ce qu'il transmet).
- **Jumelage** : l'appareil neuf n'a aucune clé. Dans la Gestion, « Ajouter un appareil » affiche un **code à 8 caractères et un QR** valable 15 minutes, à usage unique ; l'appareil, mis en mode jumelage (appui long), le présente à la passerelle ; le serveur répond par la clé de l'appareil, chiffrée avec une clé dérivée du code. Appareil retiré = clé révoquée, trames refusées au prochain contact.
- Passerelle ↔ API : HTTPS, jeton d'appareil + signature HMAC de chaque requête (horodatage, nonce) ; **toutes les écritures sont idempotentes** (règle 4) : chaque événement porte un **UUID v7 généré par l'appareil** (horloge DS3231 valide) ou, horloge douteuse, un UUID dérivé de `(appareil, seq)` marqué `clock_untrusted`.
- Toute commande envoyée à un appareil (sonner, alerte, réglage, mise à jour) a un **identifiant, une expiration** (une sonnerie de 10 min n'est pas exécutée à 14 h) et un **accusé** ; l'évacuation/alerte exige la permission dédiée et est journalisée.
- Micrologiciel : **signé** (clé publique de la plateforme dans l'appareil, ed25519), mise à jour par la passerelle puis relais en morceaux ; refus d'une version plus ancienne ; retour arrière si l'appareil ne confirme pas au démarrage.

## 4. Logiciel : serveur

Nouvelle application Django **`devices`** (tout modèle d'école hérite de `TenantModel`) :

| Modèle | Rôle |
|---|---|
| `Device` | appareil : école, `kind`, nom, salle (`Room` de l'emploi du temps si présent), identifiant matériel, clé (chiffrée), version firmware, `last_seen`, RSSI, parent dans le maillage, `gateway`, `state` |
| `DevicePairing` | code de jumelage à usage unique avec expiration |
| `DeviceCommand` | commande (type, charge, expiration, état : en attente / envoyée / exécutée / expirée) |
| `DeviceEvent` | événement brut reçu (UUID v7, appareil, type, charge, heure appareil, `clock_untrusted`) ; table purgée après traitement selon S.7 |
| `FirmwareRelease` | version signée, canal (essai / stable), notes |
| `bell.*` | `BellProfile`, `BellSlot` (heure, durée, motif de son, jours), `BellException` (date → profil ou silence), `BellRing` (journal des sonneries réelles) |
| `attendance.*` | `AttendanceSession` (cours, salle, début/fin, liste figée), `AttendanceRecord` (élève, séance, heure, source : lecteur / téléphone / main), cartes (6.1) |

Principes :
- **API d'appareil** `/api/devices/sync/` (une seule porte) : la passerelle envoie un lot `{events:[…]}` et reçoit `{commands:[…], config_rev, roster_changes:[…]}` ; réponse **delta par `rev`** comme la synchronisation de la Gestion (`/hors-ligne`). Pas de Firebase, pas de WebSocket permanent (charge serveur faible : un appel toutes les 10 à 30 s par passerelle, plus long si rien à dire).
- **Planning de la sonnerie** : source de vérité sur le serveur, **copie complète sur l'appareil** (JSON signé, versionné). Les créneaux peuvent venir de la **grille horaire de l'emploi du temps** (`TimeSlot`) quand l'école a ce module, ou être saisis seuls : une école « Sonnerie seule » n'a pas besoin de classes. Les jours fériés et congés viennent du **calendrier de l'école** (`SchoolEvent`), avec les jours fériés de la RDC en valeurs par défaut modifiables.
- **Présences** : le lecteur envoie le tap ; un service crée l'`AttendanceRecord` (idempotent par UUID), notifie les parents au besoin (lot 10), alimente les rapports. Une carte (6.1) est une clé d'identité unique par école ; les lecteurs et le pointage par téléphone (6.3) alimentent la **même** table.
- Tout changement d'appareil, de planning, de commande d'alerte ou de séance va dans l'`AuditLog` (règle 5). Isolation : un appareil ne lit et n'écrit que dans son école ; test dédié pour chaque point d'API.

## 5. Ce qui doit marcher sans connexion (revue du plan, 2026-11-03)

| Fonction | Où ça tourne sans internet | Prévu |
|---|---|---|
| Sonnerie (planning, calendrier, sirène, boutons) | **sur l'appareil** (DS3231 + copie du planning) ; jamais dépendante du réseau | lot 16 |
| Pointage par lecteur | sur le lecteur (liste de la séance en mémoire) ; événements gardés puis envoyés | lot 16 |
| Pointage par téléphone / tablette (6.3) | Gestion hors ligne (Dexie + file d'opérations) | lot 10 |
| Caisse, reçus, élèves en lecture | Gestion hors ligne | fait (V1.0) |
| Saisie des notes, conduite | Gestion hors ligne | lots 8 (HL.2) |
| Dépenses, sorties de caisse, inscription | Gestion hors ligne | lot 7 (HL.1) |
| **Bibliothèque : prêt, retour, inventaire** (scan) | **à ajouter** : file d'opérations comme la caisse | lot 11 (INV.1, BIB) |
| **Ateliers : sortie et retour d'outils** | **à ajouter** : idem | lot 11 (ATL) |
| Présence du personnel (pointage du personnel) | via lecteur ou téléphone, même moteur | lots 10 et 16 |
| Messagerie, portail des parents et des élèves, factures, console | en ligne seulement (lecture du dernier état en cache pour le portail) | — |
| Paie, personnel | en ligne ; consultation du dernier bulletin de paie hors ligne | lot 12 |

Règle générale : **tout ce qui s'enregistre à un guichet ou à une porte** se fait hors ligne ; tout ce qui s'écrit à un bureau, avec un tiers, reste en ligne.

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
