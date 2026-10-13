# Plan M.2.1 — Modules : serveur et tâches de fond (issue #215)

**But** : catalogue complet (`portal`, `notifications`, `offline`) avec dépendances ; le serveur, les tâches de fond, le portail et la synchronisation ignorent une école sans le module.

**Hors périmètre** : écrans (M.2.2), rôles libres (M.3).

**Décisions (regard senior)**
- Dépendances dans `accounts/modules.py` : `finance`→`students`, `portal`→`students`. Activer ajoute ce qui manque ; retirer est refusé tant qu'un module actif en dépend (validé dans le sérialiseur de la console, création comprise).
- Relances = `notifications` + `finance` + `portal` ; caisses ouvertes = `notifications` + `finance`. Le planificateur filtre en une requête (`modules__contains`), le détail par tâche se lit sur la ligne déjà chargée (aucune requête de plus).
- Portail : un seul filtre `School.portal_closed(prefix)` (fermée ou sans `portal`) remplace les 7 exclusions de statut ; connexion/activation refusées (`portal_not_offered`) ; les familles d'une école sans portail ne sont pas listées.
- Sync : l'instantané suit déjà les droits (finance sans `finance`) ; ajout de `offline` en garde (`required_module`) sur la synchro et l'enregistrement d'un appareil.
- Envois d'événements (`events.send`) : rien sans `notifications` ; actualités de la plateforme non concernées.
- Désactiver ne supprime rien (à écrire dans `03`).

**Tests** : sérialiseur (dépendances), tâche de fond saute l'école, portail 403 + liste, sync 403 sans `offline`, isolation.

**Documents** : `03` (journal), `05`, `06`, `reference.md`.
