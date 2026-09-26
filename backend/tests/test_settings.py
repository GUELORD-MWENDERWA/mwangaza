"""Lecture des variables d'environnement : une ligne `NOM=` vide dans `.env` vaut « absente »."""

import pytest

from config.settings.base import env, env_bool, env_list


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_variable_falls_back_to_default(monkeypatch, value):
    monkeypatch.setenv("MWANGAZA_TEST_VAR", value)

    assert env("MWANGAZA_TEST_VAR", "par-defaut") == "par-defaut"
    assert env("MWANGAZA_TEST_VAR") is None
    assert env_bool("MWANGAZA_TEST_VAR", True) is True
    assert env_list("MWANGAZA_TEST_VAR", "a,b") == ["a", "b"]


def test_set_variable_is_used(monkeypatch):
    monkeypatch.setenv("MWANGAZA_TEST_VAR", "valeur")

    assert env("MWANGAZA_TEST_VAR", "par-defaut") == "valeur"


def test_missing_variable_uses_default(monkeypatch):
    monkeypatch.delenv("MWANGAZA_TEST_VAR", raising=False)

    assert env("MWANGAZA_TEST_VAR", "par-defaut") == "par-defaut"
    assert env_bool("MWANGAZA_TEST_VAR") is False
    assert env_list("MWANGAZA_TEST_VAR") == []
