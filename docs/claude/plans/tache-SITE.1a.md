# Tâche SITE.1a — Contenus du site : questions, « Prochainement », bandeau

**But** : la communication (droit `platform.site.edit`) tient à jour depuis la console les questions fréquentes (accueil, parents), « Prochainement » et un bandeau d'annonce daté ; le site les lit en base, données structurées et `llms.txt` compris.

**Hors périmètre** : témoignages, écoles de référence, titres de recherche (SITE.1b, #361) ; actualités (SITE.2), photos (SITE.3). Points des modules : restent dans le code (ils décrivent le logiciel, relus en PR).

**Critères d'acceptation**
- `SiteEntry` [G] (`kind` : question de l'accueil / des parents / prochainement, titre et texte fr + en, `position`, `published`) ; `SiteBanner` [G] (une ligne : texte fr + en, lien, `starts_on`, `ends_on`, `active`).
- Migration : les 17 textes actuels repris tels quels (le site ne change pas en ligne), nom de la plateforme lu en base.
- Anglais vide → le français ; texte libre toujours échappé (pas de HTML) ; lien : `https://` ou chemin du site.
- Console : page « Site » (maquette `console/site` d'abord), onglets, liste + éditeur fr / en + aperçu, monter / descendre, brouillon / publié ; 20 entrées au plus par sorte (liste courte, pas de pagination).
- Chaque création, modification, déplacement, suppression au journal de la plateforme (`site.*`).
- Coût serveur : tout le contenu publié en un objet de cache, vidé à chaque changement ; une page = une lecture du cache.

**Tests obligatoires** : 403 hors du droit (test des rôles EQ.1 + garde des points de console) ; brouillon invisible, ordre, repli en français, bandeau hors dates absent ; journal ; cache vidé après un changement.

**Documents** : 05, 06, 03 (journal des décisions), 04 (entités), `reference.md` + `A-FAIRE.md` § 11 (API, écran), 07 § 1/4 et `maquettes/README.md`.

**Risques** : cache des navigateurs 1 h (un changement se voit sous l'heure) ; `make demo` ne touche pas au site réel (contenus créés par la migration).
