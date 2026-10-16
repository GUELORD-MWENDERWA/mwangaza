# PERF.5c — images hors du serveur, minutes et stockage (2026-10-16)

Sources : `docker images` local, `.github/workflows/*.yml`, durées observées des contrôles (≈ 5 min par job, `CLAUDE.md`).
**Estimations, pas des mesures du registre** : la taille réelle se lit après la première construction (GitHub > Packages).

## Tailles
- Locales (non compressées) : backend 611 Mo, caddy 104 Mo (le caddy de production ajoute le binaire Caddy compilé, ≈ +40 Mo).
- Dans le registre, les couches sont compressées (≈ 40 %) et partagées entre versions : les couches de base (Python, Pango,
  environnement `uv`) ne comptent qu'une fois. Ordre de grandeur attendu : ≈ 250 Mo pour la première version, puis
  ≈ 60 à 100 Mo par version qui change seulement le code. Trois versions gardées : probablement 300 à 450 Mo, **près des 500 Mo**.
- Réduction faite : tests et caches Python exclus de l'image (`.dockerignore`). Si le quota se rapproche : garder 2 versions
  (`.[3:]` → `.[2:]` dans `images.yml`).

## Minutes d'Actions par mois en privé (plafond 2 000)
| Poste | Minutes | Fréquence | Total |
|---|---|---|---|
| Contrôles d'une PR (serveur + front + parcours, en parallèle ≈ 15 min de calcul) | 15 | 8 PR | 120 |
| `main` après fusion (tout relancé) | 15 | 8 | 120 |
| Construction des images (à froid 15, avec cache 5) | 8 | 4 déploiements | 32 |
| Audit des dépendances (lundi) | 3 | 4 | 12 |
| **Total** | | | **≈ 300 (15 % du quota)** |

Économies déjà en place : `concurrency` avec `cancel-in-progress` (`ci.yml`, `audit.yml`), `timeout-minutes` sur chaque job,
caches uv, pnpm et (nouveau) Chromium de Playwright, une PR ne lance que les contrôles de ses fichiers, images construites
seulement au déploiement et seulement si l'empreinte du code a changé. Les minutes d'un dépôt privé sont décomptées au
multiplicateur Linux ×1.

## Secours
Quota épuisé : `CONSTRUIRE_SUR_SERVEUR=oui make deploy` (l'ancienne construction sur le serveur, lente, 15 min, priorité basse).
