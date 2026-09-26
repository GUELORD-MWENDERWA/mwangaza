"""Fixtures communes : deux écoles fictives pour prouver l'isolation dans chaque test, des comptes
avec un rôle, et des appels de l'API sur l'adresse d'une école."""

import pytest
from django.test import Client

from apps.accounts.login import MFA_SESSION_KEY
from apps.core.tenancy import get_current_school
from tests.factories import MembershipFactory, SchoolFactory


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


class Api:
    """Client de test sur l'adresse d'une école (`alpha.localhost` par défaut)."""

    def __init__(self, client: Client, host: str):
        self.client = client
        self.host = host

    def get(self, path, **params):
        return self.client.get(path, params, HTTP_HOST=self.host)

    def post(self, path, data=None):
        return self.client.post(
            path, data or {}, content_type="application/json", HTTP_HOST=self.host
        )

    def patch(self, path, data=None):
        return self.client.patch(
            path, data or {}, content_type="application/json", HTTP_HOST=self.host
        )

    def delete(self, path):
        return self.client.delete(path, HTTP_HOST=self.host)


@pytest.fixture
def api():
    """`api(user)` : session connectée comme après toutes les étapes de la connexion, double
    authentification comprise (`mfa=False` : sans elle)."""

    def make(user=None, host="alpha.localhost", *, mfa=True) -> Api:
        client = Client()
        if user is not None:
            client.force_login(user)
            session = client.session
            session[MFA_SESSION_KEY] = mfa
            session.save()
        return Api(client, host)

    return make


@pytest.fixture
def head(school):
    """Directeur de l'école alpha (seul à avoir `roles.manage` parmi les rôles système)."""
    return MembershipFactory(school=school, roles=["head"]).user


@pytest.fixture
def cashier(school):
    return MembershipFactory(school=school, roles=["cashier"]).user


@pytest.fixture
def other_head(other_school):
    """Directeur de l'école beta."""
    return MembershipFactory(school=other_school, roles=["head"]).user
