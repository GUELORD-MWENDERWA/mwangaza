"""Modules que la plateforme donne à une école (tâche M.1) : chaque fonction est un module, et un
module porte des permissions. Le socle (connexion, paramètres, rôles et comptes, journal, années
et classes) est toujours actif. Les permissions d'un module que l'école n'a pas sont retirées des
droits de chacun (`accounts/services.py:get_school_access`) : le serveur répond 403 partout, sans
supprimer aucune donnée."""

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from apps.accounts.roles import PERMISSIONS

# Jamais désactivables.
CORE_PERMISSIONS = frozenset(
    {"school.configure", "classes.manage", "roles.manage", "audit.view", "billing.view"}
)

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
            "grades.waive_fees",
            "discipline.configure",
            "discipline.record",
            "discipline.override",
        ),
    ),
    # Sans permission : ils ouvrent des fonctions (portail des parents, notifications à l'écran,
    # travail hors-ligne), pas des droits du personnel.
    # Emploi du temps (bloc EDT) : grilles, salles, puis règles, calcul et publication.
    "timetable": (
        _("Timetable"),
        ("timetable.manage", "timetable.publish", "timetable.record_exceptions"),
    ),
    # Assistance par l'IA (bloc IA) : le droit `ai.use` ; l'école ne règle que ce droit, la
    # plateforme règle les usages et les crédits (console).
    # Cartes et présences (lot 10) ; les lecteurs et la sonnerie viendront au lot 16.
    "attendance": (
        _("Cards and attendance"),
        ("attendance.cards", "attendance.scan", "attendance.view", "attendance.correct"),
    ),
    "ai": (_("AI assistance"), ("ai.use",)),
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
    # Les cartes et les passages sont ceux des élèves inscrits.
    "attendance": ("students",),
}
MODULE_CHOICES = [(code, label) for code, (label, _permissions) in MODULES.items()]
ALL_MODULES = list(MODULES)

# Tout suit les modules (MOD.1, `docs/specs/equipements.md` § 1 bis) : ce qu'une école ne voit,
# ne remplit et ne règle que si elle a **un** de ces modules. Les permissions suivent déjà les
# modules (`permissions_of`) ; ce registre couvre le reste : champs, sections de paramètres,
# étapes de mise en route, rôles du modèle de départ. Sans entrée : socle, toujours là. Le
# serveur n'exige jamais et n'écrit jamais ce qui ne s'applique pas ; `/me` envoie la liste
# (`features`) pour que l'interface masque la même chose.
FEATURES: dict[str, tuple[str, ...]] = {
    # Fiche de l'élève : en-tête du bulletin (N° ID de l'EPST, N° permanent, naissance, origine).
    "student.national_id": ("academics",),
    "student.permanent_number": ("academics",),
    "student.birth_place": ("academics",),
    "student.nationality": ("academics",),
    "student.origin": ("academics",),
    # Paramètres de l'école.
    "settings.currencies": ("finance",),
    "settings.receipt": ("finance",),
    "settings.alerts": ("finance",),
    "settings.reminders": ("finance",),
    "settings.portal": ("portal",),
    "settings.grading": ("academics",),
    "settings.pass_rules": ("academics",),
    "settings.ai": ("ai",),
    "settings.card": ("attendance",),
    "settings.attendance": ("attendance",),
    # Mise en route (`schools/setup.py`) : années et classes pour tout module qui touche des
    # élèves (plus tard : pas la sonnerie seule).
    "setup.year": ("students",),
    "setup.classes": ("students",),
    "setup.fees": ("finance",),
    "setup.staff": ("finance",),
    "setup.cash": ("finance",),
    "setup.students": ("students",),
    "setup.prior": ("finance",),
    "setup.invitations": ("portal",),
    # Rôles du modèle de départ (`roles.STARTER_ROLES`) donnés à l'école.
    "role.study_director": ("academics",),
    "role.discipline_master": ("academics",),
    "role.accountant": ("finance",),
    "role.cashier": ("finance",),
    "role.teacher": ("academics",),
}
# Champ de l'élève → ce qui le porte (`FEATURES`).
STUDENT_FIELD_FEATURES = {
    "national_id": "student.national_id",
    "permanent_number": "student.permanent_number",
    "birth_place": "student.birth_place",
    "nationality": "student.nationality",
    "origin_province": "student.origin",
    "origin_territory": "student.origin",
}


def applies(feature: str, modules) -> bool:
    """`feature` s'applique à une école qui a ces modules (socle : toujours)."""
    needed = FEATURES.get(feature)
    return needed is None or any(code in modules for code in needed)


def features_of(modules) -> list[str]:
    """Ce qui, dans le registre, s'applique à ces modules (pour `/me`)."""
    return [feature for feature in FEATURES if applies(feature, modules)]


def hidden_student_fields(modules) -> set[str]:
    """Champs de la fiche élève qui ne s'appliquent pas à ces modules."""
    return {
        field for field, feature in STUDENT_FIELD_FEATURES.items() if not applies(feature, modules)
    }


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
