"""Écoles fictives de `make demo` (`docs/07-a-fournir.md` § 4).

L'ITIG n'est que l'école d'exemple : ce qui la décrit vient d'ici, jamais du code de l'application.
"""

from apps.schools.models import School

DEMO_SCHOOLS = {
    "itig": "ITIG Don Bosco Goma (démo)",
    "volcans": "Complexe scolaire Les Volcans (fictif)",
}


def create_demo_schools() -> dict[str, School]:
    schools = {}
    for code, name in DEMO_SCHOOLS.items():
        schools[code], _created = School.objects.update_or_create(
            code=code, defaults={"name": name, "status": School.Status.ACTIVE}
        )
    return schools
