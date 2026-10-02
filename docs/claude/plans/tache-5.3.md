# Tâche 5.3 — Console : écoles

**Serveur** (`apps/schools`) : `ConsoleSchoolViewSet` sous `/api/console/schools/` (`IsPlatformAdmin`) — liste paginée (recherche, statut ; élèves de l'année en cours, dernière activité hors support : requête annotée déplacée de l'admin vers `console.py`), fiche, création avec le directeur (mot de passe provisoire renvoyé une seule fois), `PATCH` (nom, nom officiel, code, abonnement : statut essai / active, offre, fin d'essai, payé jusqu'au), `suspend/`, `reactivate/`. Pas de `DELETE`.
**Journal** : nouvelles actions de la plateforme `school.created` / `updated` / `suspended` / `reactivated` (identité + abonnement) ; le journal de l'école garde ce qu'il a (l'abonnement n'y va pas).
**Administration Django** : écoles en lecture seule (liste, fiche, lien « Ouvrir en tant qu'école ») comme l'identité en 5.2.2 ; formulaire de création et actions retirés.
**Console** : menu « Écoles » ; `/schools` (cartes du tableau de bord, recherche, filtre, tableau, « Ouvrir en tant qu'école » → `<adresse de l'école>/app/support`), `/schools/new` (école + directeur, puis mot de passe provisoire affiché une fois), `/schools/:id` (identité, abonnement, suspendre / réactiver avec confirmation). Couleur, fuseau, logo : réglés par l'école (M5).
**Maquette** : `maquettes/console/ecoles.html` redessinée dans le design de la console (07 : « à redessiner »).

**Tests** : serveur — accès (autre compte 403, autre adresse 404), création (nouveau / compte connu / refus sans rien créer), journaux école + plateforme, liste (élèves, activité, pas de N+1), PATCH (abonnement hors journal de l'école, statut « suspendue » refusé), suspendre / réactiver, admin en lecture seule ; `test_admin.py` des écoles porté sur l'API. Front — un test : création → mot de passe affiché ; suspension confirmée.

**Risques** : changer le code = l'ancienne adresse cesse de marcher (avertissement dans l'écran).
