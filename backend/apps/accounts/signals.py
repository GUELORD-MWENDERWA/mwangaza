"""Rôles système copiés à la création de chaque école ; rôles d'une autre école refusés."""

from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from apps.accounts.models import Membership, Role
from apps.accounts.services import create_system_roles
from apps.core.tenancy import CrossSchoolError
from apps.schools.models import School


@receiver(post_save, sender=School, dispatch_uid="accounts_create_system_roles")
def _copy_system_roles(sender, instance: School, created: bool, raw: bool = False, **kwargs):
    # Quelle que soit la façon de créer l'école : administration, super-admin (1.5), `make demo`.
    if created and not raw:
        create_system_roles(instance)


@receiver(m2m_changed, sender=Membership.roles.through, dispatch_uid="accounts_same_school_roles")
def _refuse_roles_of_another_school(sender, instance, action, reverse, pk_set, **kwargs):
    """Une appartenance ne reçoit que des rôles de son école, par quelque chemin que ce soit
    (`membership.roles.add/set`, `role.memberships.add`). Défense en profondeur : l'API ne
    propose déjà que les rôles de l'école de l'adresse."""
    if action != "pre_add" or not pk_set:
        return
    if reverse:
        other_school = Membership.objects.filter(pk__in=pk_set).exclude(
            school_id=instance.school_id
        )
    else:
        other_school = Role.all_schools.filter(pk__in=pk_set).exclude(school_id=instance.school_id)
    if other_school.exists():
        raise CrossSchoolError("Un rôle ne peut être donné que dans son école.")
