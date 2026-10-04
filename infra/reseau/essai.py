"""Essai de l'application construite sur plusieurs appareils du même réseau (`make reseau`).

    init      crée `reseau.env` (hors Git) avec des secrets neufs, puis vérifie qu'il est rempli
    ip [IP]   met l'adresse de la machine sur le réseau dans DuckDNS (après un changement de réseau)
    accueil   écrit la page d'accueil de l'essai : adresses et QR codes des applications
    adresses  affiche les adresses

Lancé depuis `backend/` par `uv run` : segno et la création des clés Web Push viennent du projet.
"""

import re
import secrets
import socket
import sys
import urllib.parse
import urllib.request
from html import escape
from pathlib import Path

import segno

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / "reseau.env"
PAGE = HERE / "accueil" / "index.html"
sys.path.insert(0, str(HERE.parent.parent / "backend"))

from apps.notifications.management.commands.webpush_keys import vapid_keys  # noqa: E402

TEMPLATE = """\
# Essai sur plusieurs appareils (`make reseau`) : jamais dans Git, jamais sur le serveur.
# À remplir : l'adresse choisie sur https://www.duckdns.org (ex. mwangaza-demo.duckdns.org) et le
# jeton affiché en haut de cette page (« token »), à ne montrer à personne.
MWANGAZA_DOMAIN=
DUCKDNS_TOKEN=
# La suite est remplie toute seule ; ne plus y toucher (les appareils abonnés aux notifications
# dépendent des clés Web Push). CADDY_TLS n'est lu que par docker-compose.yml : le certificat
# vient de DuckDNS (Caddyfile.reseau).
CADDY_TLS=duckdns
DJANGO_SECRET_KEY={secret}
POSTGRES_PASSWORD={password}
WEBPUSH_VAPID_PUBLIC_KEY={public}
WEBPUSH_VAPID_PRIVATE_KEY={private}
DJANGO_HSTS_SECONDS=0
GUNICORN_WORKERS=2
"""

# Écoles de `make demo` ; une école créée dans l'essai s'ouvre de la même façon : https://<code>.…
DEMO_SCHOOLS = ("itig", "volcans")


def read_env() -> dict[str, str]:
    values = {}
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def duckdns_name(domain: str) -> str:
    """`mwangaza-demo.duckdns.org` → `mwangaza-demo` (nom attendu par l'API de DuckDNS)."""
    match = re.fullmatch(r"([a-z0-9-]+)\.duckdns\.org", domain.lower())
    if not match:
        sys.exit(
            f"MWANGAZA_DOMAIN doit être une adresse DuckDNS (ex. mwangaza-demo.duckdns.org), "
            f"pas « {domain} »."
        )
    return match.group(1)


def settings() -> tuple[str, str]:
    """Adresse et jeton de `reseau.env`, ou arrêt avec ce qu'il reste à faire."""
    values = read_env()
    domain, token = values.get("MWANGAZA_DOMAIN", ""), values.get("DUCKDNS_TOKEN", "")
    if not domain or not token:
        sys.exit(
            "Remplis MWANGAZA_DOMAIN et DUCKDNS_TOKEN dans infra/reseau/reseau.env "
            "(A-FAIRE.md § 9 bis), puis relance make reseau."
        )
    duckdns_name(domain)
    return domain.lower(), token


def init() -> None:
    if not ENV_FILE.exists():
        public, private = vapid_keys()
        ENV_FILE.write_text(
            TEMPLATE.format(
                secret=secrets.token_urlsafe(50),
                password=secrets.token_urlsafe(24),
                public=public,
                private=private,
            )
        )
        ENV_FILE.chmod(0o600)
    settings()


def local_ip() -> str:
    """Adresse de la machine sur le réseau qui mène à internet (le partage de connexion)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("8.8.8.8", 53))  # aucun paquet envoyé : choisit seulement l'interface
        return probe.getsockname()[0]


def update_ip(ip: str | None = None) -> None:
    domain, token = settings()
    ip = ip or local_ip()
    query = urllib.parse.urlencode({"domains": duckdns_name(domain), "token": token, "ip": ip})
    with urllib.request.urlopen(f"https://www.duckdns.org/update?{query}", timeout=30) as answer:
        if answer.read().decode().strip() != "OK":
            sys.exit("DuckDNS a refusé la mise à jour : vérifie MWANGAZA_DOMAIN et DUCKDNS_TOKEN.")
    print(f"{domain} → {ip}")


def links(domain: str) -> list[tuple[str, str]]:
    schools = [
        (f"Gestion de l'école « {code} »", f"https://{code}.{domain}/app/") for code in DEMO_SCHOOLS
    ]
    return [
        *schools,
        ("Portail des parents", f"https://parents.{domain}/"),
        ("Console de la plateforme", f"https://admin.{domain}/"),
    ]


def qr_code(url: str) -> str:
    return segno.make_qr(url, error="m").svg_inline(scale=5, border=2)


def page(domain: str) -> str:
    cards = "\n".join(
        f"""<a class="card" href="{escape(url)}">{qr_code(url)}
<strong>{escape(title)}</strong><span>{escape(url)}</span></a>"""
        for title, url in links(domain)
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Essai sur plusieurs appareils</title>
<style>
:root {{ --ink:#1A2233; --surface:#F3F5F6; --card:#FFFFFF; --line:#DDE3E6; --lake:#0E5C6B;
  --lamp:#F2B632; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 24px 16px; background: var(--surface); color: var(--ink);
  font: 16px/1.5 system-ui, sans-serif; }}
main {{ max-width: 980px; margin: 0 auto; }}
h1 {{ margin: 0 0 4px; font-size: 1.5rem; border-left: 6px solid var(--lamp); padding-left: 12px; }}
p {{ margin: 0 0 20px; }}
.grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }}
.card {{ display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 16px;
  background: var(--card); border: 1px solid var(--line); border-radius: 12px; color: inherit;
  text-decoration: none; text-align: center; }}
.card svg {{ width: 100%; max-width: 200px; height: auto; }}
.card span {{ color: var(--lake); font-size: .875rem; word-break: break-all; }}
</style>
</head>
<body>
<main>
<h1>Essai sur plusieurs appareils</h1>
<p>Scanner un code avec l'appareil photo du téléphone, connecté au même réseau que cette machine.
iPhone : ouvrir dans Safari, puis Partager → « Sur l'écran d'accueil » pour installer l'application
(nécessaire pour les notifications).</p>
<div class="grid">
{cards}
</div>
</main>
</body>
</html>
"""


def write_page() -> None:
    domain, _ = settings()
    PAGE.parent.mkdir(exist_ok=True)
    PAGE.write_text(page(domain))


def print_links() -> None:
    domain, _ = settings()
    print(f"Prêt. Page d'accueil (QR codes) : https://www.{domain}/")
    for title, url in links(domain):
        print(f"  {title:<34} {url}")


if __name__ == "__main__":
    command, *args = sys.argv[1:] or ["?"]
    actions = {
        "init": init,
        "ip": lambda: update_ip(*args[:1]),
        "accueil": write_page,
        "adresses": print_links,
    }
    if command not in actions:
        sys.exit(__doc__)
    actions[command]()
