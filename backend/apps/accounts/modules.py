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
}
MODULE_CHOICES = [(code, label) for code, (label, _permissions) in MODULES.items()]
ALL_MODULES = list(MODULES)


def permissions_of(modules) -> frozenset[str]:
    """Permissions que donnent ces modules, socle compris."""
    return CORE_PERMISSIONS.union(*(MODULES[code][1] for code in modules if code in MODULES))
