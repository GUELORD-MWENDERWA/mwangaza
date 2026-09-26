"""Limitation des tentatives de connexion (`apps/accounts/attempts.py`)."""

from datetime import timedelta

import pytest
from django.db.models import F

from apps.accounts import attempts
from apps.accounts.models import LoginFailure

pytestmark = pytest.mark.django_db

PHONE = "+243000090001"
IP = "10.0.0.1"


def fail(times: int, phone: str = PHONE, ip: str | None = IP) -> None:
    for _ in range(times):
        attempts.record_failure(phone, ip)


def age(minutes: int) -> None:
    LoginFailure.objects.update(created_at=F("created_at") - timedelta(minutes=minutes))


def test_five_failures_lock_the_number_for_15_minutes():
    fail(4)
    assert attempts.retry_after(PHONE, IP) == 0

    fail(1)

    wait = attempts.retry_after(PHONE, "10.9.9.9")
    assert 14 * 60 < wait <= 15 * 60 + 1


def test_lock_ends_after_15_minutes():
    fail(5)
    age(15)

    assert attempts.retry_after(PHONE, IP) == 0


def test_only_the_last_15_minutes_count():
    fail(4)
    age(10)
    fail(1)

    # Bloqué jusqu'à ce que le premier des 5 échecs ait 15 minutes : encore 5 minutes.
    assert 4 * 60 < attempts.retry_after(PHONE, IP) <= 5 * 60 + 1


def test_another_number_is_not_locked():
    fail(5)

    assert attempts.retry_after("+243000090002", "10.9.9.9") == 0


def test_an_address_is_locked_after_30_failures_on_many_numbers():
    for number in range(30):
        attempts.record_failure(f"+2430000{number:05d}", IP)

    assert attempts.retry_after("+243000090002", IP) > 0
    assert attempts.retry_after("+243000090002", "10.9.9.9") == 0


def test_ensure_allowed_gives_the_waiting_time():
    fail(5)

    with pytest.raises(attempts.TooManyAttempts) as refused:
        attempts.ensure_allowed(PHONE, IP)

    assert refused.value.status_code == 429
    assert refused.value.get_codes() == "too_many_attempts"
    assert refused.value.wait > 14 * 60


def test_success_forgets_the_failures_of_the_number():
    fail(4)
    attempts.record_failure("+243000090002", IP)

    attempts.clear_failures(PHONE)

    assert list(LoginFailure.objects.values_list("phone", flat=True)) == ["+243000090002"]


def test_failures_older_than_a_day_are_purged():
    fail(1)
    age(24 * 60 + 1)

    fail(1, phone="+243000090002")

    assert list(LoginFailure.objects.values_list("phone", flat=True)) == ["+243000090002"]


def test_national_and_international_forms_count_together():
    assert attempts.phone_key("0000090001") == attempts.phone_key("+243 000 090 001") == PHONE
    assert attempts.phone_key("  pas un numéro ") == "pas un numéro"
