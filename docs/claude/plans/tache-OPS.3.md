# Tâche OPS.3 — Domaine et comptes de la plateforme protégés

**But** — Un domaine expiré ou volé, ou un compte pris (Cloudflare, AWS, GitHub…), coupe toutes les écoles. Toi : réglages chez LWS et double authentification partout. Claude : tableau « Comptes de la plateforme » (`A-FAIRE.md` § 9 octies), constat public du domaine, et une ligne « domaine » dans `make deploy-check` pour ne plus avoir à s'en souvenir.

**Constat du 2026-10-17 (annuaire public RDAP)** — registraire LWS, expire le 12/10/2027, DNS chez Cloudflare, **verrou de transfert absent** (statut « active » seul), DNSSEC absent.

**Hors périmètre** — e-mail pro, SPF / DKIM / DMARC (OPS.4) ; DNSSEC et enregistrement CAA (regard senior : peu utiles quand tout passe en HTTPS avec HSTS, et une erreur de saisie chez LWS ou Cloudflare rendrait le domaine injoignable pour toutes les écoles) ; aucun mot de passe ni code dans le dépôt.

**Critères d'acceptation** — tableau : service, à quoi il sert, si on le perd, qui y accède, renouvellement et coût, double authentification (case) ; `make deploy-check` affiche « domaine : expire le …, verrou de transfert actif / ABSENT » et avertit (sans échouer) sous 30 jours ou sans verrou ; annuaire injoignable → « non vérifié », jamais d'échec.

**Tests obligatoires** — aucun test automatique (outil d'exploitation sur ta machine, rien dans l'application) : essai réel de `make deploy-check` et de l'annuaire injoignable.

**Documents à mettre à jour** — `A-FAIRE.md` (§ 9, 9 octies, « Maintenant » 5 ter, § 11), `CLAUDE.md` et `docs/claude/reference.md` (`deploy-check`), skill `/deployer`, `infra/README.md`, `03` (journal), `05`, `06`.

**Risques / à vérifier** — `rdap.org` redirige vers l'annuaire du registre (marche pour toute extension, rien en dur) ; Python 3 de la machine, bibliothèque standard seulement.
