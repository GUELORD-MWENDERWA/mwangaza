# Tâche L.2 — Restauration réelle depuis B2

**But** : prouver que la dernière copie du stockage objet (B2) se rapatrie, se déchiffre et se restaure ; noter durée et procédure exacte.
**Hors périmètre** : remplacer la base en service (`--remplacer`) sur le vrai serveur ; changer les scripts, sauf bug trouvé.
**Critères** : `make deploy-backup cmd=fetch` puis `cmd=restore` réussis sur le vrai serveur ; nombre d'écoles, élèves, paiements et fichiers vérifiés ; durée notée ; `A-FAIRE.md` « Si le serveur est perdu » à jour ; clé de chiffrement gardée hors serveur (👤).
**Tests** : aucun code ajouté (script déjà couvert) ; l'essai réel est le test.
**Documents** : `05` (case), `06` (suivi, journal), `A-FAIRE.md`.
**Risques** : l'essai se fait dans une base à part, effacée ensuite ; ne rien remplacer en service.
