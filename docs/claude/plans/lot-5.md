# Lot 5 — Console finie

**But** : l'équipe de la plateforme pilote ses affaires depuis la console : voir où en sont les écoles (essai, payante, retard, départ), suivre les prospects jusqu'à la signature, créer une école avec ses modules, et rendre ses données à une école qui part.

## Parties
- [x] ① CON.1 tableau de bord des affaires (chiffres en SQL, cache 5 min, exports Excel) + CON.2 fiche d'école, cycle de vie, export complet à la résiliation
- [x] ② CON.3 prospects : suivi commercial des demandes de démonstration, rappels, « Créer l'espace d'essai »
- [x] ②bis-a **Console réelle / démonstration** (demande du 2026-11-04) : interrupteur de mode, données fictives jamais mêlées aux réelles (serveur). Fait : `accounts/console_mode.py` ; réel = espaces réels + essais, démonstration = espaces de démonstration ; **équipe** commune aux deux modes (page en réel seulement, comptes de l'équipe listés en réel) ; « Créer une démonstration » seulement en mode démonstration ; journal fictif déduit de l'objet (`record_platform`). **Le front n'envoie pas encore l'en-tête** : démonstrations invisibles dans la console jusqu'à ②bis-b
- [x] ②bis-b **Console refaite comme la Gestion** (maquettes `console/tableau-de-bord` et `console/menu` refaites) : coquille de la Gestion, interrupteur gardé sur l'appareil (`lib/mode.ts`, en-tête sur chaque appel), bandeau orange, pages du réel cachées et « n'existe qu'en mode réel » si on y va ; recherche Ctrl K (écoles et comptes), état des services (`/api/console/health/`, gardé 1 min), journal, compte ; tableau de bord : « À faire aujourd'hui » (`todo`) et « Dernières activités » (`recent`) selon les droits et le mode. Accueil d'un commercial : « Affaires » (première page de son menu)
- [x] ③a **IA.1.2** (2026-11-04) : page « IA » (`/ai`, droit `platform.ai.manage` : propriétaire, technique, finance), carte « IA » de la fiche d'école, « Crédits IA » des paramètres de la Gestion, boutons IA grisés avec la raison. Les deux modes : en démonstration, consommation fictive (`ai/demo.py`), sans plafond ni réglages (404). Module « IA » cochable dans « Fonctions de l'école » (il manquait). Pas de cache : cumuls déjà tenus, quelques requêtes groupées
- [x] ③b **S.8** (2026-11-04) : détection au moment de l'événement (`audit/security.py`) — rafale de connexions ratées (adresse, numéro, plateforme), export inhabituel (fichiers ou lignes par compte et par heure, 5 exports branchés), annulations hors norme (seuil et moyenne des 30 jours), appareil déconnecté qui insiste ; alerte `security.*` au journal de la plateforme + écran de l'équipe (droit journal), une par sujet et par jour ; carte « Sécurité » (maquette dessinée) ; journal ouvrable sur `?domain=security`. Seuils à valider (`03`)
- [x] ④ **MOD.1** (2026-11-04) : registre `FEATURES` (`accounts/modules.py`) + `School.applies()` + `features` dans `/me` ; branché où il sert : champs de la fiche élève (bulletin), import, sections des paramètres, mise en route, rôles du modèle de départ (ajoutés quand un module arrive, au journal). **Forfaits = offres de « Facturation »** (`Plan`) + « Sur mesure » à la création ; devises seulement avec la caisse. Matrice par forfait (élèves seuls, élèves et caisse, complet). Widgets et documents : déjà filtrés par les droits (M.2), pas d'entrée sans usage ; premier écran : le tableau de bord pour tous les modules d'aujourd'hui, la Sonnerie au lot 16

## Décisions (regard senior)
- Pas de nouveau statut : « résiliée » = `School.Status.STOPPED` + motif et date au journal de la plateforme ; « archivée » = arrêtée, export remis, plus de connexion.
- Prospects : on **étend `DemoRequest`** (étapes, responsable, relance, motif de perte) au lieu d'un nouveau modèle ; anciennes étapes migrées (`called`→contactée, `dropped`→perdue).
- Tableau de bord : un seul appel, résultat gardé 5 min (cache), espaces réels seulement, montants jamais additionnés entre devises ; exports Excel en flux, avec `openpyxl` (déjà une dépendance).
- Export complet : tâche Celery, fichier à lien signé de 7 jours, nettoyé ensuite ; jamais pendant la requête.

- Partie ① (2026-11-03) : « Affaires » est une **page à part** (`/business`, menu « Affaires ») et non un ajout au tableau de bord : elle suit d'autres droits (finance, commercial) et le tableau de bord reste léger. L'export complet est un **classeur Excel seul** : le PDF d'origine ne dirait rien de plus et pèserait des centaines de pages ; décision à valider. Le contact de l'école (`School.contact_*`) reçoit l'e-mail de chaque changement d'état ; sans adresse ou sans serveur d'envoi, le journal reste la trace.

- Partie ② (2026-11-03) : `DemoRequest` étendue (6 étapes, `assignee`, `follow_up_on`, `lost_reason`, `school_code`) ; le lien vers l'essai est un **code** et non une clé vers `School` (supprimer l'essai ne doit pas toucher l'historique commercial, et `schools/deletion.py` l'aurait traité comme une ligne de l'école). Rappel : tâche du matin (7 h) qui prévient seulement le responsable le jour dit ; une relance dépassée est montrée « en retard », pas répétée. Pas d'entrée de journal pour les changements de prospect (ni finance, ni notes, ni paie, ni rôles) : `updated_at` suffit.

## Console réelle / démonstration (②bis, décisions du 2026-11-04)
- **Interrupteur, pas deux consoles** : en-tête `X-Console-Mode: live|demo` (défaut `live`, jamais de fictif) lu par un mixin ; chaque point d'API de la console filtre : écoles par `environment`, factures, appareils et comptes par l'école, **champ `is_demo`** (nouveau) sur `DemoRequest`, `PlatformAnnouncement` et `PlatformAuditLog`, équipe et comptes par numéro fictif (`is_demo_phone`). Le groupe « Site » (site public, un seul) n'existe qu'en mode réel. « Affaires » ne mêle jamais les deux.
- Créer une école de démonstration appelle `ensure_demo_console()` (prospects, annonces, journal fictifs, s'ils manquent) ; test : matrice « rien de réel en démonstration, rien de fictif en réel » sur chaque point d'API.
- **Coquille comme la Gestion** : barre latérale 256 px (marque + étiquette Console, interrupteur de mode en haut, titres de groupes : Pilotage, Clients, Contenu du site, Plateforme), barre du haut (recherche d'écoles et de comptes, état des services, alertes, compte), tiroir sous 900 px, bandeau orange en mode démonstration. Tableau de bord : chiffres du haut, puis « À faire aujourd'hui » (relances en retard, essais qui finissent, impayés, alertes) à gauche et santé des services avec dernières activités à droite. Remplace les groupes déroulants du lot (6b041dbb).

## Hors périmètre
Facturation en ligne, relances automatiques aux écoles (ABO existant), page Équipements (lot 16).

## Critères d'acceptation
Chaque rôle de l'équipe ne voit que ce que son droit permet (commercial : prospects et essais seulement) ; changement d'état = journal + e-mail à l'école ; données d'un espace réel jamais effacées ; création d'une école ne montre que les réglages de ses modules.

## Tests obligatoires
Droits par rôle (403), isolation (export d'une école ne contient rien d'une autre), argent par devise, audit des changements d'état, lien d'export expiré, matrice par forfait (Sonnerie seule, Présences, Gestion complète).

## Documents à mettre à jour
`reference.md`, `A-FAIRE.md` § 11, `04` (DemoRequest, états), `03` journal, `07` § 1 et § 4, `maquettes/README.md`, `docs/specs/equipements.md` § 1 bis, 05 (cases), 06.

## Risques / à vérifier
Requêtes du tableau de bord sur 100+ écoles ; `make demo` : prospects à toutes les étapes ; `import_cancellation.py` non concerné (pas de clé vers un élève).
