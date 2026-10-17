# Serveur Mwangaza et crédits AWS — explication et ajouts au plan

Rédigé le 2026-10-17. Conditions AWS vérifiées ce jour sur les pages officielles (sources en bas). Ajouts au plan validés le 2026-10-17 : bloc OPS de `docs/05` § 4 quater (OPS.3 domaine et OPS.4 e-mail pro ajoutés à ta demande), marche à suivre dans `A-FAIRE.md` § 9 octies.

## Constaté le 2026-10-17 dans la console

Compte ouvert le 12/10/2026 ; crédit « AWS Free Tier » 100 $, du 12/10/2026 au 12/10/2027, 0,11 $ utilisés en 5 jours (l'instance Lightsail semble couverte par un essai : à confirmer sur *Factures*) ; aucune page « Mettre à niveau » : compte très probablement déjà sur le plan payant ; 0 activité sur 5 faite.

Calendrier (estimé) : facture d'octobre début novembre ≈ 0 $ ; essai Lightsail jusqu'à une date à lire dans Lightsail ou *Factures* ; ensuite ≈ 12 à 13 $ / mois pris sur les crédits ; carte débitée seulement quand les crédits sont épuisés ou après le 12/10/2027. Domaine (renouvelé chaque année chez son vendeur), Cloudflare et B2 : hors AWS, pas couverts par les crédits.

À vérifier : la facture montre **Secrets Manager** (0,00 $ pour l'instant), que Mwangaza n'utilise pas (aucune mention dans le code) ; un secret coûte 0,40 $ / mois après 30 jours d'essai. Regarder la liste (région Paris) avant de supprimer quoi que ce soit.

## 1. Ton serveur, en simple

| Élément | Ce que c'est | Prix |
|---|---|---|
| Instance Lightsail `mwangaza-vps-prod` | un ordinateur loué chez Amazon à Paris : 2 Go de mémoire, 2 processeurs, 60 Go de disque, Ubuntu | **12 $ / mois** (avec IPv4) |
| IP statique 15.236.78.55 | l'adresse fixe du serveur, vers laquelle Cloudflare envoie `mwangazaschool.com` | gratuite **tant qu'elle est attachée** (sinon 0,005 $ / heure ≈ 3,60 $ / mois) |
| Dans le serveur | Docker fait tourner Django (l'API), PostgreSQL (la base), Redis, Celery (tâches de fond, impression), Caddy (HTTPS) | — |
| Hors d'AWS | Cloudflare (DNS), Backblaze B2 (copie chiffrée des sauvegardes de chaque nuit), Healthchecks, Sentry, UptimeRobot | gratuits ; **pas payés par les crédits AWS** |

Ce qui est déjà solide : sauvegarde chiffrée chaque nuit copiée hors d'AWS et restauration essayée (L.1, L.2), swap de 2 Go et limites de mémoire (PERF.5a), images construites par GitHub et non sur le serveur (PERF.5c), tableau de santé dans la console (PERF.5b).

Bon à savoir :
- Une instance **arrêtée** (Stop) est facturée pareil. Seule la suppression arrête la facture.
- Lightsail ne « grossit » pas une instance en place : pour passer à 4 Go, on prend un instantané, on crée une instance plus grande depuis cet instantané, puis on y déplace l'IP statique. Cloudflare ne change pas.
- Ne pas passer en « IPv6 seulement » pour gagner 2 $ : l'IP statique ne s'y attache pas, et beaucoup de réseaux en RDC sont encore en IPv4.

## 2. Les crédits AWS : les vraies règles (depuis juillet 2025)

Tout nouveau compte reçoit **100 $ de crédits**, plus **jusqu'à 100 $** en faisant 5 activités (20 $ chacune). À l'ouverture, on choisit un **plan gratuit** ou un **plan payant**. C'est ce choix qui décide de tout :

| | Plan gratuit (Free plan) | Plan payant (Paid plan) |
|---|---|---|
| Tu paies ? | jamais | seulement ce qui dépasse les crédits |
| Fin | **6 mois après l'ouverture du compte, ou crédits épuisés** : le compte est **fermé**, le serveur s'arrête, plus d'accès | le compte ne se ferme jamais |
| Crédits | perdus à la fermeture | restent utilisables **12 mois** après l'ouverture du compte |
| Après | 90 jours pour passer au plan payant, sinon tout est **effacé** (serveur, disque, instantanés) | facturation normale sur ta carte : ≈ 12 à 13 $ / mois aujourd'hui |

### Le piège principal

« On paiera après 6 mois » n'est vrai qu'à moitié. **Si ton compte est sur le plan gratuit, au bout de 6 mois AWS ne te facture pas : il ferme le compte et coupe le serveur.** Compte ouvert vers début octobre 2026 → fermeture vers **début avril 2027**, en plein 3e trimestre, au moment des bulletins et des examens. AWS prévient par e-mail à 15, 7 et 2 jours, mais un e-mail manqué = écoles coupées.

Bonne nouvelle : passer au plan payant **garde les crédits restants** (ils s'appliquent aux factures suivantes). Avec une alerte de budget, il n'y a pas de mauvaise surprise.

### Autres pièges

1. **Crédits limités aux services « participants »** : il faut vérifier que Lightsail en fait partie sur ta facture (étape 2 ci-dessous), pas le supposer.
2. **Activités pour les 20 $** : EC2 (lancer une instance **puis la résilier**), RDS (regarder les options, **ne pas laisser de base allumée**), Lambda, Bedrock (un message dans le playground), Budgets. Une ressource oubliée consomme les crédits. La seule qui sert vraiment : **Budgets**. Les autres sont optionnelles, à faire en supprimant tout derrière.
3. **IP statique détachée** ou **instantanés** oubliés : facturés en continu.
4. **Fin des crédits** (au plus tard 12 mois après l'ouverture, vers octobre 2027) : la carte bancaire est débitée chaque mois. Il faut une carte valide, sinon AWS suspend le compte.
5. **Plus gros serveur = crédits plus vite épuisés** : 4 Go coûte 24 $ / mois (le tableau de `docs/03` dit « ≈ 20 $ », à corriger).

### Combien de temps durent tes crédits (plan payant)

| Serveur | Coût / mois (avec instantanés) | 100 $ | 120 $ (avec Budgets) |
|---|---|---|---|
| 2 Go (aujourd'hui) | ≈ 13 $ | ≈ 7 mois | ≈ 9 mois |
| 4 Go | ≈ 25 $ | ≈ 4 mois | ≈ 5 mois |

## 3. Ce que tu fais dans la console AWS (≈ 15 min, toi)

1. **Voir ton plan** : console AWS → *Billing and Cost Management* → page d'accueil (widget « Free Tier » / *Credits*) : plan gratuit ou payant, solde, jours restants, date d'expiration. Note la date d'ouverture du compte.
2. **Vérifier que Lightsail mange les crédits** : *Billing* → *Bills* : une ligne « Lightsail » avec en face une ligne *Credits* négative. Si Lightsail n'est pas couvert, on le saura tout de suite.
3. **Créer le budget** (gagne 20 $ en même temps) : *Billing* → *Budgets* → *Create budget* → modèle « Monthly cost budget », montant **15 $**, ton e-mail. Ajoute une alerte sur la **prévision** à 100 % et une sur le **réel** à 80 %. Option : un second budget « Zero spend » pour être prévenu au premier centime réellement payé.
4. **Plan payant** : constaté le 2026-10-17 (aucune page « Mettre à niveau ») ; rien à faire.
5. **Lightsail → instance → Snapshots → Automatic snapshots : activer** (un par jour, 7 gardés). Coût ≈ 0,5 à 1 $ / mois : seul l'espace réellement utilisé puis les changements sont facturés (0,05 $ / Go / mois).
6. **Double authentification du compte AWS** : menu du compte (en haut à droite) → *Informations d'identification de sécurité* → *Attribuer un appareil MFA* → application d'authentification. Ce compte (racine) peut supprimer le serveur et dépenser avec la carte.
7. **Alarmes Lightsail** : instance → *Metrics* → alarme sur « Status check failed » et sur CPU > 90 % pendant 15 min, envoyées à ton e-mail (*Alarm notifications*).

## 4. Comment utiliser l'argent sans piège : ma recommandation

- **Rester sur 2 Go** jusqu'aux 2 premières écoles réelles (seuil déjà écrit dans `docs/03`, tableau « Capacité »). Les crédits paient alors ≈ 9 mois de serveur, c'est-à-dire presque toute l'année scolaire 2026-2027.
- **Dépenser un peu en sécurité** : les instantanés automatiques (≈ 1 $ / mois) donnent un retour arrière du serveur entier en quelques minutes, en plus des sauvegardes B2 qui protègent les données.
- **Une répétition du passage à 4 Go** sur une copie temporaire (créée depuis un instantané, supprimée dans l'heure) : quelques centimes, et le jour où il faut grossir, la procédure est sûre.
- **Alléger l'application plutôt que payer plus** : l'écran « Impayés » prend ≈ 90 Mo par requête et le tableau de bord ≈ 57 Mo (`docs/03`). Les réduire repousse le passage à 4 Go, donc fait durer les crédits.
- **Ne pas** ajouter de services AWS en plus (RDS, S3, CloudFront…) : la stack décidée (un serveur + B2 + Cloudflare) est déjà la moins chère, et chaque service ajouté est une ligne de facture de plus après les crédits.

## 5. Ajouts proposés au plan (`docs/05`)

| # | Tâche | Prio | Taille | Qui | Où dans la file |
|---|---|---|---|---|---|
| 14 bis | **OPS.1** Compte AWS sans piège : plan vérifié, budget 15 $ et alertes, double authentification du compte AWS, dates notées | P0 | S | 👤 (Claude écrit la marche à suivre) | avant 🚀 Premier espace réel |
| 14 ter | **OPS.2** Instantanés automatiques et alarmes Lightsail, restauration d'un serveur entier depuis un instantané essayée une fois | P0 | S | 🤖 + 👤 | avant 🚀 Premier espace réel |
| 19 bis+ | **OPS.3** Passage à 4 Go préparé : procédure écrite (skill `/deployer`, `A-FAIRE.md`), seuils tirés de la carte Santé, répétition sur une copie temporaire ; tableau « Capacité » de `03` corrigé (24 $) | P1 | S | 🤖 + 👤 | avec PERF.6 (V1.2) |
| 19 bis+ | **PERF.7** Écrans « Impayés » et tableau de bord plus légers (calcul en SQL, pas d'objets Python par frais), mémoire mesurée avant et après avec `make perf` | P1 | S à M | 🤖 | juste après PERF.6 |

Détail pour Claude Code :

- **OPS.1** *(P0, S)* — Claude : section `A-FAIRE.md` § 9 octies « Compte AWS et crédits » (les étapes 1 à 4 et 6 du § 3 ci-dessus, avec les chemins exacts de la console) ; ligne dans « Maintenant » ; entrée au Journal de `06` ; décision au Journal de `03` (« plan payant + budget 15 $ ; crédits jusqu'à leur fin, puis ≈ 13 $ / mois »). Toi : faire les étapes, puis noter dans `A-FAIRE.md` la date d'ouverture du compte, la date d'expiration des crédits et le solde. Pas de code.
- **OPS.2** *(P0, S)* — Toi : étapes 5 et 7 du § 3. Claude : procédure « Serveur perdu ou cassé » en deux chemins dans `A-FAIRE.md` § 9 ter et la skill `/deployer` : (a) depuis un instantané Lightsail (nouvelle instance, IP statique déplacée, `make deploy-check`) ; (b) depuis B2 (déjà écrit). Essai réel une fois : instance créée depuis l'instantané de la nuit, `curl` de santé sur son IP provisoire, puis **suppression le jour même** (coût : quelques centimes). Ligne « instantanés » dans `infra/README.md`.
- **OPS.3** *(P1, S)* — Claude : `docs/03` tableau « Capacité » à jour (4 Go = 24 $, 8 Go = 44 $, vérifier les prix du jour), ligne 205 de `03` (« Hetzner… ») remplacée par la réalité (Lightsail) ; procédure pas à pas du passage à 4 Go dans `/deployer` et `A-FAIRE.md` (instantané manuel, nouvelle instance plus grande, IP statique, `make deploy-setup` pour le swap, `make deploy-check`, suppression de l'ancienne après 48 h) ; seuil d'alerte de la carte Santé relié à ce tableau. Toi : la répétition sur une copie, supprimée dans l'heure.
- **PERF.7** *(P1, S à M)* — après PERF.6 : `Impayés` et tableau de bord calculés en SQL (agrégats, pas d'objets Python par frais), `assertNumQueries`, mémoire du conteneur Django mesurée avant / après (`make perf`), limite mémoire du conteneur revue si le gain le permet. Résultat dans `docs/claude/recherches/`.

## Sources

- [Choosing an AWS Free Tier plan (AWS Billing)](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
- [AWS Free Tier Terms](https://aws.amazon.com/free/terms)
- [AWS Free Tier FAQs](https://aws.amazon.com/free/faqs/)
- [AWS News Blog — up to $200 in credits](https://aws.amazon.com/blogs/aws/aws-free-tier-update-new-customers-can-get-started-and-explore-aws-with-up-to-200-in-credits)
- [Amazon Lightsail pricing](https://aws.amazon.com/lightsail/pricing)
- [Lightsail — Billing and account management FAQ](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html)
