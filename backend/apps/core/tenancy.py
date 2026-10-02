"""École courante (d'une requête, d'une tâche, d'un test) et manager limité à cette école.

Règle 1 de `CLAUDE.md` : une école ne peut ni lire ni modifier les données d'une autre.
Voir `docs/03-architecture-technique.md` § 4.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from apps.schools.models import School

# Sous-domaines qui ne sont pas des écoles : portail des familles, super-admin, services.
RESERVED_SUBDOMAINS = frozenset(
    {"www", "parents", "admin", "api", "app", "static", "media", "mail", "status", "docs"}
)
# Console de la plateforme (super-admin, 5.2) : admin.mwangaza.school.
CONSOLE_SUBDOMAIN = "admin"

_current_school: ContextVar["School | None"] = ContextVar("current_school", default=None)


class TenancyError(Exception):
    """Erreur de programmation : accès aux données d'une école hors de son cadre."""


class SchoolNotSetError(TenancyError):
    """Requête ou écriture sur une donnée d'école alors qu'aucune école n'est définie."""


class CrossSchoolError(TenancyError):
    """Écriture qui toucherait les données d'une autre école."""


NO_SCHOOL_MESSAGE = (
    "Aucune école courante. Passer par une requête sur le sous-domaine de l'école "
    "(TenantMiddleware), par `use_school(school)` (tâches Celery, commandes, tests) ou, "
    "pour le super-admin et le portail des familles seulement, par `Model.all_schools` "
    "toujours filtré. Jamais `Model.objects.all()` au niveau d'une classe : il s'exécute au "
    "chargement du module, sans école."
)


def get_current_school() -> "School | None":
    return _current_school.get()


def require_current_school() -> "School":
    school = _current_school.get()
    if school is None:
        raise SchoolNotSetError(NO_SCHOOL_MESSAGE)
    return school


@contextmanager
def use_school(school: "School | None") -> Iterator["School | None"]:
    """Définit l'école courante le temps d'un bloc `with`, puis rétablit la précédente."""
    token = _current_school.set(school)
    try:
        yield school
    finally:
        _current_school.reset(token)


class TenantQuerySet(models.QuerySet):
    def bulk_create(self, objs, *args, **kwargs):
        # `bulk_create` ne passe pas par `save()` : mêmes contrôles ici.
        objs = list(objs)
        for obj in objs:
            obj.check_school()
        created = super().bulk_create(objs, *args, **kwargs)
        for obj in created:
            obj._school_id_in_db = obj.school_id
        return created


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """Manager par défaut des modèles d'école : seulement l'école courante, erreur sans école."""

    def get_queryset(self) -> TenantQuerySet:
        return super().get_queryset().filter(school=require_current_school())


# Toutes les écoles : super-admin et portail des familles seulement, toujours filtré explicitement.
AllSchoolsManager = models.Manager.from_queryset(TenantQuerySet)
