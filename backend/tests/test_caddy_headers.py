"""Les fichiers des trois applications sont servis avec les en-têtes de sécurité (S.1)."""

import re
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[2] / "infra" / "routes.caddy"


def _block(text: str, name: str) -> str:
    """Corps du bloc `(name) { … }` de routes.caddy (accolades équilibrées)."""
    start = text.index(f"({name}) {{") + len(f"({name}) {{")
    depth = 1
    for i, char in enumerate(text[start:], start):
        depth += (char == "{") - (char == "}")
        if depth == 0:
            return text[start:i]
    raise AssertionError(name)


def test_applications_servies_avec_les_en_tetes_de_securite():
    text = ROUTES.read_text()
    # Les trois applications passent par `pwa`, qui importe `securite`.
    assert "import securite" in _block(text, "pwa")
    assert len(re.findall(r"import pwa /srv/(gestion|portail|console)", text)) == 3
    block = _block(text, "securite")
    for header in ("Strict-Transport-Security", "X-Frame-Options DENY", "Permissions-Policy"):
        assert header in block
    csp = re.search(r'\{\$CSP_HEADER:([\w-]+)\} "([^"]+)"', block)
    assert csp and csp.group(1) == "Content-Security-Policy-Report-Only"
    directives = csp.group(2)
    for rule in (
        "default-src 'self'",
        "frame-ancestors 'none'",
        "connect-src 'self'",
        "object-src 'none'",
    ):
        assert rule in directives
    assert "unsafe-eval" not in directives
    assert "unsafe-inline" not in re.search(r"script-src[^;]*", directives).group(0)
