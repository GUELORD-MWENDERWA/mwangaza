# Tâche S.2 — Dépendances et secrets surveillés

**But** : failles connues et mises à jour des dépendances surveillées sans effort ; clé poussée par erreur bloquée.

**Hors périmètre** : fusion automatique des PR Dependabot ; analyse CodeQL ; gestionnaire de secrets sur le serveur.

**Critères** : `.github/dependabot.yml` (uv, npm/pnpm, Docker, Actions ; groupé, hebdomadaire) ; `.github/workflows/audit.yml` (`pip-audit` via `uvx`, `pnpm audit --prod --audit-level high`) ; `A-FAIRE.md` : procédure de changement de chaque clé, copie de `serveur.env`.

**Regard senior** : audit dans un workflow à part (main, lundi, PR qui change un verrou) : une faille publiée demain ne bloque pas une PR sans rapport. `pip-audit` lancé par `uvx` : aucune dépendance ajoutée au projet. `pip-audit` n'a pas de seuil de gravité : toute faille échoue, `--ignore-vuln` documenté pour l'exception.

**Tests** : les deux audits lancés en local (aucune faille) ; pas de test Python (configuration seulement).

**Documents** : `05`, `06`, `03` (surveillance, journal), `A-FAIRE.md` (§ 9 sexies bis clés + « Maintenant »), skill `deployer` si clés citées.

**Risques** : clé `DJANGO_SECRET_KEY` : garder l'ancienne dans `DJANGO_SECRET_KEY_FALLBACKS`. Dependabot `uv` : écosystème récent, à vérifier dans Insights › Dependency graph › Dependabot après fusion.
