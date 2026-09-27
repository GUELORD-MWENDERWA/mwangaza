"""make demo : données fictives pour le développement et les démonstrations."""

import re
from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import CommandError, call_command

from apps.accounts import attempts, services, totp
from apps.accounts.demo import DEMO_PASSWORD, DEMO_TOTP_SECRET
from apps.accounts.models import Membership, Role, User
from apps.accounts.roles import SYSTEM_ROLES
from apps.audit.models import AuditLog
from apps.core.crypto import decrypt
from apps.core.tenancy import use_school
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Track
from tests.factories import enable_totp

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
    assert demo["itig"].primary_color == "#003C6C"
    assert demo["itig"].status == School.Status.TRIAL
    assert demo["volcans"].status == School.Status.ACTIVE


def test_demo_puts_back_the_demo_logos(demo, settings):
    from pathlib import Path

    from django.core.files.base import ContentFile

    media = Path(settings.MEDIA_ROOT)
    volcans = demo["volcans"]
    volcans.logo.save("logo.png", ContentFile(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8))
    stored = volcans.logo.name

    call_command("demo")

    volcans.refresh_from_db()
    itig = School.objects.get(code="itig")
    assert not volcans.logo
    assert not (media / stored).exists()
    # Logo public de l'ITIG, un seul fichier gardé même après plusieurs `make demo`.
    assert itig.logo.name.endswith(".png")
    assert len(list((media / "schools" / str(itig.pk)).iterdir())) == 1


def test_demo_puts_back_a_suspended_school(demo):
    demo["volcans"].status = School.Status.SUSPENDED
    demo["volcans"].primary_color = "#000000"
    demo["volcans"].save()

    call_command("demo")

    volcans = School.objects.get(code="volcans")
    assert volcans.status == School.Status.ACTIVE
    assert volcans.primary_color == "#7A3E00"


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


def test_demo_accounts_that_require_it_have_two_factor_authentication(demo):
    enabled = set(
        User.objects.filter(totp_enabled_at__isnull=False).values_list("phone", flat=True)
    )

    # Super-admin, directeur, comptable, caissière de chaque école ; pas le promoteur de l'ITIG
    # (activation à essayer), ni l'enseignant, la secrétaire…
    assert enabled == {
        "+243000000000",
        "+243000001001",
        "+243000001004",
        "+243000001005",
        "+243000002001",
        "+243000002004",
        "+243000002005",
    }
    head = User.objects.get(phone="+243000001001")
    assert decrypt(head.totp_secret) == DEMO_TOTP_SECRET


def test_demo_resets_two_factor_authentication(demo):
    head = User.objects.get(phone="+243000001001")
    services.reset_totp(head)
    promoter = User.objects.get(phone="+243000001007")
    enable_totp(promoter)

    call_command("demo")

    head.refresh_from_db()
    promoter.refresh_from_db()
    assert head.totp_enabled
    assert not promoter.totp_enabled


def test_demo_code_is_shown(settings):
    settings.DEBUG = True
    out = StringIO()

    call_command("totp", stdout=out)

    shown = out.getvalue()[:7].replace(" ", "")
    # Le code affiché est celui de la clé de démonstration (période en cours ou qui vient de finir).
    now = totp.current_step()
    assert shown in {totp.code_at(DEMO_TOTP_SECRET, step) for step in (now - 1, now)}


def test_code_for_another_key(settings):
    settings.DEBUG = True
    out = StringIO()

    call_command("totp", "--key", "jbsw y3dp ehpk 3pxp", stdout=out)

    assert re.match(r"\d{3} \d{3}  \(valable encore \d+ s\)", out.getvalue())
    with pytest.raises(CommandError):
        call_command("totp", "--key", "pas une clé 0189")


def test_demo_code_is_refused_outside_development(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError):
        call_command("totp")


def test_demo_unblocks_logins(demo):
    for _ in range(5):
        attempts.record_failure("+243000001005", "127.0.0.1")

    call_command("demo")

    assert attempts.retry_after("+243000001005", "127.0.0.1") == 0


# Organisation scolaire (1.7)


def test_demo_organisation_of_the_itig(demo):
    with use_school(demo["itig"]):
        year = AcademicYear.objects.get()
        levels = list(Level.objects.values_list("name", flat=True))
        tracks = set(Track.objects.values_list("code", flat=True))
        groups = list(ClassGroup.objects.select_related("level", "track", "homeroom_teacher"))
        terms = list(year.terms.all())

    assert (year.name, year.is_current) == ("2026-2027", True)
    assert levels == ["7e EB", "8e EB", "1re", "2e", "3e", "4e"]
    assert tracks == {"ELEC", "ELO", "MG", "MA"}
    assert len(groups) == 23
    assert [group.name for group in groups[:3]] == ["7e EB A", "7e EB B", "7e EB C"]
    [titular] = [group for group in groups if group.homeroom_teacher]
    assert (titular.name, titular.homeroom_teacher.phone) == ("3e Électricité A", "+243000001008")
    assert [term.kind for term in terms] == ["semester", "period", "period", "exam"] * 2
    assert all(term.starts_on for term in terms)
    assert demo["itig"].matricule_format == "ITIG-{AAAA}-{0000}"


def test_demo_organisation_of_volcans_is_separate(demo):
    with use_school(demo["volcans"]):
        groups = [group.name for group in ClassGroup.objects.all()]
        terms = list(AcademicYear.objects.get().terms.all())

    assert groups == ["7e EB A", "8e EB A", "1re Scientifique A", "2e Pédagogie générale A"]
    assert not any(term.starts_on for term in terms)  # dates à saisir par l'école
    assert demo["volcans"].matricule_format == "LV/{AA}/{0000}"


def test_demo_organisation_runs_twice_without_duplicates_nor_journal(demo):
    itig = demo["itig"]
    with use_school(itig):
        extra = AcademicYear.objects.create(
            name="2027-2028", starts_on="2027-09-01", ends_on="2028-07-01"
        )
        AcademicYear.objects.filter(name="2026-2027").update(is_current=False)
        AcademicYear.objects.filter(pk=extra.pk).update(is_current=True)

    call_command("demo")

    with use_school(itig):
        assert ClassGroup.objects.count() == 23
        assert AcademicYear.objects.get(is_current=True).name == "2026-2027"
        assert AcademicYear.objects.get(name="2026-2027").terms.count() == 8
        assert AcademicYear.objects.filter(pk=extra.pk).exists()  # ajoutée en essayant : gardée
    assert not AuditLog.all_schools.filter(action__startswith="organisation.").exists()
