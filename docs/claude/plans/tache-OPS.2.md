# Tâche OPS.2 — Instantanés et alarmes Lightsail, retour d'un serveur entier

**But** : pouvoir remettre le serveur entier en ≈ 15 min (instantané Lightsail) en plus de la restauration depuis B2 (≈ 1 h, L.2), et l'avoir essayé une fois.

**Hors périmètre** : outil `aws` en ligne de commande (nouvelle dépendance, et la console suffit pour un geste rare) ; script qui crée l'instance ; instantanés vers une autre région.

**Critères d'acceptation**
- Toi : instantanés automatiques (01:00 UTC, 7 gardés) et deux alarmes actifs sur `mwangaza-vps-prod` (alarmes et IP statique déjà faites).
- `make deploy-check ip=<IP>` vérifie HTTPS, certificat et santé d'une instance sur son IP provisoire (`curl --resolve`), sans toucher au DNS.
- Procédure « Serveur perdu ou cassé » en deux chemins : `A-FAIRE.md` § 9 ter et skill `/deployer` : (a) instantané → nouvelle instance → pare-feu 443 (les règles ne sont pas copiées) → `deploy-check ip=` → IP statique déplacée ; (b) B2 (déjà écrit, L.2).
- Essai réel : instance créée depuis un instantané, `deploy-check ip=` vert, instance et instantané manuel supprimés le jour même ; résultat noté.

**Tests obligatoires** : aucun test automatique (script d'exploitation, pas de code de l'application) ; l'essai réel fait foi.

**Documents à mettre à jour** : `A-FAIRE.md` § 9 ter, 9 octies, § 11 ; skill `deployer` ; `infra/README.md` ; `CLAUDE.md` et `reference.md` (`ip=`) ; `05`, `06`, `03` (journal des décisions).

**Risques / à vérifier** : la copie lance aussi la sauvegarde de 0 h 30 et le planificateur (relances) → essai de jour, supprimée dans l'heure ; supprimer l'ancienne instance efface ses instantanés automatiques → la garder arrêtée tant que la nouvelle n'a pas les siens ; réglages par instance (alarmes, instantanés, pare-feu) à refaire sur la nouvelle.
