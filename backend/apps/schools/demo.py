"""Écoles fictives de `make demo` (`docs/07-a-fournir.md` § 4).

L'ITIG n'est que l'école d'exemple : ce qui la décrit vient d'ici, jamais du code de l'application.
"""

from datetime import timedelta

from django.conf import settings
from django.core.files import File
from django.utils import timezone

from apps.schools.models import School

# Logo public de l'ITIG (site web), recadré : `docs/ecole-pilote/fiche-itig.md`.
ITIG_LOGO = settings.BASE_DIR.parent / "docs/ecole-pilote/documents/2026-09-25-logo-itig-carre.png"
DEMO_LOGOS = {"itig": ITIG_LOGO}


def _demo_schools() -> dict[str, dict]:
    today = timezone.localdate()
    return {
        "itig": {
            "name": "ITIG Don Bosco Goma (démo)",
            "official_name": "Institut Technique Industriel de Goma — ITIG Don Bosco (démo)",
            # Décision Q8 : couleur de l'ITIG de démonstration.
            "primary_color": "#003C6C",
            "status": School.Status.TRIAL,
            "plan": "Essai",
            "trial_ends_on": today + timedelta(days=90),
            "paid_until": None,
        },
        "volcans": {
            "name": "Complexe scolaire Les Volcans (fictif)",
            "official_name": "Complexe scolaire Les Volcans (fictif)",
            "primary_color": "#7A3E00",
            "status": School.Status.ACTIVE,
            "plan": "Standard",
            "trial_ends_on": None,
            "paid_until": today + timedelta(days=60),
        },
    }


def create_demo_schools() -> dict[str, School]:
    """Crée les écoles, ou les remet comme au départ (nom, couleur, abonnement, pas suspendues,
    logo de démonstration)."""
    schools = {}
    for code, fields in _demo_schools().items():
        existing = School.objects.filter(code=code).first()
        if existing is not None and existing.logo:
            existing.logo.delete(save=False)
        school, _created = School.objects.update_or_create(
            code=code, defaults={**fields, "logo": ""}
        )
        logo = DEMO_LOGOS.get(code)
        if logo is not None and logo.exists():
            with logo.open("rb") as file:
                school.logo.save(logo.name, File(file))
        schools[code] = school
    return schools
