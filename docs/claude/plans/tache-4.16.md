# Tâche 4.16 — Supprimer un espace d'essai ou de démonstration

Issue #159 · branche `tache/4.16-supprimer-espace` · règles : `03` § 4 bis (« Effacement »), `02` A5.

**Serveur** (`apps/schools` ; trois migrations : un état de plus, déclencheurs d'immuabilité de `finance` et d'`audit` précisés)
- `School.Status.DELETING` (« suppression en cours », état fermé) : l'adresse répond « école introuvable », `/api/me/` ne la propose plus, `save_school` refuse tout changement.
- `services.delete_space(school, actor, confirm)` — dans la requête : refus pour un espace réel, code retapé exigé, une suppression à la fois (refus si un autre espace est en cours), comptes restés sans école désactivés (un seul `UPDATE`), journal de la plateforme (`school.deleted`, nombre de comptes désactivés), puis tâche de fond.
- `apps/schools/deletion.py` — la tâche : `plan()` trouve seul tous les modèles d'une école (`TenantModel`, `Membership`, `PushSubscription`, tables de liaison), les ordonne (enfants d'abord) et les vide par paquets de 2 000 lignes, sans passer par les protections Python (seule exception à « paiements immuables ») ; fichiers (photos, pièces jointes, logos) effacés ; ligne `School` en dernier. Rejouable après une panne ; verrou PostgreSQL contre deux passages en même temps.
- Dans la base : les déclencheurs d'immuabilité (paiements, clôtures, taux, journal de l'école) laissent partir une ligne seulement si son école est un espace non réel en cours de suppression ; jamais de modification ; journal de la plateforme inchangé.
- Garde-fou : un futur modèle global qui pointe vers une école fait échouer `plan()` (donc le test) au lieu d'être vidé par erreur.
- API console : `POST /api/console/schools/{id}/delete/` (`{confirm}`) → 204.

**Console** (`features/schools`) : « Supprimer » sur la fiche d'un espace d'essai ou de démonstration, confirmation en tapant le code ; état « Suppression en cours », « Relancer la suppression » si elle s'est interrompue ; liste rafraîchie tant qu'une suppression court. Maquette `console/ecoles` : confirmation ajoutée.

**Tests** : permission (super-admin seul) ; espace réel refusé et intact ; mauvais code refusé ; école de `make demo` supprimée en entier (aucune ligne d'aucun modèle, contraintes vérifiées à chaque étape) pendant que l'autre école garde **exactement** ses lignes ; comptes sans autre école désactivés, les autres non ; journal ; état « suppression en cours » = plus d'accès ni de changement. Vitest : bouton absent d'un espace réel, confirmation par le code.

**Regard senior — retiré ou simplifié**
- Pas de motif demandé (le plan ne l'exige pas ; retaper le code suffit) ; pas de barre d'avancement (quelques secondes).
- « Une à la fois » par un refus dans la requête, pas par une file d'attente : pas de tâche qui attend en bloquant un des deux processus Celery.
- Désactivation des comptes dans la requête, pas dans la tâche : rien à rejouer après une panne, et le journal en garde le nombre avec l'adresse IP.
- Les comptes ne sont jamais supprimés (auteurs du journal) ; `make demo` inchangé (aucun nouveau modèle).
