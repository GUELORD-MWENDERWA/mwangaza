"""Adresse DuckDNS de l'essai sur plusieurs appareils du même réseau (`make reseau`) et, avec
`--serveur`, du serveur de démonstration en ligne (`make deploy`, 4.6.2).

    init      crée le fichier de valeurs (hors Git) avec des secrets neufs, puis vérifie qu'il est
              rempli : `infra/reseau/reseau.env`, ou `infra/serveur/serveur.env` avec `--serveur`
    ip [IP]   met dans DuckDNS l'adresse de la machine sur le réseau (après un changement de
              réseau) ; avec `--serveur`, l'adresse publique du serveur (fin de SERVEUR)
    accueil   écrit la page d'accueil : adresses et QR codes des applications
    adresses  affiche les adresses

Lancé depuis `backend/` par `uv run` : segno et la création des clés Web Push viennent du projet.
"""

import ipaddress
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
SERVEUR = "--serveur" in sys.argv
if SERVEUR:
    sys.argv.remove("--serveur")
ENV_FILE = HERE.parent / "serveur" / "serveur.env" if SERVEUR else HERE / "reseau.env"
PAGE = ENV_FILE.parent / "accueil" / "index.html"
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

TEMPLATE_SERVEUR = """\
# Serveur de démonstration en ligne (`make deploy`, 4.6.2) : jamais dans Git. Copié sur le serveur
# à chaque `make deploy`. En garder une copie en lieu sûr : sans DJANGO_SECRET_KEY, chacun devrait
# relier son application d'authentification ; sans les clés Web Push, réabonner chaque appareil.
# À remplir : l'accès SSH au serveur (ex. ubuntu@141.144.10.20), une autre adresse DuckDNS que
# celle de `make reseau` (ex. mwangaza-goma.duckdns.org) et le jeton de https://www.duckdns.org.
SERVEUR=
MWANGAZA_DOMAIN=
DUCKDNS_TOKEN=
# La suite est remplie toute seule. DJANGO_DEMO_PASSWORD : mot de passe des comptes fictifs
# (`make deploy-demo`), à donner seulement aux personnes à qui tu montres l'application.
CADDY_TLS=duckdns
ACCUEIL=./serveur/accueil
DJANGO_DEMO_PASSWORD={demo_password}
DJANGO_SECRET_KEY={secret}
POSTGRES_PASSWORD={password}
WEBPUSH_VAPID_PUBLIC_KEY={public}
WEBPUSH_VAPID_PRIVATE_KEY={private}
GUNICORN_WORKERS=3
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
    """Adresse et jeton du fichier de valeurs, ou arrêt avec ce qu'il reste à faire."""
    values = read_env()
    domain, token = values.get("MWANGAZA_DOMAIN", ""), values.get("DUCKDNS_TOKEN", "")
    required = ["SERVEUR"] if SERVEUR else []
    missing = [
        name for name in [*required, "MWANGAZA_DOMAIN", "DUCKDNS_TOKEN"] if not values.get(name)
    ]
    if missing:
        then = (
            "A-FAIRE.md § 9 ter, puis make deploy"
            if SERVEUR
            else "A-FAIRE.md § 9 bis, puis make reseau"
        )
        where = ENV_FILE.relative_to(HERE.parent.parent)
        sys.exit(f"Remplis {', '.join(missing)} dans {where} ({then}).")
    duckdns_name(domain)
    return domain.lower(), token


def server_ip() -> str:
    """`ubuntu@141.144.10.20` → `141.144.10.20` : l'adresse publique du serveur."""
    host = read_env()["SERVEUR"].rpartition("@")[2]
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        sys.exit(f"SERVEUR doit finir par l'adresse IP publique du serveur, pas « {host} ».")


def init() -> None:
    if not ENV_FILE.exists():
        public, private = vapid_keys()
        ENV_FILE.parent.mkdir(exist_ok=True)
        ENV_FILE.write_text(
            (TEMPLATE_SERVEUR if SERVEUR else TEMPLATE).format(
                secret=secrets.token_urlsafe(50),
                password=secrets.token_urlsafe(24),
                demo_password=secrets.token_urlsafe(9),
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
    ip = ip or (server_ip() if SERVEUR else local_ip())
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
<title>{TITLE}</title>
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
<h1>{TITLE}</h1>
<p>Scanner un code avec l'appareil photo du téléphone{WHERE}.
iPhone : ouvrir dans Safari, puis Partager → « Sur l'écran d'accueil » pour installer l'application
(nécessaire pour les notifications).</p>
<div class="grid">
{cards}
</div>
</main>
</body>
</html>
"""


TITLE = "Démonstration" if SERVEUR else "Essai sur plusieurs appareils"
WHERE = (
    ", depuis n'importe quel réseau" if SERVEUR else ", connecté au même réseau que cette machine"
)


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
