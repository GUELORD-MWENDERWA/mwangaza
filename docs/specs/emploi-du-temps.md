# Spécification — Emploi du temps (bloc EDT, avec l'aide de l'IA)

Écrite le 2026-10-20 à la demande de l'utilisateur (tâche **EDT.0**). Le plan (`05` § 6.4) dit **quand** ; ce fichier dit **quoi** et **comment**. Chaque tâche EDT lit la section qui la concerne avant sa fiche (`docs/claude/plans/`). En cas de contradiction : `01` à `04` priment, puis ce fichier, puis les maquettes.

## 1. But, pour l'école

Le directeur des études (DE) et le préfet construisent en une matinée l'horaire de la semaine de toute l'école, sans conflit :

- **chaque classe** a son horaire de la semaine ; **chaque enseignant** a le sien, avec sa charge ; **chaque salle et atelier** a son occupation ;
- les **heures qui ne bougent pas** sont respectées (ex. 2HT Électricité : atelier le lundi de la 2e à la 7e heure) ;
- les élèves ne sont pas **surchargés** (jamais 5 heures de mathématiques le même jour ; au plus 2 par jour par défaut) ;
- la machine **dit ce qui coince avant de calculer** (classe surchargée, enseignant surchargé, atelier demandé par trop de classes) et, si c'est impossible, **quelle règle bloque** ;
- l'IA **aide** le DE : elle comprend ses consignes écrites en phrases, explique les problèmes, propose des corrections ; **le DE décide**, et une heure qu'il verrouille ne change plus ;
- tout s'**imprime** (horaire par classe, par enseignant, par salle, horaire général, fiche des **heures prestées**) et se voit dans le Portail et l'espace de l'enseignant.

**Avis de développeur senior.** Un emploi du temps est un problème de contraintes : il faut une **garantie mathématique** de zéro conflit, qu'une IA seule ne donne pas (elle peut mettre un enseignant dans deux classes à la même heure sans le voir). Donc trois couches, chacune dans son rôle :

| Couche | Fait | Ne fait jamais |
|---|---|---|
| **Contrôles** (code Python, instantané) | compte les heures, détecte les surcharges et les conflits, avant et après chaque changement | deviner |
| **Solveur** (OR-Tools CP-SAT, tâche de fond) | place chaque heure en respectant toutes les règles obligatoires, au mieux les souhaits ; dit quelle règle bloque | décider seul de lever une règle |
| **IA** (Claude, usage déclaré, clic de la personne) | traduit des phrases en règles, explique en mots simples, propose des changements | écrire l'horaire, calculer les conflits, valider |

Une école **sans le module IA ou sans crédits** a tout le reste : contrôles, calcul, éditeur, impressions. L'IA est un plus, pas une béquille.

## 2. Vocabulaire

| École | Ici | Code |
|---|---|---|
| Horaire type (ex. « Avant-midi », « Après-midi » pour les écoles à deux vacations) | grille horaire | `TimeGrid` |
| 1re heure, 2e heure… ; récréation | case de la grille | `TimeSlot` (`kind` : `lesson`, `break`) |
| Durée d'une heure (45, 50 min…) | durée de la leçon | `TimeGrid.lesson_minutes` |
| Volume horaire hebdomadaire d'un cours | heures par semaine | `Course.weekly_hours` (existe, 8.1) |
| Découpage d'un cours dans la semaine (5 h de maths = 2 + 2 + 1) | séances | `Course.lesson_pattern` |
| Charge horaire d'un enseignant | charge | somme des `weekly_hours` de ses cours (existe, 8.1) |
| Salle, atelier, laboratoire | salle | `Room` |
| Heure verrouillée (« cette heure ne change pas ») | verrou | `TimetableEntry.locked` |
| Consigne (« M. Kambale ne vient pas le vendredi ») | règle | `TimetableRule` |
| Horaire en préparation / en vigueur | version | `Timetable` (`draft`, `published`, `archived`) |
| Heures réellement données | heures prestées | horaire publié − `LessonException` |

## 3. Paramètres de l'école (EDT.1a)

**Rien en dur** (règle 9) : tout vient des paramètres ; les valeurs ci-dessous sont seulement le **préréglage** proposé à une école neuve et utilisé par `make demo` (question **Q16** de `06`).

- **Jours de cours** : lundi à samedi ; un jour peut avoir moins d'heures (samedi : 4 heures).
- **Grille horaire** : une par école au départ ; une école à deux vacations en crée deux (les classes de l'après-midi ont la leur). Chaque classe (`ClassGroup.time_grid`, vide = grille par défaut) suit une grille.
- **Durée d'une heure** en minutes (préréglage 50, de 30 à 90) et **heure de début** (7 h 30) : l'écran **calcule** les heures de début et de fin de chaque case ; on peut ensuite corriger une case à la main (récréation plus longue le vendredi…).
- **Récréations** : cases `break` placées entre deux heures (préréglage : 15 min après la 3e heure, 10 min après la 5e) ; jamais de cours dessus.
- **Heures par jour** : déduites des cases (préréglage 7, samedi 4). L'écran affiche le **total d'heures de cours par semaine** de la grille (préréglage 39) : c'est la capacité d'une classe.
- **Règles générales de l'école** (`School.settings["timetable"]`) : au plus **2 heures du même cours par jour** ; au plus **6 heures par jour** pour un enseignant ; une classe **n'a pas de trou** dans sa journée (elle peut finir plus tôt, jamais attendre entre deux cours) ; préférence pour les cours principaux en début de journée.
- **Salles** (`Room`) : nom, type (`classroom`, `workshop`, `lab`, `computer`, `sports`, `other`), capacité, active. Une classe a sa **salle habituelle** (facultative) ; un cours peut **exiger** une salle précise ou un type de salle (atelier de mécanique, laboratoire). Une salle ne reçoit qu'un cours à la fois (sauf type `sports`, réglable).

Contrôle immédiat à l'écran : pour chaque classe, **heures de ses cours / capacité de sa grille** (ex. « 6e A : 41 h pour 39 places → 2 h en trop »).

## 4. Cours et enseignants (EDT.1b)

Les cours, leurs heures et leurs enseignants **existent déjà** (8.1 : `Course.weekly_hours`, `Course.teacher`, charge = somme). On ajoute seulement ce qu'il faut pour placer les heures, dans les mêmes écrans (grille de cours d'une classe, d'un seul envoi comme aujourd'hui) :

- **Séances** (`lesson_pattern`, facultatif) : comment répartir les heures, ex. `2+2+1`, `6` (atelier d'un seul bloc), `1+1+1+1` ; vide = calculé (blocs de 2 si le cours a 4 heures ou plus, sinon des heures seules), toujours égal à `weekly_hours`. Une séance de 2 heures et plus se place **d'un seul tenant** ; elle peut **passer la récréation** si le cours le permet (`can_span_break`, oui par défaut pour la catégorie `practical`).
- **Au plus N heures par jour** pour ce cours (`max_per_day`, vide = règle de l'école). Contrôle : séances × jours possibles ≥ heures (5 h de maths à 1 h par jour sur 4 jours = impossible, dit avant le calcul).
- **Salle exigée** : une salle précise ou un type (`room` / `room_kind`).
- **Moment** : `preferred_part` = `morning`, `any` (souhait, pas obligation).
- **Groupes en parallèle** : en technique, une classe se coupe en groupes (moitié en mécanique, moitié en électricité) : deux cours de la même classe marqués **parallèles** se placent **à la même heure**, chacun avec son enseignant et sa salle (règle `parallel_courses`). Les heures de la classe ne comptent qu'une fois.
- **Cours commun à deux classes** (religion, éducation physique de deux sections ensemble) : règle `joint_courses` ; même heure, même enseignant, une seule fois dans sa charge.

**Profil horaire de l'enseignant** (`TeacherTimetableProfile` [T], un par membre du personnel qui a des cours) : charge **maximale** par semaine (contrat ; vide = pas de limite), heures **au plus par jour**, **indisponibilités** (jours entiers ou cases : « ne vient pas le vendredi », « enseigne ailleurs le mardi matin »). Un enseignant **partagé avec une autre école** se règle ici par ses indisponibilités : on ne lit **jamais** l'horaire d'une autre école (isolation, règle 1).

## 5. Règles (contraintes)

Une règle = une ligne `TimetableRule` [T] : `kind` (liste fermée ci-dessous), `params` (JSON **vérifié par un schéma propre à chaque kind**), `strength` (`hard` obligatoire / `soft` souhait, avec un poids 1 à 10), `active`, `source` (`manual`, `ai`), `text` (la phrase d'origine, si l'IA l'a traduite), auteur. Les réglages des §§ 3 et 4 sont aussi des règles pour le solveur, mais rangés là où l'école les cherche.

**Toujours obligatoires (non désactivables)** — le cœur, garanti par le solveur et revérifié par les contrôles :

| # | Règle |
|---|---|
| O1 | Une classe (ou un groupe) n'a qu'un cours à la fois. |
| O2 | Un enseignant n'est qu'à un endroit à la fois. |
| O3 | Une salle ne reçoit qu'un cours à la fois (capacité réglable pour le sport). |
| O4 | Chaque cours reçoit **exactement** ses heures de la semaine, selon ses séances. |
| O5 | Rien sur une récréation ni hors de la grille de la classe. |
| O6 | Une **heure verrouillée** reste à sa place, avec sa salle. |
| O7 | Un enseignant n'est jamais placé sur une indisponibilité. |

**Réglables** (obligatoires par défaut sauf mention) :

| Kind | Exemple | Défaut |
|---|---|---|
| `max_course_per_day` | maths : au plus 2 h par jour | école : 2 |
| `teacher_max_per_day` | au plus 6 h par jour | école : 6 |
| `teacher_max_week` | charge du contrat | profil |
| `class_no_gap` | pas de trou pour les élèves | obligatoire |
| `fixed_lesson` | atelier de la 2HT Électricité le lundi, 2e à 7e heure | — (crée des heures verrouillées) |
| `course_not_slot` | pas d'EPS en 1re heure ; pas de maths en dernière heure | souhait |
| `course_part_of_day` | cours principaux le matin | souhait, poids 3 |
| `parallel_courses`, `joint_courses` | § 4 | obligatoire |
| `room_unavailable` | laboratoire fermé le samedi | obligatoire |
| `spread_over_week` | les heures d'un cours sur des jours différents, pas deux jours de suite pour 2 séances | souhait, poids 5 |
| `teacher_compact` | peu de trous dans la journée de l'enseignant | souhait, poids 2 |
| `teacher_free_day` | M. X souhaite son mercredi libre | souhait |
| `stability` | à la régénération, changer le moins possible l'horaire publié | souhait, poids 8, automatique |

Liste **fermée** : une consigne qui n'entre dans aucun kind est refusée avec la raison (l'IA ne peut pas inventer de règle que le solveur ne sait pas lire). Un nouveau kind = du code, des tests, une ligne ici.

## 6. Contrôles avant le calcul (EDT.1b) — le « diagnostic »

Calcul Python pur, quelques millisecondes, **sans solveur ni IA**, montré en permanence dans un panneau « À régler avant le calcul » (rouge = impossible, orange = risqué) :

1. **Classe surchargée** : heures des cours > capacité de sa grille (moins les heures interdites à cette classe).
2. **Enseignant surchargé** : charge > charge maximale ; charge > cases où il est disponible ; charge d'un jour impossible à tenir avec `teacher_max_per_day`.
3. **Cours impossible à étaler** : `weekly_hours` > `max_per_day` × jours possibles ; séance plus longue que la plus longue suite d'heures d'un jour.
4. **Salle demandée par trop de cours** : somme des heures qui exigent une salle (ou un type) > ses cases disponibles.
5. **Cours sans enseignant**, sans heures, ou enseignant désactivé.
6. **Verrous en conflit** : deux heures verrouillées au même enseignant, à la même classe ou à la même salle.
7. **Règles qui se contredisent** directement (verrou sur une indisponibilité, etc.).

Chaque ligne dit **quoi**, **combien** et **où corriger** (lien vers l'écran). C'est aussi ce que l'IA reçoit pour expliquer (§ 9) : les chiffres viennent du code, jamais de l'IA. Le bouton « Calculer » reste grisé tant qu'il y a du rouge.

## 7. Le solveur (EDT.3)

**Outil** : OR-Tools CP-SAT (Google, Apache 2.0 ; dépendance acceptée le 2026-10-13). Importé **dans la tâche seulement** (§ 8.5 de `05`, règle PERF.8).

**Modèle** :
- Une variable booléenne `x[séance, jour, case de départ]` pour chaque départ **permis** (la séance tient dans la journée de la grille, ne coupe pas une récréation sauf `can_span_break`, ne touche pas une indisponibilité de l'enseignant ni une case interdite). Les départs impossibles ne sont **pas créés** : c'est ce qui garde le modèle petit.
- Chaque séance part exactement une fois (O4) ; séance verrouillée = variable fixée (O6).
- Occupation de chaque case par classe, enseignant, salle : somme ≤ 1 (O1–O3), en tenant compte des groupes parallèles et des cours communs.
- Pas de trou pour la classe : pour chaque jour, les cases occupées forment un bloc qui commence à la 1re heure (variables d'occupation et implications).
- Choix de la salle quand le cours demande un **type** : variable salle × séance, une seule.
- Souhaits : pénalités pondérées dans l'objectif (trous des enseignants, maths en dernière heure, deux séances le même jour ou deux jours de suite, écart à la version publiée).

**Taille attendue** : ITIG ≈ 30 classes × ≈ 39 h ≈ 1 200 heures ≈ 600 séances × 6 jours × ≈ 6 départs ≈ 20 000 variables : taille ordinaire pour CP-SAT. **À mesurer** dès EDT.3 sur `make demo` (temps et pic de mémoire, noté dans `docs/claude/recherches/`).

**Exécution** (serveur partagé de 2 Go) :
- tâche Celery de la file `heavy`, **une à la fois** pour toute la plateforme (verrou Redis), `num_workers=1`, **temps limité** (préréglage 60 s, au plus 180 s, réglable dans la console), `soft_time_limit` et `time_limit` ;
- `TimetableRun` [T] : demande idempotente (UUID v7 de l'écran), état (`queued`, `running`, `done`, `infeasible`, `timeout`, `error`), durée, score, nombre de souhaits non tenus, pic de mémoire ; l'écran suit l'état et peut annuler ;
- résultat écrit dans un **brouillon** (`Timetable` en `draft`), jamais directement dans la version publiée ;
- si le pic dépasse 250 Mo : résoudre grille par grille (vacation du matin, puis de l'après-midi avec la première verrouillée), sinon OPS.5 (4 Go).

**Quand c'est impossible** : chaque groupe de règles réglables (une règle `TimetableRule`, les indisponibilités d'un enseignant, les verrous d'une classe, le `max_per_day` d'un cours…) est relié à une **variable d'hypothèse** ; CP-SAT rend un sous-ensemble suffisant pour l'impossibilité (`SufficientAssumptionsForInfeasibility`), traduit en phrases : « Impossible : M. Kambale a 26 h à donner mais n'est disponible que 24 h (indisponible le vendredi) ». On propose ce qu'on peut assouplir ; les règles O1 à O5 ne s'assouplissent jamais.

**Temps écoulé sans solution complète** : on garde la meilleure solution partielle **seulement si** toutes les règles obligatoires tiennent ; sinon « pas trouvé dans le temps : relancer plus longtemps ou verrouiller moins ».

**Régénération partielle** : « recalculer seulement la 4e Mécanique » ou « seulement M. X » = tout le reste verrouillé le temps du calcul. Une heure **verrouillée par le DE** n'est jamais déplacée, quelle que soit la demande, IA comprise.

## 8. Éditeur et contrôle des conflits (EDT.2)

**Maquettes d'abord** (`maquettes/gestion/emploi-du-temps-*.html`, 390 et 1440 px) ; s'inspirer d'aSc Timetables, FET, Untis (étude courte notée dans `docs/claude/recherches/`).

- Vues : **par classe**, **par enseignant**, **par salle**, et **horaire général** (toutes les classes en lignes, les heures en colonnes, pour le bureau du DE). Au téléphone : un jour à la fois, liste verticale.
- Chaque case : cours, enseignant, salle ; couleur par cours ; cadenas si verrouillée.
- **Déplacer** une heure (glisser sur ordinateur, « Déplacer vers… » au téléphone) ; échanger deux heures ; verrouiller / déverrouiller ; « heures restant à placer » listées à côté de la grille.
- **Conflits montrés tout de suite**, par les mêmes contrôles qu'au § 6 rejoués sur le brouillon (côté serveur, l'écran peut aussi les calculer pour réagir sans attendre) : enseignant à deux endroits, salle prise, classe surchargée ce jour-là, charge dépassée, règle non tenue. On **peut** enregistrer un brouillon avec conflits (on travaille), on **ne peut pas** publier tant qu'une règle obligatoire est violée.
- **Charges visibles** : pour chaque enseignant, heures placées / heures dues / maximum ; pour chaque classe, heures placées / heures dues, heures par jour.
- Une écriture par geste (pas d'enregistrement à chaque survol) ; le brouillon garde son historique de gestes pour « Annuler ».

## 9. Ce que fait l'IA (IA.2a, IA.2b)

Usages du catalogue `ai/uses.py` (IA.1.1), module hôte `timetable`, permission hôte `timetable.manage`, toujours sur un **clic** du DE, jamais automatique ; chaque appel passe par les cinq verrous et les crédits de l'école.

**IA.2a — Consignes en phrases → règles** (`timetable_constraints`). Le DE écrit : « M. Kambale ne vient pas le vendredi ; la 4e Mécanique a l'atelier le mardi matin ; pas de maths après la récréation en 1re ». L'IA reçoit la phrase, la **liste fermée des kinds** et leurs schémas, les noms des cours, classes, enseignants et salles **de cette école seulement** ; elle rend du **JSON vérifié par schéma** : une règle proposée par consigne, ou « pas compris : … ». Chaque proposition s'affiche comme une ligne lisible (« M. Kambale : indisponible le vendredi, toute la journée ») ; le DE coche, corrige, enregistre. Rien n'est enregistré sans lui.

**IA.2b — Analyse et propositions** (`timetable_review`). Bouton « Demander conseil » sur le diagnostic ou sur un horaire calculé. L'IA reçoit **les chiffres calculés par le code** (diagnostic § 6, conflits, charges, souhaits non tenus, contrainte qui bloque) et les règles en vigueur ; elle rend :
- une **explication** courte en mots simples (« la 6e A a 41 h pour 39 places : deux cours ont une heure de trop par rapport au programme ») ;
- des **propositions d'action** structurées, chacune d'un kind connu : modifier une règle, retirer un verrou, changer les séances d'un cours, déplacer une heure, demander un enseignant de plus. Chaque proposition a un bouton « Appliquer » qui passe par l'écran normal (permission, journal), puis le DE relance le calcul : **le solveur vérifie** toute proposition, l'IA ne garantit rien.

**« Ces heures ne changent pas »** : dites en phrase (IA.2a → règle `fixed_lesson`) ou d'un clic (cadenas) ; même résultat, un verrou que ni le solveur ni l'IA ne déplacent.

**Données envoyées** (IA.1.1, minimisation) : noms des cours, des classes, des salles, noms des enseignants (utiles pour la consigne) ; **jamais** d'élève, de téléphone, d'argent. Un horaire calculé envoie un résumé (comptes par classe et enseignant), pas toutes les cases.

## 10. Versions et publication (EDT.4)

- `Timetable` [T] : année scolaire, nom, état `draft` → `published` → `archived`, date d'effet, publié par, basé sur. **Une seule version publiée** par année à la fois ; publier archive la précédente (gardée, consultable, réimprimable).
- `TimetableEntry` [T] : version, cours, case de départ, longueur (heures), salle, verrouillée, groupe. Une version publiée **ne se modifie plus** : un changement = un nouveau brouillon copié de la publiée, puis publication.
- Publier : bloqué si une règle obligatoire est violée ; journal (`AuditLog` : publication, verrous et règles changés, car l'horaire publié sert à la paie) ; **notification** aux enseignants dont l'horaire change et, pour le Portail, aux parents des classes touchées (5.6), regroupée en une seule par personne.
- **Lecture sans réseau** : la version publiée (de l'enseignant, de sa classe) part dans l'instantané de la Gestion ; l'édition et le calcul restent en ligne (`05` § 5 bis : configuration partagée).

## 11. Impressions (EDT.4, EDT.6)

En-tête des documents imprimés de l'école (logo, drapeau, lignes centrées, filet épais, titre et N° de référence), PDF dans la file `heavy`, gardés (PERF.2) jusqu'au prochain changement de version. **Maquette de chaque document d'abord.**

1. **Horaire d'une classe** (A4 paysage) : jours en colonnes, heures en lignes avec leurs heures de début et de fin, cours, enseignant, salle ; récréations ; titulaire ; total d'heures. Toutes les classes d'un coup = un PDF, une classe par page.
2. **Horaire d'un enseignant** : ses heures, classes, salles ; **charge de la semaine** (heures dues, placées), répartition par classe et par cours.
3. **Horaire d'une salle ou d'un atelier.**
4. **Horaire général** (A3 paysage, ou A4 sur deux pages) : toutes les classes, pour le bureau et la salle des professeurs.
5. **Fiche des heures prestées** (EDT.6), par enseignant et par mois : heures prévues par l'horaire publié sur les jours de cours du mois (calendrier de l'école, `SchoolEvent` : congés et jours fériés retirés), moins les heures non données, plus les remplacements et heures en plus ; signature de l'enseignant et du DE. Export Excel de tout le personnel (pour la paie, 7.3, et les primes, `TeacherBonus`).
6. **Horaire des interrogations et des examens** de chaque période (EDT.5) : fait par le DE à partir des cours de chaque classe (jour, heure, durée, salle, surveillant) ; contrôles des § 6 et § 8 réutilisés (un surveillant à un seul endroit, une classe une seule épreuve à la fois) ; même impression et même publication.

## 12. Heures prestées (EDT.6)

Les vraies heures données demandent de savoir ce qui ne s'est pas passé comme prévu. Sans appel en classe (V1.5), on part de l'**horaire publié** et le DE (ou le surveillant) note **les exceptions**, jamais chaque heure :

- `LessonException` [T] : date, heure de l'horaire (`TimetableEntry`), type (`teacher_absent`, `replaced`, `cancelled`, `extra`), enseignant remplaçant, motif, auteur ; **journal** (sert à la paie, règle 5) ; une annulation de l'exception, pas une suppression silencieuse.
- Heures prestées = prévues − absentes − annulées + remplacements faits + heures en plus. Calcul **en SQL** sur le mois, jamais stocké en double ; la fiche est un PDF généré à la demande.
- Plus tard (V1.5) : l'appel en classe confirmera les heures réellement tenues.

## 13. Modèle de données (résumé, détail dans `04` à chaque tâche)

| Modèle | Tâche | Champs principaux |
|---|---|---|
| `TimeGrid` [T] | EDT.1a | `name`, `lesson_minutes`, `start_time`, `is_default` |
| `TimeSlot` [T] | EDT.1a | `grid`, `weekday` (1–7), `index` (1re heure…, vide pour une récréation), `start`, `end`, `kind` (`lesson`, `break`) ; unique (`grid`, `weekday`, `start`) |
| `ClassGroup.time_grid`, `ClassGroup.home_room` | EDT.1a | FK facultatives |
| `Room` [T] | EDT.1a | `name`, `kind`, `capacity`, `is_active` |
| `Course` (champs ajoutés) | EDT.1b | `lesson_pattern`, `max_per_day`, `room`, `room_kind`, `can_span_break`, `preferred_part` |
| `TeacherTimetableProfile` [T] | EDT.1b | `member` (personnel), `max_week_hours`, `max_day_hours`, `unavailable` (liste de cases ou jours, validée) |
| `TimetableRule` [T] | EDT.1b | `kind`, `params` (schéma par kind), `strength`, `weight`, `active`, `source`, `text`, `created_by` |
| `Timetable` [T] | EDT.2 | `academic_year`, `name`, `status`, `valid_from`, `published_at`, `published_by`, `based_on` |
| `TimetableEntry` [T] | EDT.2 | `timetable`, `course`, `slot`, `length`, `room`, `locked` ; index (`timetable`, `slot`) |
| `TimetableRun` [T] | EDT.3 | `request_id` (UUID v7, unique), `timetable`, `status`, `scope`, `time_limit`, `duration_ms`, `score`, `blocking` (JSON), `peak_mb` |
| `LessonException` [T] | EDT.6 | `date`, `entry`, `kind`, `replacement`, `reason`, `created_by` |

Tous en `TenantModel` (isolation, RLS de S.6). **Permissions** : `timetable.view` (voir les horaires publiés de l'école), `timetable.manage` (règles, brouillons, calcul, IA), `timetable.publish`, `timetable.record_exceptions` (heures prestées) ; l'enseignant voit **toujours** son propre horaire, le parent celui de la classe de son enfant (Portail). Module `timetable` du catalogue (M.2), vendable seul (ABO), dépend de `academics`.

## 14. Tests obligatoires (en plus de la définition de « fini » de `05` § 8.2)

- Isolation : chaque modèle, chaque point d'API, chaque PDF, le diagnostic, le calcul et l'IA ne lisent ni ne modifient une autre école (dont : un enseignant partagé ne fait jamais voir l'autre école).
- Permissions : 403 sans `timetable.manage` / `publish` / `record_exceptions` ; l'enseignant ne voit que son horaire et l'horaire publié.
- Solveur, sur de **petits cas écrits à la main** (3 classes, 4 enseignants) : aucune règle O1–O7 violée ; un verrou ne bouge pas ; 5 h de maths avec `max_per_day=2` jamais 3 le même jour ; groupes parallèles à la même heure ; cas impossible → la bonne règle nommée ; même `request_id` deux fois = un seul calcul.
- Diagnostic : chaque contrôle du § 6 sur un cas qui le déclenche.
- Publication : bloquée avec un conflit obligatoire ; version publiée immuable ; journal écrit.
- Heures prestées : calcul exact sur un mois avec congé, absence et remplacement ; journal.
- `make demo` : l'ITIG reçoit une grille, ses salles et ateliers, des règles (dont l'atelier de la 2HT Électricité le lundi de la 2e à la 7e heure) et un horaire publié **calculé une fois** ; le scénario de `core/tests/test_demo.py` vérifie qu'il est complet et sans conflit (pas de nouveau `make demo` dans un test).

## 15. Hors périmètre (pour l'instant)

Horaire différent selon les semaines (A/B) ou les trimestres ; demi-classes qui alternent une semaine sur deux ; remplacement automatique d'un absent ; enseignant partagé vu des deux écoles ; appel en classe (V1.5) ; paie (7.3). Chacun se discute quand une école le demande.
