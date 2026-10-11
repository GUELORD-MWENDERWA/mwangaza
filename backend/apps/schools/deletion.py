"""Suppression d'un espace d'essai ou de démonstration (4.16, `03` § 4 bis « Effacement »).

Seule exception à la règle « paiements immuables » : un espace réel ne passe jamais ici
(`services.delete_space` le refuse, `run` aussi). Aucune liste de modèles à tenir : `plan()`
trouve tout ce qui appartient à une école et l'ordonne. Un modèle qu'il ne sait pas classer le
fait échouer, donc les tests avec lui, au lieu d'être oublié ou vidé par erreur.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from graphlib import CycleError, TopologicalSorter

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connection, models
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import Membership, User
from apps.core.models import TenantModel
from apps.notifications.models import PushSubscription
from apps.schools.models import School
from apps.students.models import Family

logger = logging.getLogger(__name__)

# Lignes effacées par requête : des transactions courtes, la base reste disponible pour les écoles.
BATCH = 2000
# Modèles globaux [G] dont chaque ligne appartient pourtant à une seule école.
GLOBAL_MODELS_OF_A_SCHOOL = (Membership, PushSubscription)
# Verrou PostgreSQL (clé arbitraire) : un seul passage à la fois sur le serveur.
_LOCK = 4_160_001

Plan = list[tuple[type[models.Model], tuple[str, ...]]]


def _foreign_keys(model: type[models.Model]) -> list[models.ForeignKey]:
    return [
        field
        for field in model._meta.get_fields()
        if field.concrete and (field.many_to_one or field.one_to_one)
    ]


def _unknown(model: type[models.Model]) -> ImproperlyConfigured:
    return ImproperlyConfigured(
        f"{model._meta.label} pointe vers une école ou vers une de ses données sans être un "
        "`TenantModel` : dire dans `apps/schools/deletion.py` ce que la suppression d'un espace "
        "en fait (`GLOBAL_MODELS_OF_A_SCHOOL` : ses lignes partent avec l'école)."
    )


def plan() -> Plan:
    """Modèles à vider pour supprimer une école, dans l'ordre (qui pointe vers un autre passe
    avant lui), chacun avec ses chemins vers `School`."""
    every = [
        model
        for model in apps.get_models(include_auto_created=True)
        if model is not School and not model._meta.proxy
    ]
    lookups: dict[type[models.Model], tuple[str, ...]] = {}
    for model in every:
        direct = tuple(f.name for f in _foreign_keys(model) if f.related_model is School)
        if issubclass(model, TenantModel):
            lookups[model] = ("school",)
        elif direct and (model in GLOBAL_MODELS_OF_A_SCHOOL or model._meta.auto_created):
            lookups[model] = direct
        elif direct:
            raise _unknown(model)
    # Sans lien direct : tables de liaison entre deux données d'école (`Membership.roles`).
    owned = set(lookups)
    for model in every:
        if model in owned:
            continue
        through = tuple(
            f"{field.name}__{lookups[field.related_model][0]}"
            for field in _foreign_keys(model)
            if field.related_model in owned
        )
        if through and not model._meta.auto_created:
            raise _unknown(model)
        if through:
            lookups[model] = through

    sorter: TopologicalSorter = TopologicalSorter()
    for model in lookups:
        sorter.add(model)
        for field in _foreign_keys(model):
            if field.related_model in lookups and field.related_model is not model:
                sorter.add(field.related_model, model)
    try:
        return [(model, lookups[model]) for model in sorter.static_order()]
    except CycleError as exc:
        raise ImproperlyConfigured(
            f"Modèles d'école qui pointent l'un vers l'autre en boucle : {exc.args[1]}. "
            "La suppression d'un espace ne sait pas les ordonner."
        ) from exc


def _rows(model: type[models.Model], lookups: tuple[str, ...], school: School) -> QuerySet:
    """Lignes de `school`, sans passer par les managers des modèles (école courante, lignes
    immuables) : c'est ici, et seulement ici, qu'on a le droit de tout effacer."""
    condition = Q()
    for lookup in lookups:
        condition |= Q(**{lookup: school})
    return model._base_manager.filter(condition)


def _delete_files(model: type[models.Model], rows: QuerySet) -> None:
    for field in model._meta.get_fields():
        if isinstance(field, models.FileField):
            names = rows.exclude(**{field.name: ""}).values_list(field.name, flat=True)
            for name in names:
                field.storage.delete(name)


def _empty(model: type[models.Model], rows: QuerySet) -> int:
    """Efface `rows` par paquets, sans les contrôles ni les signaux de Django (l'ordre de `plan()`
    les remplace). Renvoie le nombre de lignes effacées."""
    if any(field.related_model is model for field in _foreign_keys(model)):
        # Lignes liées entre elles (`Term.parent`) : en une fois, un paquet laisserait des
        # orphelins.
        return rows._raw_delete(rows.db)
    total, manager = 0, model._base_manager
    while deleted := manager.filter(pk__in=rows.values("pk")[:BATCH])._raw_delete(rows.db):
        total += deleted
    return total


@contextmanager
def _only_one() -> Iterator[bool]:
    """`True` si aucun autre passage ne tourne (verrou de session PostgreSQL, rendu à la fin ou
    quand la connexion tombe)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [_LOCK])
        free = cursor.fetchone()[0]
    try:
        yield free
    finally:
        if free:
            # Connexion perdue : PostgreSQL a déjà rendu le verrou.
            with suppress(DatabaseError), connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [_LOCK])


def deactivate_accounts_left_without_school(school: School) -> int:
    """Personnel et parents qui n'avaient que cet espace : comptes désactivés, jamais supprimés
    (ils restent les auteurs du journal de la plateforme). Un super-admin garde le sien. Avant
    d'effacer quoi que ce soit : rien à rejouer après une panne."""
    staff = Membership.objects.filter(school=school).values("user")
    parents = Family.all_schools.filter(school=school, primary_user__isnull=False)
    staff_elsewhere = Membership.objects.exclude(school=school).values("user")
    parents_elsewhere = Family.all_schools.exclude(school=school).filter(primary_user__isnull=False)
    return (
        User.objects.filter(
            Q(pk__in=staff) | Q(pk__in=parents.values("primary_user")),
            is_active=True,
            is_platform_admin=False,
        )
        .exclude(pk__in=staff_elsewhere)
        .exclude(pk__in=parents_elsewhere.values("primary_user"))
        .update(is_active=False, updated_at=timezone.now())
    )


def run(school_id: str) -> None:
    """Vide puis supprime l'espace `school_id`, déjà marqué « suppression en cours ». Rejouable :
    un nouveau passage efface ce qu'une panne a laissé."""
    with _only_one() as free:
        if not free:
            logger.warning("Suppression de l'espace %s : un autre passage tourne déjà", school_id)
            return
        school = (
            School.objects.filter(pk=school_id, status=School.Status.DELETING)
            .exclude(environment=School.Environment.LIVE)
            .first()
        )
        if school is None:
            return
        total = 0
        for model, lookups in plan():
            rows = _rows(model, lookups, school)
            _delete_files(model, rows)
            total += _empty(model, rows)
        mine = School.objects.filter(pk=school.pk)
        _delete_files(School, mine)
        # Par Django cette fois : `PROTECT` refuse si une ligne de l'école avait échappé au plan.
        mine.delete()
        logger.info("Espace %s supprimé : %d lignes", school.code, total)
