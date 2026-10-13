# Tâche L.0 — installer le plan révisé

- **But** : une seule file de tâches ordonnée et validée, que Claude Code suit sans relire l'historique.
- **Hors périmètre** : aucun code applicatif ; jalons et issues GitHub des nouvelles versions (après la fusion).
- **Critères d'acceptation** : `05` remplacé (ancien dans `docs/archives/`) ; versions, sécurité et nouveaux modules cohérents dans `01`, `02`, `03`, `04`, `07`, `06`, `A-FAIRE.md`, `CLAUDE.md`, `README.md`, `maquettes/README.md`, skills `tache` et `etat`.
- **Tests obligatoires** : aucun (documents) ; la CI ne lance rien pour des `.md`.
- **Documents à mettre à jour** : la liste ci-dessus.
- **Risques / vérifié dans le code** : purge absente de `ChangeLog` / `SyncOperation` ; catalogue des modules sans dépendances ; codes de rôle encore lus à 8 endroits ; logos SVG filtrés par liste noire ; Dependabot annoncé mais absent ; journal d'audit déjà protégé par un déclencheur.
