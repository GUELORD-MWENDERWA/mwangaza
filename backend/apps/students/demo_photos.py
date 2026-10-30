"""Photos de profil fictives des élèves de démonstration (captures du site public, `make
captures-site`) : des silhouettes dessinées, jamais le visage d'une vraie personne. Tirage fixe
par élève ; seuls quelques élèves en ont une, comme dans une école qui commence à les ajouter."""

import io
import random

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw

from apps.students.models import Student

SIZE = 256
BACKGROUNDS = ["#DCE6F7", "#E8EFD8", "#F6E6CF", "#E4DDF0", "#D9EEEA", "#F3DDD6"]
SKINS = ["#5B3A29", "#6F4630", "#835A3E", "#4A2F22", "#966B4B"]
HAIRS = ["#1A1411", "#221A15", "#2B211A"]
UNIFORMS = ["#2457B8", "#1F4E9E", "#2F6B4F", "#7A2E2E"]
# Nombre d'élèves qui ont une photo dans chaque espace de démonstration.
PHOTOS_PER_SPACE = 60


def avatar(seed: str) -> bytes:
    """Silhouette PNG de 256 px : épaules en uniforme, tête, cheveux courts ou coiffure."""
    rng = random.Random(seed)
    skin, hair = rng.choice(SKINS), rng.choice(HAIRS)
    image = Image.new("RGB", (SIZE * 2, SIZE * 2), rng.choice(BACKGROUNDS))
    draw = ImageDraw.Draw(image)
    s = 2  # dessiné deux fois plus grand, puis réduit : bords lissés
    draw.ellipse((40 * s, 168 * s, 216 * s, 330 * s), fill=rng.choice(UNIFORMS))
    draw.rectangle((108 * s, 148 * s, 148 * s, 190 * s), fill=skin)
    draw.ellipse((78 * s, 52 * s, 178 * s, 172 * s), fill=skin)
    if rng.random() < 0.5:
        draw.pieslice((74 * s, 44 * s, 182 * s, 124 * s), 180, 360, fill=hair)
    else:
        draw.ellipse((72 * s, 36 * s, 184 * s, 112 * s), fill=hair)
        draw.rectangle((78 * s, 82 * s, 178 * s, 100 * s), fill=skin)
    out = io.BytesIO()
    image.resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(out, "PNG", optimize=True)
    return out.getvalue()


def add_demo_photos(family_students: list[Student] | None = None) -> None:
    """Donne une photo (avec l'accord du parent) aux premiers élèves de l'école courante et aux
    enfants de la première famille (le parent de démonstration). Sans effet sur ceux qui en ont."""
    chosen = {s.pk: s for s in Student.objects.order_by("matricule")[:PHOTOS_PER_SPACE]}
    for student in family_students or []:
        chosen[student.pk] = student
    updated = []
    for student in chosen.values():
        if student.photo:
            continue
        student.photo.save(
            f"photo-{student.pk}.png", ContentFile(avatar(str(student.pk))), save=False
        )
        student.photo_consent = True
        updated.append(student)
    Student.objects.bulk_update(updated, ["photo", "photo_consent"])
