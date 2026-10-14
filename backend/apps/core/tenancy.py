"""École courante (d'une requête, d'une tâche, d'un test) et manager limité à cette école.

Règle 1 de `CLAUDE.md` : une école ne peut ni lire ni modifier les données d'une autre.
Voir `docs/03-architecture-technique.md` § 4.

Deuxième barrière (S.6, Row Level Security) : chaque contexte ci-dessous pose aussi la portée de
la connexion PostgreSQL, les écoles dont la base laisse voir et écrire les lignes
(`apps/core/row_security.py`). Sans contexte, la base ne montre rien.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from django.db import DEFAULT_DB_ALIAS, connections, models
from psycopg import pq

if TYPE_CHECKING:
    from apps.schools.models import School

# Sous-domaines qui ne sont pas des écoles : portail des familles, super-admin, services.
RESERVED_SUBDOMAINS = frozenset(
    {"www", "parents", "admin", "api", "app", "static", "media", "mail", "status", "docs"}
)
# Console de la plateforme (super-admin, 5.2) : admin.mwangaza.school.
CONSOLE_SUBDOMAIN = "admin"

_current_school: ContextVar["School | None"] = ContextVar("current_school", default=None)

# Portée de la base : identifiants des écoles visibles, ou `ALL_SCHOOLS` (plateforme).
ALL_SCHOOLS = "all"
_db_scope: ContextVar[tuple[str, ...] | str] = ContextVar("db_scope", default=())


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
    """Définit l'école courante le temps d'un bloc `with`, puis rétablit la précédente. La base
    ne laisse voir que ses lignes."""
    token = _current_school.set(school)
    try:
        with _db_scoped((str(school.pk),) if school else ()):
            yield school
    finally:
        _current_school.reset(token)


@contextmanager
def use_schools(school_ids: Iterable) -> Iterator[None]:
    """Portail des familles : la base ne laisse voir que les lignes de ces écoles (celles des
    familles du parent), sans école courante ; chaque lecture reste filtrée sur ses familles."""
    with _db_scoped(tuple(sorted({str(pk) for pk in school_ids}))):
        yield


@contextmanager
def use_all_schools() -> Iterator[None]:
    """Toutes les écoles pour la base : console et administration du super-admin, tâches de la
    plateforme (relances de toutes les écoles, suppression d'un espace). Ne change pas l'école
    courante ; `Model.all_schools`, toujours filtré, reste le seul accès aux autres écoles."""
    with _db_scoped(ALL_SCHOOLS):
        yield


@contextmanager
def _db_scoped(scope: tuple[str, ...] | str) -> Iterator[None]:
    token = _db_scope.set(scope)
    _apply_db_scope(connections[DEFAULT_DB_ALIAS])
    try:
        yield
    finally:
        _db_scope.reset(token)
        _apply_db_scope(connections[DEFAULT_DB_ALIAS])


# Une seule requête, hors du journal de Django (comptages des tests, barre de débogage).
_SET_SCOPE = (
    "SELECT set_config('mwangaza.school_ids', %s, false),"
    " set_config('mwangaza.all_schools', %s, false)"
)


def _apply_db_scope(connection) -> None:
    """Pose la portée courante sur la connexion. Connexion pas encore ouverte : `connect()` la
    posera (`apply_scope_on_connect`). Transaction en échec : rien, son annulation rétablit la
    valeur du début du bloc, celle du contexte englobant."""
    raw = connection.connection
    if raw is None or raw.closed or raw.info.transaction_status == pq.TransactionStatus.INERROR:
        return
    scope = _db_scope.get()
    params = ["{}", "on"] if scope == ALL_SCHOOLS else ["{" + ",".join(scope) + "}", "off"]
    with raw.cursor() as cursor:
        cursor.execute(_SET_SCOPE, params)


def apply_scope_on_connect(sender, connection, **kwargs) -> None:
    """Signal `connection_created` : nouvelle connexion (ou reprise après une coupure) au milieu
    d'un contexte."""
    if connection.alias == DEFAULT_DB_ALIAS:
        _apply_db_scope(connection)


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
