# Lot 5 — Console finie

**But** : l'équipe de la plateforme pilote ses affaires depuis la console : voir où en sont les écoles (essai, payante, retard, départ), suivre les prospects jusqu'à la signature, créer une école avec ses modules, et rendre ses données à une école qui part.

## Parties
- [x] ① CON.1 tableau de bord des affaires (chiffres en SQL, cache 5 min, exports Excel) + CON.2 fiche d'école, cycle de vie, export complet à la résiliation
- [x] ② CON.3 prospects : suivi commercial des demandes de démonstration, rappels, « Créer l'espace d'essai »
- [ ] ②bis-a **Console réelle / démonstration** (demande du 2026-11-04) : interrupteur de mode, données fictives jamais mêlées aux réelles (serveur)
- [ ] ②bis-b **Console refaite comme la Gestion** : coquille à barre latérale, interrupteur et bandeau de mode, tableau de bord et pages repositionnés (maquette d'abord)
- [ ] ③ IA.1.2 page « IA » et carte de la fiche d'école ; S.8 alertes de sécurité (carte « Sécurité » de la santé)
- [ ] ④ MOD.1 registre des modules (champs, réglages, rôles, widgets, documents), forfaits de départ à la création d'une école, matrice de tests par forfait

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
