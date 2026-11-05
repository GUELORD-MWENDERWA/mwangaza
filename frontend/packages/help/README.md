# @mwangaza/help

Bouton « Aide » et panneau (AIDE.2), dialogue « Quoi de neuf » (AIDE.1) des trois applications.
Les textes viennent du serveur (`/api/help/…`, `/api/console/help/…`, articles dans
`backend/apps/core/help/`) ; chaque application passe seulement la clé de l'article de l'écran
ouvert (`screens.ts` de l'application, vérifié par un test : chaque écran a son article fr + en).
