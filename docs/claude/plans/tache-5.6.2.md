# Tâche 5.6.2 — Notifications : événements à heure fixe

## Fait ici
- **Planificateur** : Celery beat **dans le worker existant** (`celery worker -B`, aucun conteneur en plus) ; un passage toutes les 15 minutes (`notifications.tasks.tick`), une purge chaque nuit (`purge`).
- `notifications/scheduled.py` : à chaque passage, 2 requêtes (écoles ouvertes, passages déjà faits) ; le travail d'une école ne se fait qu'**une fois par jour et par sorte**, à son heure et dans son fuseau, marqué par `ScheduledRun` [T] (école, sorte, jour, unique) dans la même transaction que ses notifications.
- **Parent** (08:00, si l'école a activé les relances) : « Échéance proche » (J − `days_before`, reste > 0) et « Retard de paiement » (reste échu > 0, au plus une fois tous les `overdue_every_days` jours par parent, d'après sa dernière notification). Une notification par parent, tous ses enfants de l'école réunis, montants par devise, dans sa langue.
- **Directeur** (heure de clôture de l'école) : « Caisse encore ouverte » → comptes qui lisent les rapports.
- **Réglages** : `School.settings["reminders"]` (`schools/reminders.py`, comme `alerts.py`) ; carte « Relances aux parents » sur l'écran Paramètres de l'école ; journal de l'école.
- 3 sortes nouvelles + préférences (Portail : échéance, retard ; Gestion : caisse ouverte, selon le droit).
- Purge : notifications et marques de plus de 90 jours.
- `make relances` : lancer le passage à la main (essais, `make dev-local` sans worker). `make demo` : relances activées, exemples chez le parent fictif.

## Retiré ou simplifié (regard senior)
- Relances **désactivées par défaut** : une école qui n'a pas fini de saisir ses paiements d'avant enverrait de faux retards aux parents.
- Pas de notification « retard » par échéance en plus des relances : un parent de 3 enfants en recevrait une dizaine ; une seule, résumée.
- Pas d'heure d'envoi réglable ni de conteneur beat séparé ; pas d'alerte au caissier lui-même (hors tâche).

## Tests
`notifications/tests/test_scheduled.py` : isolation (l'autre école ne reçoit ni ne déclenche rien), montants (payé, partiel, deux devises), un seul envoi par jour et par intervalle, caisse ouverte selon le droit et l'heure, purge ; `schools` : réglages (droit, journal). Front : carte des relances dans le formulaire.

## Coût serveur
Passage : 2 requêtes. Par école et par jour : 5 requêtes limitées aux familles qui ont un compte, 2 lignes `ScheduledRun` (purgées à 90 jours).
