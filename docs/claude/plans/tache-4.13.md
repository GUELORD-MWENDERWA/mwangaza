# Tâche 4.13 — Import : matricule jamais imposé (issue #156)

**Cause trouvée (Q14)** : la colonne est facultative dans le code et à l'écran. Le blocage vient d'une colonne « Matricule » présente mais remplie de valeurs d'attente (« - », « 0 », « néant », « N/A ») : la 2e ligne et les suivantes sont refusées, « Matricule répété ». Rien ne dit non plus que la colonne est facultative (modèle Excel, étape « Colonnes »).

**Serveur**
- `students/imports.py` : valeur d'attente = matricule vide (`_matricule`) ; modèle Excel : colonnes facultatives titrées « … (facultatif) » (les parenthèses sont déjà ignorées à la lecture) ; `run` ne crée un matricule que si l'école le demande.
- `schools` : `School.auto_matricule` (oui par défaut, donc oui pour les écoles existantes), migration ; lu et écrit par `/api/matricule-format/` (droit `classes.manage`, journal) ; lu par `/api/school/` pour l'écran d'inscription.
- `students/services.py` : `enroll` ne donne un matricule que si l'école le demande.
- Documents PDF (fiche d'inscription, relevé, reçu du portail, liste de classe) : ligne ou colonne « Matricule » absente quand il n'y en a pas.

**Gestion**
- `MatriculeCard` : interrupteur « Attribuer un matricule automatiquement » ; format grisé sur non.
- Import, étape « Colonnes » : « Facultatif » au lieu de « Non utilisé », visible aussi sur téléphone.
- Inscription : champ « Généré automatiquement » absent sur non ; message de fin sans matricule.
- Reçu, annulation, preuve d'avoir, caisse : pas de « Matricule » ni de « · » orphelin.

**Tests** : valeurs d'attente importées sans matricule (répétition d'un vrai matricule toujours refusée) ; interrupteur sur non → ni import ni inscription n'en créent ; droit `classes.manage` et isolation de l'interrupteur ; journal ; Vitest : interrupteur, reçu sans ligne vide.

**Regard senior — retiré ou simplifié** : un seul interrupteur, sur la carte « Format du matricule » déjà là (même droit, même API) plutôt qu'un nouvel écran ; pas de saisie du matricule à l'inscription (il vient de la colonne de l'import ou de « Modifier » sur la fiche, déjà là) ; fiche élève : « Matricule : — » gardé (le secrétariat voit qu'il manque) ; aucune requête ajoutée (l'école est déjà chargée).
