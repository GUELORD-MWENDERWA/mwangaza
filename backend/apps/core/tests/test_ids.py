"""UUID v7 (RFC 9562) : identifiants triés par date de création, générés sans serveur."""

import time
import uuid

import pytest

from apps.core import ids
from apps.core.ids import is_uuid7, uuid7


def timestamp_ms(value: uuid.UUID) -> int:
    return value.int >> 80


def test_uuid7_has_version_7_and_rfc_variant():
    value = uuid7()

    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_uuid7_starts_with_current_time_in_milliseconds():
    before = time.time_ns() // 1_000_000
    value = uuid7()
    after = time.time_ns() // 1_000_000

    assert before <= timestamp_ms(value) <= after


def test_uuid7_values_are_unique_and_increasing():
    values = [uuid7() for _ in range(10_000)]

    assert len(set(values)) == len(values)
    assert values == sorted(values)


def test_uuid7_stays_increasing_when_the_clock_goes_back(monkeypatch):
    first = uuid7()
    monkeypatch.setattr(ids.time, "time_ns", lambda: (timestamp_ms(first) - 5_000) * 1_000_000)

    second = uuid7()

    assert second > first


def test_uuid7_counter_overflow_moves_to_next_millisecond(monkeypatch):
    frozen_ms = time.time_ns() // 1_000_000 + 60_000
    monkeypatch.setattr(ids.time, "time_ns", lambda: frozen_ms * 1_000_000)
    first = uuid7()
    monkeypatch.setattr(ids, "_last_counter", ids._COUNTER_MAX)

    second = uuid7()

    assert timestamp_ms(second) == timestamp_ms(first) + 1
    assert second > first


def test_uuid7_keeps_32_random_bits_in_the_same_millisecond(monkeypatch):
    frozen_ms = time.time_ns() // 1_000_000 + 120_000
    monkeypatch.setattr(ids.time, "time_ns", lambda: frozen_ms * 1_000_000)

    tails = {uuid7().int & 0xFFFF_FFFF for _ in range(50)}

    # Pas de suite prévisible (+1) : un identifiant ne permet pas de deviner le suivant.
    assert len(tails) > 45


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (uuid7(), True),
        (str(uuid7()), True),
        (uuid.uuid4(), False),
        (str(uuid.uuid4()), False),
        ("pas-un-uuid", False),
        ("", False),
        (None, False),
        (42, False),
    ],
)
def test_is_uuid7(value, expected):
    assert is_uuid7(value) is expected
