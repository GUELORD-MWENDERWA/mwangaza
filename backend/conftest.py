"""Fixtures communes : deux écoles fictives pour prouver l'isolation dans chaque test."""

import pytest

from apps.core.tenancy import get_current_school
from tests.factories import SchoolFactory


@pytest.fixture
def school(db):
    return SchoolFactory(code="alpha", name="École Alpha (fictive)")


@pytest.fixture
def other_school(db):
    return SchoolFactory(code="beta", name="École Beta (fictive)")


@pytest.fixture(autouse=True)
def _no_current_school_left_behind():
    yield
    assert get_current_school() is None, "un test a laissé une école courante définie"
