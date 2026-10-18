# Tâche NB.1 — Carnet de l'enseignant et fiche de cotes

**But** : les évaluations et leurs notes ne sont lues et modifiées que par l'enseignant du cours ; les autres (DE, titulaire, secrétariat) ne reçoivent que la fiche de cotes (un total par élève, au maximum de la période ; examens : leur propre fiche), envoyée et signée par l'enseignant, que le DE valide ou renvoie avec remarques.

**Hors périmètre** : tableau du DE (NB.2), espace du titulaire (NB.3), signature sur la fiche imprimée (une fiche imprimée couvre toutes les périodes), totaux des brouillons dans la fiche imprimée « provisoire » (inchangée).

**Critères d'acceptation**
- `GET/PUT …/grades/` : enseignant du cours (carnet complet) ; `grades.enter_any` sans donner le cours : seulement une feuille « total » (aucune ou une évaluation au maximum), sinon 403 `notebook_private` ; DE, titulaire, préfet : 403.
- `GET …/grades/totals/` (nouveau) : fiche de cotes — totaux seulement, et seulement une fois envoyée ; lue par l'enseignant, le titulaire, `grades.enter_any`, `grades.validate`.
- Envoi = « Envoyer et signer » (qui et quand, déjà gardés) ; notification au DE (coupable dans ses préférences) et au titulaire ; renvoi (`reopen`) = « Renvoyer avec remarques » : motif au journal, notification à l'enseignant, remarques affichées dans son carnet. Statut « renvoyée » = brouillon rouvert (pas de nouveau champ).
- `grading` : même liste qu'avant, plus `teaches` par cours ; la saisie ne propose que ses cours (ou tous en total pour `enter_any`).
- Écran « Fiche de cotes » (`/grade-sheets/totals?course=&term=`), ouvert depuis la validation et les notifications ; maquette d'abord.

**Tests obligatoires** : isolation (fiche d'une autre école : 404) ; 403 sur le détail pour DE, titulaire, préfet ; secrétariat : total oui, devoirs 403 ; fiche sans détail des évaluations, vide avant l'envoi ; renvoi avec motif au journal et notification ; envoi notifie DE et titulaire.

**Documents** : 04 (visibilité), 03 (journal des décisions), 07 § 1, maquettes/README, reference.md, A-FAIRE § 11, 05, 06.

**Risques** : tests existants qui saisissent des devoirs avec le secrétariat (passer à l'enseignant du cours) ; `Record<NotificationKind>` du front (nouvelles sortes) ; message `make messages`.
