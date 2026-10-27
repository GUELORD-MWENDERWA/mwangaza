# Tâche R.1 — Import du personnel depuis Excel

**But** : créer d'un coup les comptes du personnel d'une école (une soixantaine à l'ITIG) depuis un fichier Excel ou CSV, puis imprimer une lettre d'accès par nouveau compte.

**Hors périmètre** : choix des colonnes à la main (modèle fixe, titres reconnus comme pour les élèves) ; envoi des accès par SMS ; changer un compte existant (noms, rôles) par l'import.

**Critères d'acceptation**
- « Comptes du personnel » → « Importer depuis Excel » (`/staff/import`), droit `roles.manage` (celui de l'écran ; le plan disait `staff.manage`, qui n'existe pas). Modèle Excel : NOM, POST-NOM, PRÉNOM, TÉLÉPHONE, RÔLES (plusieurs séparés par « , » ou « ; »), noms des rôles de l'école rappelés à l'écran.
- Aperçu sans rien écrire (comme la reprise des résultats, 8.4.7 : ni table ni tâche de fond) : prête, ignorée (déjà dans l'école : renvoyer le fichier ne crée rien deux fois), erreur (nom manquant, numéro invalide, numéro de démonstration dans un vrai espace ou l'inverse, rôle manquant ou inconnu, même numéro qu'une ligne plus haut). L'aperçu ne dit pas si un numéro a déjà un compte ailleurs (B3).
- Enregistrement : même fichier renvoyé avec le nombre de lignes prêtes, revérifié sous verrou (409 `preview_outdated` sinon), en une transaction et par lots (pas une requête par ligne). Nouveau compte sans mot de passe utilisable, `must_change_password` ; numéro connu : appartenance ajoutée, son mot de passe habituel. Journal `staff.added` par personne, alerte « droits sensibles » comme l'ajout seul. 150 lignes au plus.
- Lettres d'accès (PDF, deux par A4, comme les invitations H7) : le mot de passe provisoire est créé à l'impression (Argon2, 0,1 à 0,2 s chacun, donc 50 lettres par PDF au plus) ; seulement les comptes jamais connectés, gérés par cette école ; journal `staff.password_reset`. Réimprimer remplace le mot de passe de la lettre précédente.

**Regard senior** : pas de hachage pendant l'import (60 × 0,2 s qui bloqueraient les connexions du processus) ; lettres réimprimables au lieu de mots de passe perdus si la page se ferme ; pas de modèle ni de Celery pour 60 lignes.

**Tests** : isolation (école B : ni aperçu ni lettre des comptes de A), 403 sans `roles.manage`, règles de l'aperçu, fichier renvoyé deux fois, audit, mot de passe de la lettre valable et compte déjà connecté exclu.

**Documents** : 05, 06, `reference.md`, `A-FAIRE.md` § 11, `07` § 1, `maquettes/README.md`, `03` journal des décisions.

**Risques** : longueur de l'URL des lettres (50 identifiants ≈ 1,9 Ko, limite Gunicorn 4 Ko) ; compte parent sans connexion (lettre possible : il n'a pas encore de mot de passe choisi).
