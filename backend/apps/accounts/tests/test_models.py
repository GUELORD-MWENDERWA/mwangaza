"""Comptes, rôles et appartenances au niveau des modèles."""

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction

from apps.accounts import services
from apps.accounts.models import LoginFailure, Membership, RecoveryCode, Role, User
from apps.core.crypto import decrypt
from apps.core.ids import is_uuid7
from apps.core.tenancy import CrossSchoolError, SchoolNotSetError, use_school
from tests.factories import (
    TEST_PASSWORD,
    MembershipFactory,
    UserFactory,
    enable_totp,
    starter_role,
    totp_code,
)

pytestmark = pytest.mark.django_db


# Compte


def test_user_model_is_the_phone_account():
    assert get_user_model() is User
    assert User.USERNAME_FIELD == "phone"


def test_create_user_stores_the_international_form():
    user = User.objects.create_user("097 123 45 67", "secret-123", last_name="Kasereka")

    assert user.phone == "+243971234567"
    assert is_uuid7(user.id)
    assert user.check_password("secret-123")
    assert not user.is_platform_admin
    assert user.language == "fr"


def test_create_user_without_password_cannot_log_in():
    user = User.objects.create_user("0971234567", last_name="Kasereka")

    assert not user.has_usable_password()


def test_phone_is_unique_whatever_the_form_typed():
    User.objects.create_user("0971234567", last_name="Un")

    with pytest.raises(IntegrityError):
        User.objects.create_user("+243 97 123 45 67", last_name="Deux")


def test_log_in_with_the_phone_as_typed():
    user = UserFactory(phone="+243971234567")

    assert authenticate(username="097 123 45 67", password=TEST_PASSWORD) == user
    assert authenticate(username="0971234567", password="mauvais") is None
    assert authenticate(username="pas un numéro", password=TEST_PASSWORD) is None


def test_inactive_account_cannot_log_in():
    UserFactory(phone="+243971234567", is_active=False)

    assert authenticate(username="0971234567", password=TEST_PASSWORD) is None


def test_full_name_follows_congolese_order():
    user = UserFactory(last_name="Kambale", middle_name="Muhindo", first_name="Patrice")

    assert user.get_full_name() == "Kambale Muhindo Patrice"
    assert str(user) == "Kambale Muhindo Patrice"
    assert user.get_short_name() == "Patrice"


def test_only_platform_admin_enters_django_admin():
    user = UserFactory()
    admin = User.objects.create_superuser("0000000000", "secret-123", last_name="Admin")

    assert not user.is_staff
    assert not user.has_perm("accounts.view_user")
    assert not user.has_module_perms("accounts")
    assert admin.is_platform_admin and admin.is_staff
    assert admin.has_perm("accounts.view_user")
    assert admin.has_perms(["accounts.view_user", "schools.change_school"])
    assert admin.has_module_perms("accounts")
    admin.is_active = False
    assert not admin.has_perm("accounts.view_user")


def test_created_by_is_recorded():
    head = UserFactory()
    user = UserFactory(created_by=head)

    user.refresh_from_db()
    assert user.created_by == head


# Rôle


def test_role_needs_a_school(db):
    with pytest.raises(SchoolNotSetError):
        Role.objects.create(name="Chef d'atelier")


def test_role_names_are_unique_per_school_ignoring_case(school, other_school):
    with use_school(school):
        Role.objects.create(name="Chef d'atelier")
    with use_school(other_school):
        Role.objects.create(name="Chef d'atelier")  # autre école : permis
    with use_school(school), pytest.raises(IntegrityError):
        Role.objects.create(name="CHEF D'ATELIER")


def test_role_needs_a_name(school):
    with use_school(school), pytest.raises(IntegrityError):
        Role.objects.create(name="")


# Appartenance


def test_one_membership_per_person_and_school(school):
    membership = MembershipFactory(school=school)

    with pytest.raises(IntegrityError):
        Membership.objects.create(user=membership.user, school=school)


def test_one_account_in_two_schools(school, other_school):
    user = UserFactory()
    MembershipFactory(user=user, school=school, roles=["head"])
    MembershipFactory(user=user, school=other_school, roles=["teacher"])

    assert {m.school for m in user.memberships.all()} == {school, other_school}


def test_several_roles_in_one_school(school):
    membership = MembershipFactory(school=school, roles=["teacher", "secretary"])

    with use_school(school):
        assert {role.name for role in membership.roles.all()} == {"Enseignant", "Secrétaire"}


def test_role_of_another_school_is_refused(school, other_school):
    membership = MembershipFactory(school=other_school)
    alpha_head = starter_role(school, "head")

    # Le refus annule la transaction en cours : chaque essai dans la sienne.
    with use_school(other_school), pytest.raises(CrossSchoolError), transaction.atomic():
        membership.roles.add(alpha_head)
    with pytest.raises(CrossSchoolError), transaction.atomic():
        membership.roles.add(alpha_head.pk)  # sans école courante, par identifiant
    with use_school(school), pytest.raises(CrossSchoolError), transaction.atomic():
        alpha_head.memberships.add(membership)  # dans l'autre sens

    assert not Membership.roles.through.objects.filter(membership=membership).exists()


# Double authentification


def test_totp_key_is_encrypted_in_the_database():
    user = UserFactory()
    secret = enable_totp(user)

    stored = User.objects.values_list("totp_secret", flat=True).get(pk=user.pk)

    assert secret not in stored
    assert decrypt(stored) == secret
    assert user.totp_enabled


def test_recovery_codes_are_stored_as_fingerprints():
    user = UserFactory()
    secret = enable_totp(user)

    codes = services.enable_totp(user, secret, totp_code(secret))

    stored = set(RecoveryCode.objects.filter(user=user).values_list("digest", flat=True))
    assert len(stored) == 8
    assert not {code.replace("-", "") for code in codes} & stored
    assert not set(codes) & stored


def test_login_failures_are_platform_wide(db):
    # [G] : un numéro vaut dans toutes les écoles ; lu sans école courante.
    LoginFailure.objects.create(phone="+243000090001", ip="10.0.0.1")

    assert LoginFailure.objects.count() == 1
