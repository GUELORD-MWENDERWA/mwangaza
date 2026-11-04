"""Captures de l'aide (`make captures-aide`) : PNG de `apercu/captures/aide/<langue>/` mis en WebP
dans `backend/apps/core/static/core/aide/<langue>/`. Lancé avec le Python du serveur (Pillow)."""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "captures" / "aide"
TARGET = HERE.parents[1] / "backend" / "apps" / "core" / "static" / "core" / "aide"

for png in sorted(SOURCE.glob("*/*.png")):
    target = TARGET / png.parent.name
    target.mkdir(parents=True, exist_ok=True)
    Image.open(png).convert("RGB").save(target / f"{png.stem}.webp", quality=78, method=6)
    print(f"{png.parent.name}/{png.stem}: {(target / f'{png.stem}.webp').stat().st_size // 1024} Ko")
