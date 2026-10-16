"""Étiquette des images de production (PERF.5c) : une image n'est reconstruite que si le code
qu'elle contient change, pas pour un document ou un script du serveur."""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / "infra" / "serveur" / "etiquette.sh"
CONTENU = (
    "backend/a.py",
    "frontend/a.ts",
    "infra/Dockerfile",
    "infra/Caddyfile",
    "infra/routes.caddy",
    "infra/production/Caddyfile",
    ".dockerignore",
)


def git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip


def commit(repo, fichier, texte):
    path = repo / fichier
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texte)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "x")
    return subprocess.run(
        ["bash", str(SCRIPT), "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()  # fmt: skip


def test_etiquette_suit_le_code_des_images_seulement(tmp_path):
    git(tmp_path, "init", "-q")
    for fichier in CONTENU:
        commit(tmp_path, fichier, "1")
    base = commit(tmp_path, "docs/notes.md", "document")
    assert len(base) == 12
    assert commit(tmp_path, "infra/serveur/deployer.sh", "script") == base
    assert commit(tmp_path, "backend/a.py", "2") != base
