# Plan IA.1.1 — Socle IA (branche tache/IA.1.1-socle-ia, issue #388)

**But** : l'application `ai` côté serveur : catalogue des usages, cinq verrous (`ai.services.authorize`), un seul fichier qui parle à l'API (`ai/client.py`), registre `AiCall`, cumuls `AiBalance` (crédits du mois) / `AiUsageMonth` / `AiPlatformMonth` (plafond), alertes 80 % et 100 %, purge.
**Hors périmètre** : page console et carte « Crédits IA » (IA.1.2), aucun usage réel (IA.2a, IA.5), assistant (IA.3).

**Critères** : un refus ne coûte rien et dit pourquoi ; coûts en entiers (micro-dollars, 1 crédit = 1 000) ; même demande deux fois = un appel ; session support = compté sur la plateforme ; clé seulement dans `serveur.env`.

**Tests** : isolation (crédits et appels d'une autre école), refus sans `ai.use` / sans permission hôte / sans module hôte, crédits épuisés et plafond atteint sans appel à l'API (client simulé), cumul exact, doublon, support, alertes une seule fois, purge.

**Documents** : `03` (journal des décisions), `04` (modèles), `05`, `06`, `07` § 4, `reference.md`, `A-FAIRE.md` (clé API), `.env.example`, compose.

**Risques / décisions (regard senior)** :
- Pas de réservation de crédits (une ligne lue, pas de verrou) : dépassement borné par 2 appels en cours.
- Texte jamais dans `AiCall` ; la réponse attend dans `AiResult` (supprimée à « gardé » / « abandonné », ou à 24 h) : pas de cache Redis dans ce projet.
- Refus enregistrés (une ligne, clic d'une personne) ; file `ai` : travailleur dédié, 2 appels à la fois.
- Dépendance `anthropic` acceptée le 2026-10-13 (apporte pydantic, httpx2).
