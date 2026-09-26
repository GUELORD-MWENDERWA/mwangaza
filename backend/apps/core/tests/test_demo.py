"""make demo : données fictives pour le développement et les démonstrations."""

import pytest
from django.contrib.auth import authenticate
from django.core.management import CommandError, call_command

from apps.accounts.demo import DEMO_PASSWORD
from apps.accounts.models import Membership, Role, User
from apps.accounts.roles import SYSTEM_ROLES
from apps.core.tenancy import use_school
from apps.schools.models import School

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo(settings):
    settings.DEBUG = True
    call_command("demo")
    return {school.code: school for school in School.objects.all()}


def roles_of(phone: str, school: School) -> set[str]:
    membership = Membership.objects.get(user__phone=phone, school=school)
    with use_school(school):
        return {str(role.code or role.name) for role in membership.roles.all()}


def test_demo_creates_the_two_demo_schools(demo):
    assert set(demo) == {"itig", "volcans"}
    assert demo["itig"].name == "ITIG Don Bosco Goma (démo)"
    assert all(school.status == School.Status.ACTIVE for school in demo.values())


def test_demo_creates_one_account_per_system_role_at_itig(demo):
    itig = demo["itig"]
    codes = [
        role
        for membership in Membership.objects.filter(school=itig)
        for role in roles_of(membership.user.phone, itig)
    ]

    assert sorted(codes) == sorted([*SYSTEM_ROLES, "Chef d'atelier"])
    assert Membership.objects.filter(school=demo["volcans"]).count() == 4


def test_demo_accounts_log_in_with_the_local_number(demo):
    head = authenticate(username="0000001001", password=DEMO_PASSWORD)

    assert head is not None
    assert roles_of(head.phone, demo["itig"]) == {"head"}
    assert authenticate(username="0000000000", password=DEMO_PASSWORD).is_platform_admin


def test_one_demo_teacher_works_in_both_schools(demo):
    teacher = User.objects.get(phone="+243000001008")

    assert {m.school.code for m in teacher.memberships.all()} == {"itig", "volcans"}
    assert roles_of(teacher.phone, demo["volcans"]) == {"teacher"}


def test_workshop_head_is_a_role_of_the_itig_demo_only(demo):
    with use_school(demo["itig"]):
        assert Role.objects.get(name="Chef d'atelier").permissions == ["students.view"]
    with use_school(demo["volcans"]):
        assert not Role.objects.filter(name="Chef d'atelier").exists()


def test_demo_can_run_twice_and_resets_the_demo(demo):
    itig = demo["itig"]
    with use_school(itig):
        cashier = Role.objects.get(code="cashier")
        cashier.name = "Caissier principal"
        cashier.permissions = []
        cashier.save()
    head = User.objects.get(phone="+243000001001")
    head.set_password("changé")
    head.save()

    call_command("demo")

    assert School.objects.count() == 2
    assert User.objects.filter(phone="+243000001001").count() == 1
    assert Membership.objects.filter(school=itig).count() == 10
    with use_school(itig):
        assert Role.objects.count() == 10
        cashier = Role.objects.get(code="cashier")
    assert (cashier.name, cashier.permissions) == ("", list(SYSTEM_ROLES["cashier"].permissions))
    assert authenticate(username="0000001001", password=DEMO_PASSWORD) == head


def test_demo_is_refused_outside_development(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError):
        call_command("demo")

    assert not School.objects.exists()
    assert not User.objects.exists()
