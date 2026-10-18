"""Captures du produit (`make captures-site`) : PNG de `apercu/captures/produit/` mis en WebP
pour le site public, dans `backend/apps/core/static/core/site/captures/` ; la Gestion en deux
largeurs (1 184 et 592 px), le Portail au téléphone (390 px). Lancé avec le Python du serveur
(Pillow)."""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "captures" / "produit"
TARGET = HERE.parents[1] / "backend" / "apps" / "core" / "static" / "core" / "site" / "captures"

TARGET.mkdir(parents=True, exist_ok=True)
for png in sorted(SOURCE.glob("*.png")):
    image = Image.open(png).convert("RGB")
    image.save(TARGET / f"{png.stem}.webp", quality=78, method=6)
    if not png.stem.endswith("-mobile"):
        half = image.resize((image.width // 2, image.height // 2), Image.Resampling.LANCZOS)
        half.save(TARGET / f"{png.stem}-592.webp", quality=78, method=6)
    size = (TARGET / f"{png.stem}.webp").stat().st_size // 1024
    print(f"{png.stem}: {image.width} x {image.height}, {size} Ko")
