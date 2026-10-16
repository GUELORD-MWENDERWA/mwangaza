# Tâche 8.5.1c — Application : cote proposée et corrigée par le titulaire

**But.** Cote d'application de chaque période proposée d'après le pourcentage de la période (mêmes cotes TB à MA que la conduite), corrigée par le titulaire avec motif ; remplit la ligne Application du bulletin.

**Hors périmètre.** Correction par la délibération (8.4 réutilisera le service) ; seuils réglables par l'école (seuils des mentions, `07` I15, tant qu'ils ne sont pas confirmés) ; avis aux parents.

**Critères d'acceptation.**
- `ApplicationGrade` [T] (enrollment, term, grade, reason, corrected_by) : seule la correction est stockée, la proposition se lit des notes (jamais figée).
- Proposition : ≥ 80 % TB, ≥ 70 B, ≥ 60 AB, ≥ 50 ME, sinon MA ; sans note dans la période : pas de proposition (case vide au bulletin).
- Qui corrige : titulaire de la classe ou `grades.enter_any`, côté serveur ; motif obligatoire ; audit `application.grade_overridden`.
- API : `GET class-groups/<id>/application/` (élèves × périodes : pourcentage, proposée, retenue, motif) ; `PUT/DELETE application/enrollments/<id>/`.
- Bulletin : ligne Application remplie (corrigée sinon proposée). Écran « Application » (maquette dessinée) : tableau de la classe + dialogue « Corriger ».

**Tests obligatoires.** Droit (autre enseignant 403, titulaire ok) ; motif, audit, retour à la proposition ; cote du bulletin ; isolation entre écoles.

**Documents à mettre à jour.** 04, 05, 06, 03 (journal), reference.md, A-FAIRE § 11, 07 §1/§4, maquettes/README, import_cancellation.

**Regard senior.** Cote non stockée, comme la conduite ; les pourcentages viennent du rapport de classe déjà calculé (aucun calcul de plus) ; une requête pour les corrections de la classe.
