# Tâche 4.21 — Recette finale (plan)

Issue #165 · branche `tache/4.21-recette-finale` · 2026-10-11

1. **Revue rôle par rôle** : parcours Playwright provisoire (jamais commité) sur `make demo`, à 390 px, en français puis en anglais — les 8 rôles de la Gestion, le parent du Portail, le super-admin de la console, tous les écrans. Il relève : erreur JavaScript, réponse d'API en erreur, clé de traduction affichée telle quelle, français resté en anglais, page plus large que l'écran. Petits défauts corrigés ici ; un gros défaut devient une tâche dans `05`.
2. **Mesure** : base à part (`mwangaza_mesure`, effacée à la fin) avec plusieurs écoles remplies par `core.demo.fill` ; nombre de requêtes et temps du tableau de bord, des impayés, de la recherche de la caisse et de la première synchronisation ; `EXPLAIN` de ce qui est lent, correction (index, requête), chiffres au journal.
3. **Guide** : `frontend/guide` complété par les espaces (console : onglets, fiche d'accès ; bandeau), `make guide`.
4. **`make reseau`** relancé une fois à la fin, puis vérifié (trois applications, certificat, même adresse).
5. **Documents** : « Le jour du lancement » dans `A-FAIRE.md` ; `05`, `06`, `03`, `reference.md`.

## Regard senior — retiré ou simplifié
- Revue **sur le serveur de démonstration en ligne** : il n'existe pas encore (action de l'utilisateur, « quand tu veux »). Faite sur la machine et sur `make reseau`, qui utilise les mêmes images.
- Revue **sur un vrai téléphone** : Claude ne peut pas ; largeur de téléphone dans Chromium, le vrai téléphone reste dans « À tester toi-même ».
- Pas de commande `make recette` : `make guide` repasse déjà sur tous les écrans à chaque version.
- Mise à jour avec des opérations en attente : déjà construite et testée (proposée, jamais imposée, installée quand la file est vide ; schéma Dexie seulement complété). Vérifiée par relecture, pas de parcours à deux versions (lourd, fragile).

## Tests
Seulement ceux qu'une correction demande (requêtes d'un écran lourd, permission). Risque : la taille des corrections n'est connue qu'après la revue.
