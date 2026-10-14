# Tâche S.6.2 — Row Level Security : toutes les autres tables d'une école (#242)

**But** : chaque table de `TenantModel` (élèves, familles, années et classes, rôles, notifications, synchronisation, journal d'audit, finance) refuse, dans PostgreSQL même, toute ligne hors de la portée de la connexion.

**Hors périmètre** : tables sans école ou partagées (`School`, `User`, `Membership`, `PushSubscription` à école facultative, `PlatformAuditLog`…) : sans école, ou liens d'un compte avec ses écoles, lus d'une école à l'autre par conception (connexion, choix de l'école).

**Simplification (regard senior)** : plus de liste `row_security.APPS` à tenir : la règle va sur toute table `TenantModel` (une nouvelle n'est jamais oubliée).

**Critères d'acceptation**
- Règle sur toutes les tables `TenantModel` après `migrate`.
- Chemins qui doivent voir toute la plateforme, dans `use_all_schools()` le temps de leur lecture : code famille unique, identifiant déjà pris (élève, inscription), activation et mot de passe oublié du Portail (famille par code), rôles d'un compte dans toutes ses écoles (`/me`, double authentification exigée), planificateur et purges, envoi des notifications, import d'élèves (tâche), `make demo` et remplissage d'une démonstration.
- Contrôle « rôle d'une autre école » qui ne dépend plus de leur visibilité.

**Tests obligatoires** : règle posée sur une table de chaque application ; toute la suite sous le compte des tests ; **requêtes du client de test et tâches Celery partent d'un contexte vide** (comme en production), pour qu'un oubli dans une tâche échoue en test.

**Documents** : `03` § 4 et journal, `05`, `06`, skill `backend`, `A-FAIRE.md` (mise en ligne).

**Risques** : assertions de tests devenues vides sans portée (`assert not X.all_schools.exists()`) ; `refresh_from_db` hors portée ; tâches Celery qui héritaient du contexte en test.
