# Tâche 5.1 — Identité de la plateforme

**Serveur (`core`)** : modèle `PlatformSettings` (une seule ligne, pas `TenantModel` : donnée de la plateforme) — nom, nom court, logo (PNG/JPEG/SVG, règles du logo d'école), icône (PNG carré ≥ 512 px, lue sans Pillow), couleur principale (`lake`) et d'accent (`lamp`) avec contraste vérifié, téléphone et e-mail du support, mentions légales. Valeurs de départ : défauts du modèle (seul endroit du code où figure « Mwangaza »).
API publique, sur toute adresse (école suspendue ou inconnue comprise) : `GET /api/platform/`, `…/logo/`, `…/icon/`, `…/manifest/<gestion|portail>/` (manifeste servi par le serveur ; icônes par défaut de l'application sans icône).
Lecteurs : administration Django (titre, écran d'édition unique en attendant la console 5.2), émetteur TOTP, gabarits PDF et pages de vérification (`platform` dans le contexte), messages d'erreur et journal (« Support {nom} »).

**Front** : `packages/api` (`loadPlatform`, cache localStorage : hors-ligne), `packages/i18n` (`setPlatformName` → variable `{{platform}}` dans toutes les traductions), `packages/ui` (`PlatformContext`, `Brand` avec le logo, `applyPlatform` : couleurs, favicon). Fournisseur dans chaque application, titres de page, manifeste servi par `/api/platform/manifest/…` (VitePWA `manifest: false`). Contact du support sur « École suspendue » ; mentions légales en lien sous la connexion.

**Tests** : API publique sur école suspendue / portail, refus d'un contraste illisible et d'une icône non carrée, nom changé → titre admin, TOTP, PDF, journal ; `textes.test.ts` et test serveur qui refusent « Mwangaza » dans les textes (traductions, gabarits, index.html, vite.config).

**Décisions** : pas d'écran d'édition dans la Gestion (console 5.2) ; pas de Pillow (icône non redimensionnée : une seule taille déclarée) ; la couleur de fond du menu (basalte) reste du design ; domaine (`mwangaza.school`) reste dans la configuration (`.env`), pas dans les paramètres.
**Risques** : re-rendu des textes quand le nom change (`changeLanguage` sur la même langue) ; premier lancement sans cache : nom vide jusqu'à la réponse.
