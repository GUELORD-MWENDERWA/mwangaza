"""Espaces de démonstration créés depuis la console (4.17.2, A6, `03` § 4 bis).

Créer : l'espace et sa ligne `Demonstration` (profil, bloc de numéros, mot de passe) dans la
requête, les données fictives en tâche de fond (`core.demo.fill`, le code de `make demo`), avec
l'avancement. Un seul travail lourd à la fois sur le serveur, par un refus ; nombre d'espaces de
démonstration limité (`DEMO_SPACES_MAX`).

Remettre à zéro = supprimer (4.16) puis recréer : même adresse, même identifiant, mêmes numéros,
nouveau mot de passe (les visiteurs d'avant n'entrent plus).

Fiche d'accès : adresses, mot de passe, un compte par rôle, parents du portail.
"""

import logging
from collections.abc import Callable
from functools import partial

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.demo import demo_accounts
from apps.accounts.models import Membership, User
from apps.accounts.phone import InvalidPhoneError, normalize_phone
from apps.accounts.services import make_temporary_password
from apps.core.crypto import decrypt, encrypt
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import use_school
from apps.schools import deletion, services, tasks
from apps.schools.demo import BLOCKS, DemoNumbers, DemoSpace
from apps.schools.models import Demonstration, School
from apps.students.models import Family

logger = logging.getLogger(__name__)

# Profil choisi dans la console → données d'exemple (`schools/demo.py`).
DATA = {Demonstration.Profile.SMALL: "volcans", Demonstration.Profile.LARGE: "itig"}
# Familles proposées sur la fiche pour essayer « Activer mon compte ».
FAMILIES_TO_ACTIVATE = 3

LIMIT_REACHED = ApiError(
    "demo_limit",
    _("The platform has its maximum number of demonstration spaces: delete one first."),
    409,
)
NOT_FROM_CONSOLE = ApiError(
    "not_a_console_demo",
    _("Only a demonstration space created from the console has an access sheet and a reset."),
    409,
)
NOT_READY = ApiError("demo_not_ready", _("This demonstration space is not ready yet."), 409)

State = Demonstration.State


class _Leaving(Exception):
    """L'espace est supprimé ou remis à zéro pendant qu'il se remplit."""


def _start(school: School, *, profile: str, block: int, actor) -> None:
    from apps.core import demo  # les données fictives de toutes les apps

    Demonstration.objects.create(
        school=school,
        profile=profile,
        block=block,
        password=encrypt(make_temporary_password()),
        steps_total=len(demo.STEPS),
        created_by=actor,
    )
    transaction.on_commit(partial(tasks.fill_demonstration.delay, str(school.pk)))


def create(*, code: str, name: str, profile: str, actor) -> School:
    """Nouvel espace de démonstration, ouvert tout de suite ; ses données arrivent en tâche de
    fond (`fill`). Bloc de numéros : le plus petit de libre."""
    with transaction.atomic():
        demos = School.objects.filter(environment=School.Environment.DEMO)
        taken = set(Demonstration.objects.values_list("block", flat=True))
        block = next((number for number in BLOCKS if number not in taken), None)
        if block is None or demos.count() >= settings.DEMO_SPACES_MAX:
            raise BusinessError(LIMIT_REACHED)
        if services.space_busy():
            raise BusinessError(services.SPACE_BUSY)
        school = School(
            code=code,
            name=name,
            environment=School.Environment.DEMO,
            status=School.Status.ACTIVE,
        )
        services.open_space(school, actor=actor)
        _start(school, profile=profile, block=block, actor=actor)
    return school


def _space(record: Demonstration) -> DemoSpace:
    return DemoSpace(
        record.school,
        DATA[record.profile],
        DemoNumbers.block(record.block),
        decrypt(record.password),
    )


def fill(school_id: str) -> None:
    """Tâche de fond : écrit **une** étape des données fictives de l'espace (une transaction),
    note l'avancement, puis demande la suivante. Une tâche par étape (2026-10-27) : chacune a son
    temps, et le travailleur des tâches lourdes rend sa mémoire entre deux (calcul de l'horaire,
    ~800 élèves et leurs notes ne tenaient pas en 10 minutes ni en 384 Mo d'un seul tenant) ;
    une étape interrompue se reprend là où on en était. Attend son tour si un espace s'efface
    encore (remise à zéro). Une erreur laisse l'espace « en échec » : on le remet à zéro ou on le
    supprime."""
    from apps.core import demo  # les données fictives de toutes les apps

    leaving = more = False
    with deletion.only_one(wait=True):
        mine = Demonstration.objects.filter(school_id=school_id, state=State.FILLING)
        record = mine.select_related("school").first()
        if record is None:
            return

        def on_step(done: int, total: int) -> None:
            staying = mine.exclude(school__status=School.Status.DELETING)
            if not staying.update(steps_done=done, steps_total=total, updated_at=timezone.now()):
                raise _Leaving

        try:
            on_step(record.steps_done, len(demo.STEPS))  # déjà parti ? on ne remplit rien
            done = demo.fill([_space(record)], on_step, start=record.steps_done, count=1)
        except _Leaving:
            leaving = True
        except Exception:
            mine.update(state=State.FAILED, updated_at=timezone.now())
            logger.exception("Espace de démonstration %s : remplissage en échec", school_id)
            raise
        else:
            more = done < len(demo.STEPS)
            if not more:
                mine.update(state=State.READY, updated_at=timezone.now())
    if leaving:
        # Sa suppression n'a pas pu commencer pendant le remplissage : c'est son tour.
        tasks.delete_space.delay(school_id)
    elif more:
        tasks.fill_demonstration.delay(school_id)


def _record(school: School) -> Demonstration:
    record = Demonstration.objects.filter(school=school).first()
    if record is None:
        raise BusinessError(NOT_FROM_CONSOLE)
    record.school = school
    return record


def reset(school: School, *, actor, confirm: str) -> None:
    """« Remettre à zéro » : l'espace est supprimé (`services.delete_space` : fermé, comptes
    désactivés, journal), puis recréé et rempli par la même tâche de fond."""
    record = _record(school)
    with transaction.atomic():
        services.delete_space(school, actor=actor, confirm=confirm)
        Demonstration.objects.filter(pk=record.pk).update(
            reset_requested=True, created_by=actor, updated_at=timezone.now()
        )


def recreation(school_id: str) -> Callable[[School], None] | None:
    """Pour `deletion.run` : de quoi recréer l'espace à l'instant où sa ligne part, si une remise
    à zéro est demandée ; lu avant, la ligne `Demonstration` part avec l'école. Même identifiant
    (la fiche ouverte dans la console le suit), même adresse, même bloc de numéros."""
    record = (
        Demonstration.objects.filter(school_id=school_id, reset_requested=True)
        .select_related("created_by")
        .first()
    )
    if record is None:
        return None

    def recreate(old: School) -> None:
        school = School(
            pk=old.pk,
            code=old.code,
            name=old.name,
            official_name=old.official_name,
            environment=School.Environment.DEMO,
            status=School.Status.ACTIVE,
        )
        services.open_space(school, actor=record.created_by)
        _start(school, profile=record.profile, block=record.block, actor=record.created_by)

    return recreate


def typed(phone: str) -> str:
    """Le numéro comme on le tape à la connexion : sans indicatif (0004001001)."""
    prefix = f"+{settings.PHONE_DEFAULT_COUNTRY_CODE}"
    return f"0{phone.removeprefix(prefix)}" if phone.startswith(prefix) else phone


def _guardian_phone(family: Family) -> str | None:
    primary = next((g for g in family.guardians.all() if g.is_primary), None)
    try:
        return normalize_phone(primary.phone) if primary and primary.phone else None
    except InvalidPhoneError:
        return None


def _parents(school: School) -> list[dict]:
    """Le parent qui a déjà son compte (première famille, `portal/demo.py`), puis des familles
    qui n'ont pas encore activé le leur : numéro et code famille. Un numéro qui a déjà un compte
    (activé à la main avant une remise à zéro) n'est pas proposé."""
    rows, waiting = [], {}
    with use_school(school):
        families = Family.objects.prefetch_related("guardians").order_by("created_at", "id")
        first = families.select_related("primary_user").first()
        if first is not None and first.primary_user is not None:
            name = next((g.full_name for g in first.guardians.all() if g.is_primary), "")
            rows.append({"name": name, "phone": typed(first.primary_user.phone), "code": ""})
        candidates = families.filter(
            primary_user=None, portal_suspended_at=None, code_expires_at=None
        )
        for family in candidates[: FAMILIES_TO_ACTIVATE * 5]:
            if phone := _guardian_phone(family):
                waiting.setdefault(phone, family)
    known = set(User.objects.filter(phone__in=waiting).values_list("phone", flat=True))
    free = [(phone, family) for phone, family in waiting.items() if phone not in known]
    for phone, family in free[:FAMILIES_TO_ACTIVATE]:
        name = next(g.full_name for g in family.guardians.all() if g.is_primary)
        rows.append(
            {"name": name, "phone": typed(phone), "code": f"{family.code[:4]}-{family.code[4:]}"}
        )
    return rows


def access_sheet(school: School) -> dict:
    """Ce que la fiche d'accès montre (gabarit `schools/access_sheet.html`) : lu dans l'espace
    lui-même, jamais ailleurs."""
    record = _record(school)
    if record.state != State.READY or school.status == School.Status.DELETING:
        raise BusinessError(NOT_READY)
    space = _space(record)
    phones = {space.numbers.of(account.phone): account for account in demo_accounts(space)}
    with use_school(school):
        members = (
            Membership.objects.filter(school=school, user__phone__in=phones)
            .select_related("user")
            .prefetch_related("roles")
            .order_by("user__phone")
        )
        accounts = [
            {
                "role": ", ".join(role.name for role in member.roles.all()),
                "name": member.user.get_full_name(),
                "phone": typed(member.user.phone),
            }
            for member in members
        ]
    return {
        "school": school,
        "gestion_url": f"{school.url}/app/",
        "portal_url": settings.PORTAL_URL,
        "password": space.password,
        "accounts": accounts,
        "parents": _parents(school),
        "printed_at": timezone.localtime(),
    }
