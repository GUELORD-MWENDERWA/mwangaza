"""Catalogue des usages de l'IA (IA.1.1, `05` § 6.5) : chaque usage déclare son module hôte, la
permission exigée dans l'école, son modèle par défaut et la taille de l'entrée et de la réponse.
Un usage ne marche que si l'école a le module hôte et que la plateforme le lui a affecté. La
console peut changer le modèle et les limites d'un usage (`AiSettings.use_overrides`), jamais en
ajouter : une tâche qui crée un usage l'ajoute ici."""

from dataclasses import dataclass

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

DEFAULT_MODEL = "claude-opus-5-5"


@dataclass(frozen=True)
class AiUse:
    code: str
    label: Promise
    module: str  # module hôte de l'école (`accounts/modules.py`)
    permission: str  # droit de l'écran hôte, en plus de `ai.use`
    model: str = DEFAULT_MODEL
    max_input_tokens: int = 20_000
    max_output_tokens: int = 4_000


USES: dict[str, AiUse] = {
    use.code: use
    for use in (
        AiUse(
            "course_grid_from_pdf",
            _("Course grid from a report card"),
            "academics",
            "courses.configure",
            max_input_tokens=30_000,
        ),
        AiUse(
            "timetable_constraints",
            _("Timetable rules from sentences"),
            "timetable",
            "timetable.manage",
            max_input_tokens=6_000,
            max_output_tokens=3_000,
        ),
        AiUse(
            "timetable_review",
            _("Timetable analysis and proposals"),
            "timetable",
            "timetable.manage",
            max_input_tokens=20_000,
            max_output_tokens=4_000,
        ),
    )
}
