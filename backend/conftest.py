"""Fixtures communes : deux écoles fictives pour prouver l'isolation dans chaque test, des comptes
avec un rôle, et des appels de l'API sur l'adresse d'une école."""

import time

import pytest
from django.test import Client

from apps.accounts import privileged
from apps.accounts.login import MFA_SESSION_KEY
from apps.accounts.models import User
from apps.core.tenancy import get_current_school
from tests.factories import MembershipFactory, SchoolFactory


@pytest.fixture
def school(db):
    return SchoolFactory(code="alpha", name="École Alpha (fictive)")


@pytest.fixture
def other_school(db):
    return SchoolFactory(code="beta", name="École Beta (fictive)")


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    """Fichiers (logos) de chaque test dans un dossier temporaire, jamais dans `backend/media`."""
    settings.MEDIA_ROOT = tmp_path / "media"


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

    def put(self, path, data=None):
        return self.client.put(
            path, data or {}, content_type="application/json", HTTP_HOST=self.host
        )

    def delete(self, path):
        return self.client.delete(path, HTTP_HOST=self.host)


def _open_session(client: Client, user, *, mfa: bool) -> None:
    client.force_login(user)
    session = client.session
    session[MFA_SESSION_KEY] = mfa
    if user.is_platform_admin:
        # Comme à la connexion (`privileged.keep_short`) : session courte, déjà datée.
        session.set_expiry(privileged.IDLE_SECONDS)
        session[privileged.SEEN_SESSION_KEY] = time.time()
    session.save()


@pytest.fixture
def api():
    """`api(user)` : session connectée comme après toutes les étapes de la connexion, double
    authentification comprise (`mfa=False` : sans elle)."""

    def make(user=None, host="alpha.localhost", *, mfa=True) -> Api:
        client = Client()
        if user is not None:
            _open_session(client, user, mfa=mfa)
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


@pytest.fixture
def platform_admin(db):
    """Super-admin de la plateforme (administration Django, session support)."""
    return User.objects.create_superuser("0000000000", "secret-123", last_name="Admin")


@pytest.fixture
def admin_client(platform_admin):
    """Super-admin connecté à l'administration Django, double authentification comprise."""
    client = Client(HTTP_HOST="localhost")
    _open_session(client, platform_admin, mfa=True)
    return client
