# Tâche 8.5.1a — Conduite : barème et incidents

**But.** Le directeur de discipline tient la liste des infractions (points) et les seuils des cotes TB à MA ; tout enseignant attribue une infraction à un élève ; liste des incidents d'un élève avec points et cote proposée par période.

**Hors périmètre (8.5.1b).** Parent prévenu (notification, Portail), cote de conduite stockée et ligne du bulletin, correction (`discipline.override`), Application.

**Critères d'acceptation.**
- `DisciplineRule`, `ConductScale`, `DisciplineIncident`, `IncidentCancellation` (isolés par école) ; points copiés à l'attribution ; incident jamais modifié ni effacé, annulé par une ligne liée avec motif.
- Droits `discipline.configure` / `discipline.record` (rôles de départ, migration des écoles existantes d'après leurs droits voisins) ; module `academics`.
- Écrans « Conduite » et « Barème de conduite » d'après les maquettes dessinées, 390 et 1440 px.

**Tests obligatoires.** Droits et module ; points copiés, annulation, totaux ; période d'après la date ; seuils ; liste proposée ; isolation entre écoles ; journal d'audit.

**Documents à mettre à jour.** `04`, `05`, `06`, `03` (journal), `reference.md`, `A-FAIRE.md` § 11, `07` § 1 et § 4, `maquettes/README.md`.

**Regard senior.** Peu d'incidents par élève et par an : aucune charge serveur. Pas de modèle de période par incident à choisir à l'écran : la date suffit (erreur claire sinon). Le parent prévenu reste en 8.5.1b (moteur de notifications existant). Droits dans le module `academics` (pas de nouveau module à activer dans chaque école).

**Risques.** Rôles des écoles existantes : le directeur de discipline n'a pas de droit voisin sûr, l'école le règle dans « Rôles » (dit dans « À valider »).
