# Tâche WEB.1d — Demande de démonstration, adresse et réseaux sociaux

**But** : le formulaire de la page Démonstration (`maquettes/site/demonstration.html`) range la demande dans la console (`DemoRequest`, modèle de plateforme), alerte le super-admin (écran abonné + e-mail si le serveur a une boîte d'envoi) ; l'identité de la plateforme gagne une adresse postale et six liens de réseaux, lus par le pied de page, la page Démonstration et `sameAs`.

**Hors périmètre** : comptes des réseaux tenus par l'équipe et boutons de partage (SITE.5, après EQ.1) ; transformer une demande en espace d'essai en un clic (on garde le lien vers « Nouvelle école ») ; Amazon SES ou autre service d'envoi.

**Critères d'acceptation** : POST sans JavaScript, CSRF, champs obligatoires (nom, fonction, école, ville, téléphone RDC normalisé, consentement) ; champ caché rempli → « merci » sans rien garder ; 6e demande de la même IP dans l'heure refusée ; même téléphone sous 24 h → pas de doublon ni de seconde alerte ; écran console « Demandes » (statuts nouveau, rappelé, espace d'essai ouvert, sans suite ; note interne ; effacement à la demande) ; effacement automatique après un an ; adresse et liens vides = cachés.

**Tests obligatoires** : envoi valide (ligne + alerte), téléphone invalide, champ caché, limite par IP, doublon ; console : 403 pour un compte d'école, liste filtrée, changement de statut ; purge à un an ; lien d'un réseau sur un autre domaine refusé ; `sameAs` et pied de page lisent l'identité.

**Documents à mettre à jour** : `05`, `06`, `03` (journal), `04` (DemoRequest, champs d'identité), `07` § 1, `maquettes/README.md`, `docs/claude/reference.md`, `A-FAIRE.md` (boîte d'envoi sur le serveur, § 11), `infra/.env.example`, `infra/README.md`.

**Regard senior** : pas d'adresse IP gardée (seulement le compteur en cache, 1 h) ; pas de journal d'audit des statuts (ni argent ni notes) ; une purge par jour (une requête) ; la page Démonstration n'est plus gardée par le navigateur (jeton CSRF) : une lecture de plus par visite, négligeable. L'utilisateur n'a pas d'e-mail dans `User` : l'adresse des alertes est un réglage du serveur (`DJANGO_ALERT_EMAIL`, ta boîte personnelle, décidé en OPS.3), envoi par la boîte `contact@` de LWS (SMTP de Django, sans dépendance).

**Risques** : jeton CSRF et page en cache ; `Origin` derrière Caddy ; e-mail lent → tâche Celery ; mots `fr`/`en` du formulaire et de la console (i18n).
