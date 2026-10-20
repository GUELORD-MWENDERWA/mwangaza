"""Modules que la plateforme donne à une école (tâche M.1) : chaque fonction est un module, et un
module porte des permissions. Le socle (connexion, paramètres, rôles et comptes, journal, années
et classes) est toujours actif. Les permissions d'un module que l'école n'a pas sont retirées des
droits de chacun (`accounts/services.py:get_school_access`) : le serveur répond 403 partout, sans
supprimer aucune donnée."""

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from apps.accounts.roles import PERMISSIONS

# Jamais désactivables.
CORE_PERMISSIONS = frozenset({"school.configure", "classes.manage", "roles.manage", "audit.view"})

MODULES: dict[str, tuple[Promise, tuple[str, ...]]] = {
    "students": (
        _("Students, families and enrolments"),
        ("students.view", "students.edit", "students.import"),
    ),
    "finance": (
        _("Fees, cash desk and payments"),
        tuple(code for code in PERMISSIONS if code.startswith("finance.")),
    ),
    "communication": (_("Announcements"), ("announcements.publish",)),
    # Cours (8.1), puis notes, bulletins et délibération (8.2 à 8.4).
    "academics": (
        _("Courses, grades and report cards"),
        (
            "courses.configure",
            "grades.enter",
            "grades.enter_any",
            "grades.validate",
            "discipline.configure",
            "discipline.record",
            "discipline.override",
        ),
    ),
    # Sans permission : ils ouvrent des fonctions (portail des parents, notifications à l'écran,
    # travail hors-ligne), pas des droits du personnel.
    # Emploi du temps (bloc EDT) : grilles, salles, puis règles, calcul et publication.
    "timetable": (_("Timetable"), ("timetable.manage",)),
    "portal": (_("Parent portal"), ()),
    "notifications": (_("Notifications and reminders"), ()),
    "offline": (_("Offline work and synchronisation"), ()),
}
# Un module a besoin de ceux-ci : les activer ensemble, ne pas retirer le second tant que le
# premier est actif. Rien n'est supprimé en désactivant (les données reviennent à la réactivation).
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "finance": ("students",),
    # Les notes sont celles des élèves inscrits.
    "academics": ("students",),
    # L'horaire place les cours des classes.
    "timetable": ("academics",),
    "portal": ("students",),
}
MODULE_CHOICES = [(code, label) for code, (label, _permissions) in MODULES.items()]
ALL_MODULES = list(MODULES)


def permissions_of(modules) -> frozenset[str]:
    """Permissions que donnent ces modules, socle compris."""
    return CORE_PERMISSIONS.union(*(MODULES[code][1] for code in modules if code in MODULES))


def resolve(wanted, current=()) -> list[str]:
    """Liste des modules après un changement de `current` vers `wanted` : ajoute ce dont dépend
    un module activé ; refuse (`ValueError`, texte pour l'utilisateur) de retirer un module dont
    un module actif dépend. Résultat dans l'ordre du catalogue."""
    chosen = set(wanted)
    # Dépendances en chaîne (emploi du temps → cours → élèves).
    todo = list(wanted)
    while todo:
        code = todo.pop()
        for needed in DEPENDENCIES.get(code, ()):
            if needed in current and needed not in chosen:
                message = _("%(module)s is still needed by %(by)s.") % {
                    "module": MODULES[needed][0],
                    "by": MODULES[code][0],
                }
                raise ValueError(str(message))
            if needed not in chosen:
                chosen.add(needed)
                todo.append(needed)
    return [code for code in ALL_MODULES if code in chosen]
