# Tâche NB.4 — Règles de délibération du règlement de l'école (#345)

**But** : la décision proposée suit le règlement des études de l'école (sources : `recherches/2026-10-18-notes-deliberation-rdc.md`, critères de Mwapusukeni relus le 2026-10-19) et cite la règle appliquée ; remplace la fenêtre 45–50 % de 8.4.1.

**Choix (regard senior)** : rien de stocké de plus que les réglages (`School.settings["pass_rules"]`, `Level.pass_rules`) et une **catégorie par cours** (`Course.category` : générale, principale, option, pratique), qui remplace `resit_allowed` (migration : sans repêchage → pratique). Une seule colonne, pas deux : un cours principal compte à part des options. Proposition toujours recalculée (une requête de plus par classe : l'historique des inscriptions de l'élève). Préréglages définis une fois côté serveur, renvoyés par l'API, appliqués dans le formulaire. Par défaut « courant » (Q15 en attente).

**Hors périmètre** : conseil et PV (NB.5), seconde session (NB.6), diplôme jésuite de fin de 6e.

**Critères d'acceptation**
- Passe : total ≥ seuil, chaque cours ≥ seuil (conduite : renvoi d'abord). Entrée en dernière classe (niveau suivant avec Examen d'État) : seuil propre et aucun échec.
- Repêchage : total ≥ seuil de repêchage, N cours au plus, N cours principaux au plus, N options au plus, pratique au choix ; sinon double.
- Sous le seuil d'orientation : orienté ; exception d'âge (âge limite du niveau à la rentrée suivante, au-dessus d'un plancher) : double.
- Exclusion : a déjà fait ce niveau, redoublements au maximum, MA / ME N périodes **de suite**, en conduite et (au choix) en application.
- Délibération et repêchage affichent la règle citée ; carte « Règles de délibération » avec les deux préréglages ; colonne « Catégorie » des cours.

**Tests obligatoires** : chaque règle ; préréglage par l'API ; isolation (historique d'un élève d'une autre école ignoré) ; droits inchangés.

**Documents** : `04`, `03`, `05`, `06`, `07`, `reference.md`, `maquettes/README.md` + maquettes (paramètres, cours, délibération, repêchage), `A-FAIRE.md` 7 ter.

**Risques** : `make demo` (cours sans catégorie) ; application ME de 50 à 59 % (préréglage catholique : renvoi après 3 périodes de suite) ; anciens réglages `resit_mode` ignorés.
