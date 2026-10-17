# Tâche OPS.4 — E-mail professionnel et domaine protégé contre l'usurpation

**But** : `contact@` et `support@mwangazaschool.com` (2 boîtes comprises dans l'offre LWS : pas d'offre à comparer) ; MX, SPF, DKIM, DMARC dans Cloudflare, vérifiés et notés ; `make deploy-check` signale s'ils disparaissent.

**Constat du 2026-10-17 (`dig`)** : les enregistrements de LWS sont déjà dans Cloudflare (importés avec la zone) — MX `mail.mwangazaschool.com` (10), SPF unique en `-all`, DKIM au sélecteur `dkim` (RSA 1024, clé de LWS), DMARC `p=quarantine` **sans rapports**. Restes inutiles de l'import : `ftp` (nuage orange, vers l'hébergement LWS, non utilisé).

**Hors périmètre** : envoi d'e-mails par l'application (aucun aujourd'hui, pas d'Amazon SES) ; changement de fournisseur ; clé DKIM 2048 (choix de LWS).

**Décisions (regard senior)** : rapports DMARC reçus par la gestion DMARC de Cloudflare (gratuite, beta) et non dans `contact@` (des XML chaque jour dans 1 Go) ; on garde `quarantine` (déjà protecteur) et on passe à `reject` après deux semaines de rapports propres (vers le 2026-10-31) ; comptes et alertes restent sur ta boîte personnelle (OPS.3).

**Critères d'acceptation** : ligne « e-mail » dans `make deploy-check` (MX, SPF, DKIM, DMARC ; ATTENTION si absent, double SPF ou `p=none`), DNS par HTTPS (bibliothèque standard, pas de dépendance) ; enregistrements notés dans `infra/README.md` ; ta part pas à pas dans `A-FAIRE.md`.

**Tests obligatoires** : aucun test automatique (script de la machine, pas de code de l'application) ; essai réel de `domaine.py` sur le vrai domaine et sur un domaine sans DMARC.

**Documents à mettre à jour** : `infra/README.md`, `A-FAIRE.md` (« Maintenant » 5 ter, § 9 octies ligne 10, § 9 nonies 3 c et 4 b), `05`, `06`, `03` (journal des décisions), `docs/claude/reference.md` et skill `deployer` si elles décrivent `deploy-check`.

**Risques** : boîtes pas encore créées chez LWS (seul ton essai d'envoi le prouve, le port 25 est fermé depuis ta machine) ; `dns.google` injoignable → « non vérifié », jamais d'échec.
