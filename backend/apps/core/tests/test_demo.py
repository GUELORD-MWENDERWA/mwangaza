"""make demo : données fictives pour le développement et les démonstrations.

Une démonstration complète coûte près d'une minute en CI : le scénario principal la fait trois
fois seulement (première fois, seconde fois qui remet tout comme au départ, passage « serveur »)
au lieu d'un `make demo` par vérification (24 fois, 21 minutes de CI). Une vérification de plus
s'ajoute à l'étape qui lui correspond, pas dans un nouveau test qui refait la démonstration."""

import re
from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import CommandError, call_command

from apps.academics.models import (
    Deliberation,
    DisciplineIncident,
    DisciplineRule,
    Grade,
    PlaceConfirmation,
)
from apps.accounts import attempts, services, totp
from apps.accounts.demo import DEMO_PASSWORD, DEMO_TOTP_SECRET
from apps.accounts.models import Membership, Role, User
from apps.accounts.phone import is_demo_phone
from apps.accounts.roles import STARTER_ROLES
from apps.audit.models import AuditLog
from apps.core.crypto import decrypt
from apps.core.demo import STEPS, fill
from apps.core.models import PlatformSettings
from apps.core.tenancy import use_school
from apps.finance.models import Payment
from apps.finance.tests.test_payments import pay, school_with_fees
from apps.schools.demo import DemoNumbers, DemoSpace
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Track
from apps.students.models import Enrollment, Family, Guardian, Student
from tests.factories import SchoolFactory, enable_totp

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo(settings):
    # Développement : `DEBUG` (super-admin fictif, clé commune de double authentification).
    settings.DEMO_DATA = True
    settings.DEBUG = True
    call_command("demo")
    return {school.code: school for school in School.objects.all()}


def roles_of(phone: str, school: School) -> set[str]:
    membership = Membership.objects.get(user__phone=phone, school=school)
    with use_school(school):
        return {role.name for role in membership.roles.all()}


def test_demo_creates_the_spaces_puts_them_back_and_runs_on_a_server(demo, settings):
    created(demo)
    rerun_puts_everything_back(demo, settings)
    server_run(settings)


def created(demo) -> None:
    """Première fois : écoles, comptes, élèves, organisation, double authentification."""
    itig, volcans = demo["itig"], demo["volcans"]
    assert set(demo) == {"itig", "volcans"}
    assert itig.name == "ITIG DON BOSCO"
    assert itig.primary_color == "#003C6C"
    assert itig.status == School.Status.TRIAL
    assert volcans.status == School.Status.ACTIVE
    # Données fictives : jamais dans un espace réel (`03` § 4 bis).
    assert {school.environment for school in demo.values()} == {School.Environment.DEMO}
    # Conduite (8.5.1a) : liste proposée et incidents dans chaque espace.
    for school in demo.values():
        with use_school(school):
            assert DisciplineRule.objects.count() == 10
            assert DisciplineIncident.objects.exists()
    # Reprise des résultats (8.4.7) : la 8EB C sans aucune note, la moitié de ses élèves repris.
    with use_school(itig):
        paper = Deliberation.objects.get(class_group__level__name="8EB", class_group__section="C")
        assert not Grade.objects.filter(enrollment__class_group=paper.class_group).exists()
        repris = paper.decisions.filter(prior_percent__isnull=False).count()
        enrolled = paper.class_group.enrollments.filter(status="active").count()
        assert repris == (enrolled + 1) // 2
    # Passage de classe (8.4.5) : 2027-2028 préparée (pas en cours), la classe de l'enfant du
    # portail proclamée, des places proposées et des réponses ; la sienne attend le parent.
    with use_school(itig):
        following = AcademicYear.objects.get(name="2027-2028")
        assert not following.is_current
        assert following.class_groups.count() == 23
        places = PlaceConfirmation.objects.select_related("enrollment__student__family")
        assert {p.answer for p in places} == {"yes", "no", ""}
        family = Family.objects.order_by("created_at", "id").first()
        assert [p.answer for p in places if p.enrollment.student.family == family] == [""]
        assert not Enrollment.objects.filter(academic_year=following).exists()

    # Un compte par rôle, chaque école nomme ses rôles à sa façon : pas de « Directeur » à l'ITIG.
    names = [
        role
        for membership in Membership.objects.filter(school=itig)
        for role in roles_of(membership.user.phone, itig)
    ]
    with use_school(itig):
        assert sorted(names) == sorted(Role.objects.values_list("name", flat=True))
        assert Role.objects.get(name="Chef d'atelier").permissions == ["students.view"]
    with use_school(volcans):
        assert not Role.objects.filter(name="Chef d'atelier").exists()
    assert {"Préfet des études", "Caissier", "Chef d'atelier"} <= set(names)
    assert "Directeur" not in names
    assert roles_of("+243000002001", volcans) == {"Directeur"}
    assert roles_of("+243000002005", volcans) == {"Caissière"}
    assert Membership.objects.filter(school=volcans).count() == 4
    # Connexion avec le numéro local ; l'enseignant de démonstration travaille dans les deux.
    head = authenticate(username="0000001001", password=DEMO_PASSWORD)
    assert head is not None
    assert roles_of(head.phone, itig) == {"Préfet des études"}
    assert authenticate(username="0000000000", password=DEMO_PASSWORD).is_platform_admin
    teacher = User.objects.get(phone="+243000001008")
    assert {m.school.code for m in teacher.memberships.all()} == {"itig", "volcans"}
    assert roles_of(teacher.phone, volcans) == {"Enseignant"}

    # Double authentification : super-admin, directeur, directeur des études (ITIG : valide les
    # notes), comptable, caissière ; pas le promoteur de l'ITIG (activation à essayer), ni
    # l'enseignant, la secrétaire…
    enabled = set(
        User.objects.filter(totp_enabled_at__isnull=False).values_list("phone", flat=True)
    )
    assert enabled == {
        "+243000000000",
        "+243000001001",
        "+243000001002",
        "+243000001004",
        "+243000001005",
        "+243000002001",
        "+243000002004",
        "+243000002005",
    }
    assert decrypt(head.totp_secret) == DEMO_TOTP_SECRET

    # Élèves : fratries, une famille dans les deux écoles, numéros fictifs.
    with use_school(itig):
        assert Enrollment.objects.filter(status="active").count() == 800
        families = Student.objects.values_list("family", flat=True)
        assert len(set(families)) < 800  # des fratries
        assert Student.objects.filter(matricule="ITIG-2026-0001").exists()
        phones = set(Guardian.objects.values_list("phone", flat=True))
    with use_school(volcans):
        assert Student.objects.count() == 150
        assert phones & set(Guardian.objects.values_list("phone", flat=True))
    assert all(phone.startswith("+24300") for phone in phones)

    # Organisation scolaire (1.7) de l'ITIG.
    with use_school(itig):
        year = AcademicYear.objects.get(name="2026-2027")
        levels = list(Level.objects.values_list("name", flat=True))
        tracks = set(Track.objects.values_list("code", flat=True))
        groups = list(
            ClassGroup.objects.filter(academic_year=year).select_related(
                "level", "track", "homeroom_teacher"
            )
        )
        terms = list(year.terms.all())
    assert (year.name, year.is_current) == ("2026-2027", True)
    assert levels == ["7EB", "8EB", "1HT", "2HT", "3HT", "4HT"]
    assert tracks == {"ELEC", "ELO", "MG", "MA"}
    assert len(groups) == 23
    assert [group.name for group in groups[:3]] == ["7EB A", "7EB B", "7EB C"]
    titulars = {
        group.name: group.homeroom_teacher.phone for group in groups if group.homeroom_teacher
    }
    assert titulars["3HT ÉLECTRICITÉ A"] == "+243000001008"
    # 5.7 : la classe de l'enfant du compte du portail a aussi un titulaire (le portail le
    # montre), l'enseignant de démonstration faute d'autre.
    assert set(titulars.values()) == {"+243000001008"}
    assert len(titulars) <= 2
    assert [term.kind for term in terms] == ["semester", "period", "period", "exam"] * 2
    assert all(term.starts_on for term in terms)
    assert itig.matricule_format == "ITIG-{AAAA}-{0000}"
    # Celle des Volcans, à part.
    with use_school(volcans):
        groups = [group.name for group in ClassGroup.objects.all()]
        terms = list(AcademicYear.objects.get().terms.all())
    assert groups == ["7E EB A", "8E EB A", "1RE SCIENTIFIQUE A", "2E PÉDAGOGIE GÉNÉRALE A"]
    assert not any(term.starts_on for term in terms)  # dates à saisir par l'école
    assert volcans.matricule_format == "LV/{AA}/{0000}"


def rerun_puts_everything_back(demo, settings) -> None:
    """Seconde fois : tout ce qu'on a changé en essayant est remis comme au départ, sans double."""
    from pathlib import Path

    from django.core.files.base import ContentFile

    itig, volcans = demo["itig"], demo["volcans"]
    media = Path(settings.MEDIA_ROOT)
    volcans.logo.save("logo.png", ContentFile(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8))
    stored = volcans.logo.name
    volcans.status = School.Status.SUSPENDED
    volcans.primary_color = "#000000"
    volcans.save()
    with use_school(itig):
        cashier = Role.objects.get(name="Caissier")
        cashier.permissions = []
        cashier.save()
        extra = AcademicYear.objects.get(name="2027-2028")
        AcademicYear.objects.filter(name="2026-2027").update(is_current=False)
        AcademicYear.objects.filter(pk=extra.pk).update(is_current=True)
    head = User.objects.get(phone="+243000001001")
    head.set_password("changé")
    head.save()
    services.reset_totp(head)
    promoter = User.objects.get(phone="+243000001007")
    enable_totp(promoter)
    kept = User.objects.get(phone="+243000001002").password
    PlatformSettings.objects.update(name="Lumière", primary_color="#000000")
    for _ in range(5):
        attempts.record_failure("+243000001005", "127.0.0.1")

    call_command("demo")

    # Logos : celui ajouté aux Volcans effacé ; logo public de l'ITIG, un seul fichier gardé.
    volcans.refresh_from_db()
    itig = School.objects.get(code="itig")
    assert not volcans.logo
    assert not (media / stored).exists()
    assert itig.logo.name.endswith(".png")
    folder = media / "schools" / str(itig.pk)
    assert len([f for f in folder.iterdir() if f.name.startswith("logo")]) == 1
    # École suspendue remise en service, sa couleur aussi.
    assert volcans.status == School.Status.ACTIVE
    assert volcans.is_demo
    assert volcans.primary_color == "#7A3E00"
    # Plateforme, comptes et rôles remis, sans double.
    platform = PlatformSettings.load()
    assert (platform.name, platform.primary_color) == ("Mwangaza", "#0B5FCC")
    assert platform.support_phone and platform.legal_notice
    assert School.objects.count() == 2
    assert User.objects.filter(phone="+243000001001").count() == 1
    assert Membership.objects.filter(school=itig).count() == 10
    with use_school(itig):
        assert Role.objects.count() == 10
        cashier = Role.objects.get(name="Caissier")
        assert Student.objects.count() == 800
    assert cashier.permissions == list(STARTER_ROLES["cashier"].permissions)
    assert authenticate(username="0000001001", password=DEMO_PASSWORD) == head
    # Mot de passe déjà le bon : hachage gardé, `make demo` ne ferme pas les sessions ouvertes.
    assert User.objects.get(phone="+243000001002").password == kept
    # Double authentification remise : le directeur l'a, le promoteur ne l'a plus.
    head.refresh_from_db()
    promoter.refresh_from_db()
    assert head.totp_enabled
    assert not promoter.totp_enabled
    # Essais ratés débloqués.
    assert attempts.retry_after("+243000001005", "127.0.0.1") == 0
    # Organisation : pas de double ni de journal ; l'année suivante n'est pas recréée.
    with use_school(itig):
        assert ClassGroup.objects.filter(academic_year__name="2026-2027").count() == 23
        assert ClassGroup.objects.filter(academic_year=extra).count() == 23
        assert AcademicYear.objects.get(is_current=True).name == "2026-2027"
        assert AcademicYear.objects.get(name="2026-2027").terms.count() == 8
        assert AcademicYear.objects.filter(pk=extra.pk).exists()
    assert not AuditLog.all_schools.filter(action__startswith="organisation.").exists()


def server_run(settings) -> None:
    """Essai sur plusieurs appareils, serveur de démonstration en ligne : mot de passe propre au
    serveur, ni clé commune ni code demandé (comptes partagés entre visiteurs), et plus de
    super-admin fictif, dont le mot de passe et la clé sont écrits dans le dépôt."""
    settings.DEBUG = False
    settings.DEMO_PASSWORD = "propre-au-serveur"
    enable_totp(User.objects.get(phone="+243000001007"))

    call_command("demo")

    cashier = User.objects.get(phone="+243000001005")
    assert authenticate(username="0000001005", password="propre-au-serveur") == cashier
    assert authenticate(username="0000001005", password=DEMO_PASSWORD) is None
    assert not User.objects.filter(totp_enabled_at__isnull=False).exists()
    assert not services.totp_required(cashier)
    admin = User.objects.get(phone="+243000000000")
    assert not admin.is_platform_admin and not admin.is_active


def test_demo_is_refused_outside_development_and_the_essai(settings):
    # Serveur : `DJANGO_DEMO_DATA` absent ; seul l'essai sur plusieurs appareils le met.
    settings.DEMO_DATA = False

    with pytest.raises(CommandError):
        call_command("demo")

    assert not School.objects.exists()
    assert not User.objects.exists()


def test_demo_is_refused_on_a_platform_with_a_live_school_and_nothing_moves(
    settings, school, head, cashier, platform_admin
):
    """Tous les espaces partagent une plateforme (`03` § 4 bis) : le réglage ne suffit pas. Comme
    sur un serveur (pas `DEBUG`), où `make demo` retire ses droits au compte `0000000000`."""
    settings.DEMO_DATA, settings.DEBUG = True, False
    payment = pay(school, cashier, school_with_fees(school, head)["enrollment"], 12000, "USD")
    PlatformSettings.objects.update_or_create(
        pk=1, defaults={"name": "Shule Yetu", "support_phone": "+243970000001"}
    )

    with pytest.raises(CommandError, match="Démonstration"):
        call_command("demo")

    assert list(School.objects.values_list("code", "environment")) == [("alpha", "live")]
    with use_school(school):
        assert Payment.objects.get() == payment
    platform = PlatformSettings.objects.get()
    assert (platform.name, str(platform.support_phone)) == ("Shule Yetu", "+243970000001")
    platform_admin.refresh_from_db()
    assert platform_admin.is_platform_admin and platform_admin.is_active


def test_demo_never_changes_the_kind_of_an_existing_space(settings):
    """Le code `volcans` est pris par un espace d'essai : il ne devient pas une démonstration,
    dont les données sont remplacées et qui se supprime."""
    settings.DEMO_DATA = settings.DEBUG = True
    SchoolFactory(code="volcans", name="Essai des Volcans", environment=School.Environment.TEST)

    with pytest.raises(CommandError, match="volcans"):
        call_command("demo")

    spaces = School.objects.values_list("code", "name", "environment")
    assert list(spaces) == [("volcans", "Essai des Volcans", "test")]
    assert not User.objects.exists()


def test_another_demo_space_gets_the_same_data_in_its_own_numbers(db):
    """Le code de `make demo` remplit n'importe quel espace de démonstration (console, 4.17.2) :
    mêmes données, numéros de son bloc, son mot de passe ; rien dans un espace réel."""
    school = School.objects.create(
        code="vitrine", name="École vitrine", environment=School.Environment.DEMO
    )
    space = DemoSpace(school, "volcans", DemoNumbers.block(40), "mot-de-passe-vitrine")
    steps = []

    fill([space], on_step=lambda done, total: steps.append((done, total)))

    assert steps == [(done, len(STEPS)) for done in range(1, len(STEPS) + 1)]
    staff = set(Membership.objects.filter(school=school).values_list("user__phone", flat=True))
    assert staff == {"+243004002001", "+243004002004", "+243004002005", "+243004001008"}
    head = authenticate(username="0004002001", password="mot-de-passe-vitrine")
    assert roles_of(head.phone, school) == {"Directeur"}
    assert not head.totp_enabled and not services.totp_required(head)
    with use_school(school):
        assert Student.objects.count() == 150
        phones = set(Guardian.objects.values_list("phone", flat=True))
        assert all(phone.startswith("+24300401") for phone in phones)
    # Le parent du portail : premier tuteur de la première famille, même mot de passe.
    assert authenticate(username="0004010001", password="mot-de-passe-vitrine") is not None
    assert all(is_demo_phone(phone) for phone in User.objects.values_list("phone", flat=True))

    real = School.objects.create(code="reelle", name="École réelle")
    with pytest.raises(ValueError, match="reelle"):
        fill([DemoSpace(real, "volcans", DemoNumbers.block(41), "x")])
    with use_school(real):
        assert not Student.objects.exists()


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
