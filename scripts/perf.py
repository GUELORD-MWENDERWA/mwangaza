"""Mesure du temps des écrans lourds et de l'impression (PERF.4) : `make perf`.

À lancer sur `make prod-local` (mêmes images que le serveur) avec les données de `make demo` : N
utilisateurs de l'ITIG (promoteur, sans double authentification) font en même temps les mêmes
requêtes ; pour chaque point d'API, le temps médian et le plus long. Puis l'impression d'une classe,
du dépôt au PDF prêt. Rien que la bibliothèque standard ; le résultat s'écrit en tableau Markdown
(`--out`, par défaut dans `docs/claude/recherches/`)."""

import argparse
import http.cookiejar
import json
import ssl
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

PAGES = [
    ("Tableau de bord", "/api/dashboard/"),
    ("Impayés (1re page)", "/api/unpaid/"),
    ("Élèves (1re page)", "/api/students/"),
    ("Paiements (1re page)", "/api/payments/"),
    ("Classes", "/api/class-groups/"),
]
PRINT_TIMEOUT = 600


class Session:
    def __init__(self, base: str):
        self.base = base
        context = ssl.create_default_context()
        context.check_hostname, context.verify_mode = False, ssl.CERT_NONE  # certificat local
        jar = http.cookiejar.CookieJar()
        self.jar = jar
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar), urllib.request.HTTPSHandler(context=context)
        )

    def request(self, path: str, body: dict | None = None):
        headers = {"Referer": self.base + "/", "Accept": "application/json, application/pdf"}
        token = next((c.value for c in self.jar if c.name == "csrftoken"), None)
        if token:
            headers["X-CSRFToken"] = token
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        req = urllib.request.Request(self.base + path, data=data, headers=headers)
        with self.opener.open(req, timeout=PRINT_TIMEOUT) as response:
            return response.status, response.headers.get_content_type(), response.read()

    def login(self, phone: str, password: str) -> None:
        self.request("/api/auth/csrf/")
        self.request("/api/auth/login/", {"phone": phone, "password": password})


def timed(session: Session, path: str) -> float:
    start = time.perf_counter()
    session.request(path)
    return time.perf_counter() - start


def user_run(base: str, phone: str, password: str, rounds: int) -> dict[str, list[float]]:
    session = Session(base)
    session.login(phone, password)
    return {title: [timed(session, path) for _ in range(rounds)] for title, path in PAGES}


def print_class(base: str, phone: str, password: str) -> tuple[str, float]:
    session = Session(base)
    session.login(phone, password)
    classes = json.loads(session.request("/api/class-groups/")[2])
    classes = classes["results"] if isinstance(classes, dict) else classes
    biggest = max(classes, key=lambda c: c.get("student_count", 0))
    path = f"/api/class-groups/{biggest['id']}/report-card/?output=pdf"
    start = time.perf_counter()
    while time.perf_counter() - start < PRINT_TIMEOUT:
        try:
            _status, kind, _body = session.request(path)
        except urllib.error.HTTPError as error:
            if error.code != 409:
                raise
            # Notes pas encore validées (données de la démo) : lettres d'invitation de la classe,
            # un PDF lourd lui aussi (même file de tâches, même travailleur).
            path = f"/api/families/letters/?class_group={biggest['id']}&output=pdf"
            continue
        if kind == "application/pdf":
            return biggest.get("name", "?"), time.perf_counter() - start
        time.sleep(2)  # page d'attente : le travail est en cours
    raise TimeoutError(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="https://itig-demo.localhost")
    parser.add_argument("--users", type=int, default=5)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--phone", default="0000001007")
    # Les bulletins demandent un droit sur les notes : la directrice des études de la démo.
    parser.add_argument("--print-phone", default="0000001002")
    parser.add_argument("--password", default="mwangaza-demo")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    started = time.perf_counter()
    with ThreadPoolExecutor(args.users + 1) as pool:
        printing = pool.submit(print_class, args.base, args.print_phone, args.password)
        runs = list(
            pool.map(
                lambda _: user_run(args.base, args.phone, args.password, args.rounds),
                range(args.users),
            )
        )
        name, seconds = printing.result()
    lines = [
        f"# Mesure du {date.today():%Y-%m-%d} ({args.users} utilisateurs, {args.rounds} tours)",
        "",
        "| Écran | Médiane (s) | Plus long (s) |",
        "|---|---|---|",
    ]
    for title, _path in PAGES:
        times = [t for run in runs for t in run[title]]
        lines.append(f"| {title} | {statistics.median(times):.2f} | {max(times):.2f} |")
    lines += ["", f"Impression de la classe « {name} » (pendant ces requêtes) : {seconds:.0f} s.", ""]
    lines.append(f"Durée totale de la mesure : {time.perf_counter() - started:.0f} s.")
    report = "\n".join(lines)
    print(report)
    out = args.out or f"docs/claude/recherches/perf-mesure-{date.today():%Y-%m-%d}.md"
    Path(out).write_text(report + "\n")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as error:
        raise SystemExit(f"Serveur injoignable ({error}). `make prod-local` puis `make demo` ?")
