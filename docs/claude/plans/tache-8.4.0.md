# Tâche 8.4.0 — Saisie des points sans devoirs (#293)

**But** : l'école choisit, pour tout l'établissement (`School.settings["grading"]["entry"]`) ou par cours (`Course.grade_entry`, vide = réglage de l'école) : devoirs détaillés (comme aujourd'hui) ou **seulement le total de la période** (ou des examens).

**Choix technique (regard senior)** : en mode « total », la feuille a **une seule évaluation « Total »** dont le maximum est celui de la période (ou le double pour les examens), créée toute seule à l'enregistrement. Rien d'autre à changer : bulletin, fiches de cotes, contrôle (8.2.2) et délibération lisent déjà les évaluations ; aucune seconde table, aucun cas particulier en aval.

**Hors périmètre** : conversion des feuilles déjà saisies. Simplification : une feuille qui a déjà plusieurs évaluations reste détaillée quel que soit le réglage (rien perdu, aucun refus à gérer).

**Critères d'acceptation**
- Réglage d'école (paramètres) et choix par cours (grille des cours), journal.
- Feuille en mode total : une colonne « Total », saisie de 0 au maximum ; ajout/retrait d'évaluation refusé (400).
- Note de période, bulletin et fiches de cotes identiques à un détaillé équivalent.

**Tests obligatoires** : mode total (évaluation unique auto, refus d'évaluation en plus, note de période juste), résolution cours > école, feuille à plusieurs évaluations qui reste détaillée, isolation (réglage d'une école ne touche pas l'autre), permission de réglage, audit.

**Documents** : `04`, `02`, `05`, `06`, `reference.md`, `A-FAIRE.md`, `07` § 4 (démo).

**Risques** : maximum du cours changé après coup (le total suit `term_maximum` à l'enregistrement) ; saisie hors ligne (8.2.3) : la feuille envoie déjà l'évaluation avec son id, vérifier le cas « Total » créé côté appareil.
