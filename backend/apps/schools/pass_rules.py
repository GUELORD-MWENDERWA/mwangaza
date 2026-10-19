"""Règles de délibération de l'école (`School.settings["pass_rules"]`, 8.4.1 puis NB.4) : le
règlement des études qui donne la décision proposée (passe, repêchage, double, orienté, exclu).
Pas de règle nationale : chaque école choisit un préréglage puis le corrige, et chaque niveau peut
remplacer un champ (`Level.pass_rules`). Jamais dans le code d'une école.

Sources des préréglages : `docs/claude/recherches/2026-10-18-notes-deliberation-rdc.md`.
"""

COMMON, CATHOLIC = "common", "catholic"
# « Courant » (Institut Lukanga, Kinshasa) : préréglage par défaut d'une école neuve (Q15).
DEFAULTS = {
    # Passe : total de l'année et chaque cours au moins à ce pourcentage.
    "pass_percent": 50,
    "course_pass_percent": 50,
    # Repêchage : échecs partiels avec le total au moins à ce pourcentage.
    "resit_percent": 50,
    "max_resit_courses": 4,
    # Cours principaux (catégorie `main`, ex. mathématiques et français) et branches d'option
    # repêchés ensemble au plus ; un cours pratique (atelier) ouvre-t-il un repêchage ?
    "max_main_resits": 1,
    "max_option_resits": 4,
    "practical_resit": False,
    # Entrer dans la dernière classe (celle de l'Examen d'État) : ce total et aucun cours échoué
    # (0 : règles ordinaires).
    "final_pass_percent": 0,
    # Sous ce pourcentage, la classe ne peut pas être reprise : orientation ailleurs (0 : jamais).
    "orientation_percent": 40,
    # Exception d'âge : un élève qui aura, à la rentrée suivante, au moins N ans de moins que l'âge
    # limite de son niveau (`age_limit`, réglé par niveau, 0 : aucun) et au moins ce pourcentage
    # double au lieu d'être orienté ou exclu (0 an : jamais).
    "age_exception_years": 0,
    "age_exception_percent": 40,
    "age_limit": 0,
    # Exclusion : l'élève a déjà fait ce niveau (tripler), ou a déjà doublé N fois (0 : sans
    # limite).
    "exclude_repeated_class": True,
    "max_repeats": 0,
    # Exclusion : conduite notée MA, ou ME ou moins, autant de périodes de suite (0 : jamais) ;
    # l'application aussi, comptée à part, si `application_counts`.
    "conduct_ma_to_exclude": 2,
    "conduct_me_to_exclude": 3,
    "application_counts": False,
    # Seconde session : cours perdus au repêchage qui font doubler.
    "resit_failures_to_fail": 2,
}
FIELDS = tuple(DEFAULTS)
PRESETS = {
    COMMON: DEFAULTS,
    # « Réseau catholique » (critères du Collège technique Mwapusukeni, relus le 2026-10-19).
    CATHOLIC: {
        **DEFAULTS,
        "resit_percent": 53,
        "max_option_resits": 2,
        "final_pass_percent": 55,
        "orientation_percent": 50,
        "age_exception_years": 1,
        "max_repeats": 2,
        "application_counts": True,
    },
}


def _known(rules: dict | None) -> dict:
    """Seulement les champs d'aujourd'hui : un ancien réglage (`resit_mode`…) est oublié."""
    return {name: value for name, value in (rules or {}).items() if name in DEFAULTS}


def pass_rules_settings(settings: dict) -> dict:
    """Règles d'après `School.settings`, valeurs par défaut comprises."""
    return {**DEFAULTS, **_known((settings or {}).get("pass_rules"))}


def class_rules(settings: dict, level_rules: dict | None) -> dict:
    """Règles d'une classe : celles de l'école, que le niveau de la classe (7e, 3e…) peut
    remplacer champ par champ (`Level.pass_rules`, vide : celles de l'école)."""
    return {**pass_rules_settings(settings), **_known(level_rules)}


def merged(current: dict, changed: dict) -> dict:
    """Règles enregistrées après une écriture partielle, sans les anciens champs."""
    return _known({**current, **changed})


def journal_fields(settings: dict) -> dict:
    """Règles à plat pour le journal de l'école (`pass_rules_resit_percent`…)."""
    return {f"pass_rules_{name}": value for name, value in pass_rules_settings(settings).items()}
