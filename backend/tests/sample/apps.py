from django.apps import AppConfig


class SampleConfig(AppConfig):
    """Modèles d'école réservés aux tests du socle multi-écoles (jamais installés hors tests)."""

    name = "tests.sample"
    label = "sample"
