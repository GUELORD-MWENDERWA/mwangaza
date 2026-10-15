# Tâche 8.2.3 — Notes hors ligne

**But** : saisir les notes sans réseau. La feuille et la liste des cours sont gardées sur l'appareil (Dexie) à chaque lecture en ligne ; un enregistrement hors ligne devient l'opération `grades.save` de la file, envoyée à la reconnexion.

**Hors périmètre** : envoi, validation, réouverture (restent en ligne : décision du directeur) ; modification d'une feuille déjà envoyée hors ligne (motif exigé : écran verrouillé hors ligne) ; descente des feuilles par `pull` (lecture à l'ouverture).
**Retiré (regard senior)** : pas de nouvelle ligne `ChangeLog` pour les notes (une feuille = ~40 lignes × cours : trop lourd pour l'instantané) ; la feuille se garde quand on l'ouvre en ligne.

**Critères d'acceptation**
- `POST /api/sync/push` accepte `grades.save` (mêmes champs que `PUT …/grades/` + `course`, `term`) ; droit `grades.enter` / `enter_any` / `validate` ; cours non noté par le compte : 403 refusé ; erreurs du service (`deadline_passed`, `sheet_validated`, `reason_required`…) = opération refusée, gardée visible.
- Même opération reçue deux fois : une seule application. Nouvelle évaluation : identifiant UUID v7 de l'appareil.
- Écran : feuille et liste lues depuis l'appareil si le serveur est injoignable ; enregistrement hors ligne = file + copie locale mise à jour (bandeau « en attente d'envoi ») ; refus montré sur la feuille.

**Tests obligatoires** : pytest (isolation entre deux écoles, 403 cours d'un autre, doublon, date limite → refusée) ; Vitest (copie locale + file) ; Playwright réseau coupé : deux notes saisies, réseau rétabli, une seule feuille à jour, rechargement hors ligne.

**Documents** : 03, 05, 06, reference.md, A-FAIRE § 11, skill hors-ligne.
**Risques** : ne pas écraser la copie locale par une lecture serveur tant que des opérations de la feuille attendent.
