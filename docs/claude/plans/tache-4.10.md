# Tâche 4.10 — Guide de la V1.0 en PDF (I5)

**Fichiers** : `frontend/guide/` — `playwright.config.ts` (Django, Gestion, Portail ; `make demo` avant et après), `captures.spec.ts` (connexion avec chaque compte de démo, captures JPEG dans `guide/captures/`, ignoré par Git, puis PDF), `guide.html` (texte du guide, jetons du design, police Atkinson Hyperlegible). Sortie : `docs/guide/guide-v1.0.pdf` (dans Git, à partager). `make guide`.

**Contenu** : la V1.0 en bref ; se connecter (double authentification, PIN, plusieurs écoles) ; rôle par rôle (directeur, promoteur, comptable, caissier, secrétaire, directeur des études, directeur de discipline, enseignant, parent, super-admin, rôle personnalisé) : ce qu'il fait, comment, captures ; hors ligne ; contrôle (audit, annulation à deux, QR) ; ce que la V1.0 ne fait pas encore, V1.1 → V1.4 et V2.

**Décisions** : PDF par Chromium de Playwright (déjà là : aucune dépendance) ; le guide est un document en français (pas un texte d'interface) ; nom de la plateforme et version dans une seule variable du script, remplie dans la page (paramètres de la plateforme après la 5.1) ; la page du guide est sa propre maquette (07 § 1).

**Tests** : aucun test automatique (document) ; le script échoue si un écran attendu manque. Pas dans la CI (trop long, rien à protéger) ; lancé à la fin de chaque version.

**Risques** : captures qui bougent avec les données de démo (choisir des écrans stables) ; poids du PDF (JPEG, échelle 1,5).
