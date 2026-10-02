"""Adresse IP du visiteur : derrière Caddy, celle que le proxy transmet, jamais celle d'un en-tête
envoyé par le visiteur lui-même (il contournerait le blocage par adresse)."""

import pytest
from django.test import RequestFactory, override_settings

from apps.core.http import client_ip

CADDY = "172.18.0.5"


def request(**headers):
    return RequestFactory().get("/api/auth/login/", REMOTE_ADDR=CADDY, **headers)


@override_settings(CLIENT_IP_HEADER="HTTP_X_REAL_IP")
@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("41.243.12.7", "41.243.12.7"),
        ("2c0f:f248::1", "2c0f:f248::1"),
        (None, CADDY),  # requête interne, sans le proxy
        ("41.243.12.7, 10.0.0.1", CADDY),  # pas une adresse : ignorée
        ("' OR 1=1", CADDY),
    ],
)
def test_behind_the_proxy_the_address_comes_from_its_header(header, expected):
    headers = {} if header is None else {"HTTP_X_REAL_IP": header}
    assert client_ip(request(**headers)) == expected


@override_settings(CLIENT_IP_HEADER=None)
def test_without_proxy_headers_sent_by_the_visitor_are_ignored():
    spoofed = request(HTTP_X_REAL_IP="1.2.3.4", HTTP_X_FORWARDED_FOR="1.2.3.4")
    assert client_ip(spoofed) == CADDY
