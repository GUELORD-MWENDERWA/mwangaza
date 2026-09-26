"""Écoles : création avec le premier directeur (A1), changements et suspension notés dans le
journal de l'école."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts.models import Membership, Role, User
from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.errors import BusinessError
from apps.core.tenancy import use_school
from apps.schools import services
from apps.schools.models import School
from apps.schools.services import Director
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def journal(school) -> list[AuditLog]:
    with use_school(school):
        return list(AuditLog.objects.order_by("created_at", "id"))


def new_school(**fields) -> School:
    return School(**{"code": "gamma", "name": "Institut Gamma (fictif)", **fields})


# Création (A1)


def test_create_a_school_with_a_new_director(platform_admin, school):
    director = Director(phone="0000003001", last_name="Kasereka", first_name="Dieudonné")

    membership, password = services.create_school(
        new_school(official_name="Institut technique Gamma"),
        actor=platform_admin,
        director=director,
    )

    gamma = School.objects.get(code="gamma")
    assert gamma.created_by == platform_admin
    assert membership.school == gamma
    assert membership.user.last_name == "Kasereka"
    assert membership.user.must_change_password
    assert membership.user.check_password(password)
    with use_school(gamma):
        assert Role.objects.count() == 9
        assert list(membership.roles.values_list("code", flat=True)) == ["head"]
    created, added = journal(gamma)
    assert created.action == Action.SCHOOL_CREATED
    assert created.actor == platform_admin
    assert created.after["code"] == "gamma"
    assert created.after["official_name"] == "Institut technique Gamma"
    assert added.action == Action.STAFF_ADDED
    assert added.actor == platform_admin
    assert added.after["new_account"] is True
    assert journal(school) == []


def test_create_a_school_whose_director_already_has_an_account(platform_admin, school):
    existing = MembershipFactory(school=school, roles=["teacher"]).user

    membership, password = services.create_school(
        new_school(),
        actor=platform_admin,
        director=Director(phone=existing.phone, last_name="Autre nom"),
    )

    assert password is None
    assert membership.user == existing
    existing.refresh_from_db()
    assert existing.last_name != "Autre nom"
    assert journal(membership.school)[-1].after["new_account"] is False
    # Rien dans le journal de l'autre école de cette personne.
    assert journal(school) == []


def test_a_new_director_needs_a_name(platform_admin):
    with pytest.raises(BusinessError) as error:
        services.create_school(new_school(), actor=platform_admin, director=Director("0000003002"))

    assert error.value.error.code == "names_required"
    assert not School.objects.filter(code="gamma").exists()
    assert not User.objects.filter(phone="+243000003002").exists()


# Changements


def test_changes_are_noted_field_by_field(platform_admin, school):
    school.name = "École Alpha"
    school.primary_color = "#003C6C"

    services.save_school(school, actor=platform_admin)

    [entry] = journal(school)
    assert entry.action == Action.SCHOOL_UPDATED
    assert entry.before == {"name": "École Alpha (fictive)", "primary_color": "#0E5C6B"}
    assert entry.after == {"name": "École Alpha", "primary_color": "#003C6C"}
    assert entry.entity_label == "École Alpha"


def test_nothing_changed_nothing_noted(platform_admin, school):
    services.save_school(school, actor=platform_admin)

    assert journal(school) == []


def test_subscription_is_not_in_the_school_journal(platform_admin, school):
    school.plan = "Standard"
    school.paid_until = timezone.localdate() + timedelta(days=90)
    school.status = School.Status.TRIAL

    services.save_school(school, actor=platform_admin)

    assert journal(school) == []
    school.refresh_from_db()
    assert school.plan == "Standard"


def test_update_school_by_the_school_itself(head, school):
    services.update_school(school, actor=head, official_name="Complexe scolaire Alpha")

    school.refresh_from_db()
    assert school.official_name == "Complexe scolaire Alpha"
    [entry] = journal(school)
    assert entry.actor == head
    assert entry.after == {"official_name": "Complexe scolaire Alpha"}


def test_changes_of_one_school_stay_in_its_journal(platform_admin, school, other_school):
    services.update_school(other_school, actor=platform_admin, name="École Beta")

    assert journal(school) == []
    assert len(journal(other_school)) == 1


# Suspension


def test_suspend_and_reactivate(platform_admin, school):
    services.suspend(school, actor=platform_admin)
    school.refresh_from_db()
    assert school.status == School.Status.SUSPENDED

    services.reactivate(school, actor=platform_admin)
    school.refresh_from_db()
    assert school.status == School.Status.ACTIVE

    assert [entry.action for entry in journal(school)] == [
        Action.SCHOOL_SUSPENDED,
        Action.SCHOOL_REACTIVATED,
    ]


def test_suspending_twice_notes_it_once(platform_admin, school):
    services.suspend(school, actor=platform_admin)
    services.suspend(school, actor=platform_admin)

    assert len(journal(school)) == 1


def test_reactivated_during_its_trial_a_school_is_back_in_trial(platform_admin, school):
    school.trial_ends_on = timezone.localdate() + timedelta(days=30)
    services.suspend(school, actor=platform_admin)

    services.reactivate(school, actor=platform_admin)

    school.refresh_from_db()
    assert school.status == School.Status.TRIAL


def test_suspension_keeps_everything(platform_admin, school, head):
    services.suspend(school, actor=platform_admin)

    assert Membership.objects.filter(school=school, user=head, is_active=True).exists()
    with use_school(school):
        assert Role.objects.count() == 9


# Logo


def test_new_logo_noted_and_old_file_removed(
    platform_admin, school, django_capture_on_commit_callbacks
):
    services.update_school(
        school, actor=platform_admin, logo=SimpleUploadedFile("a.png", PNG, "image/png")
    )
    old_name = school.logo.name
    storage = school.logo.storage

    with django_capture_on_commit_callbacks(execute=True):
        services.update_school(
            school, actor=platform_admin, logo=SimpleUploadedFile("b.png", PNG, "image/png")
        )

    assert school.logo.name != old_name
    assert school.logo.name.startswith(f"schools/{school.pk}/logo-")
    assert school.logo.name.endswith(".png")
    assert not storage.exists(old_name)
    assert storage.exists(school.logo.name)
    assert [entry.action for entry in journal(school)] == [Action.SCHOOL_LOGO_CHANGED] * 2
    assert journal(school)[-1].after == {"logo": True}


def test_logo_removed(platform_admin, school, django_capture_on_commit_callbacks):
    services.update_school(
        school, actor=platform_admin, logo=SimpleUploadedFile("a.png", PNG, "image/png")
    )
    old_name = school.logo.name

    with django_capture_on_commit_callbacks(execute=True):
        services.update_school(school, actor=platform_admin, logo=None)

    school.refresh_from_db()
    assert not school.logo
    assert not school.logo.storage.exists(old_name)
    assert journal(school)[-1].after == {"logo": False}
