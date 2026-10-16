# Tâche 8.5.1b — Conduite : parents et bulletin

**But.** Le parent est prévenu d'un incident (notification Portail + carte « Conduite » sur la page de l'enfant) ; la cote de chaque période est calculée d'après les points, corrigeable avec motif (`discipline.override`, journal) ; elle remplit la ligne Conduite du bulletin.

**Hors périmètre.** Application (découpée en 8.5.1c, #282) ; correction par la délibération (8.4 réutilisera le service) ; messagerie (8.5.2).

**Critères d'acceptation.**
- `ConductGrade` [T] (enrollment, term, grade, reason, overridden_by) : seule la correction est stockée, la cote calculée se lit des incidents (jamais figée). Droit `discipline.override` (directeur, DD ; écoles existantes par migration).
- Notification `discipline_incident` au parent (Portail, dans la transaction), pas de point ni de motif interne ; PDF du bulletin : colonnes de période de la ligne Conduite remplies (corrigée sinon calculée, seulement si la période a des incidents ou une correction ; sinon « TB »).
- Portail : `GET children/<id>/conduct/` (incidents non annulés, points, cote par période) + carte sur ChildPage.
- Gestion : cote par période et bouton « Corriger » sur la fiche conduite d'un élève.

**Tests obligatoires.** Droit 403 ; correction (motif obligatoire, audit, retour à la cote calculée) ; cote du bulletin ; notification au bon parent seulement ; isolation (portail d'un autre parent/école : 404).

**Documents à mettre à jour.** 04, 05, 06, 03 (journal), reference.md, A-FAIRE § 11, 07 §1/§4, maquettes/README.

**Regard senior.** Cote non stockée = pas de recalcul à synchroniser ni de cote périmée après annulation d'incident ; une requête agrégée par élève. Bulletin : une requête de plus par classe (corrections de la classe), clé du PDF gardé inclut la cote.

**Risques.** Clé des PDF gardés (PERF.2) : la cote doit entrer dans l'empreinte du HTML (elle y est, puisqu'elle est dans le gabarit) ; cache du rapport de classe à ne pas figer.
