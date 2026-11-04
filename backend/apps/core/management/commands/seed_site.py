"""Remplit les actualités du site public d'une plateforme neuve (`make deploy-site`) : les articles
d'exemple de `demo_articles.py` (fonctions qui existent vraiment, aucune école ni personne nommée,
photos libres de la photothèque). Ne fait rien si le site a déjà un article : jamais d'écrasement,
ni de ce que l'équipe a écrit dans la console, ni d'un second passage. Tout se modifie ensuite dans
la console (« Actualités »)."""

from django.core.management.base import BaseCommand

from apps.core.demo_articles import create_demo_articles
from apps.core.models import Article


class Command(BaseCommand):
    help = "Ajoute les actualités d'exemple au site si celui-ci n'en a aucune."

    def handle(self, *args, **options):
        if Article.objects.exists():
            self.stdout.write("Le site a déjà des actualités : rien n'est changé.")
            return
        create_demo_articles()
        self.stdout.write(
            f"{Article.objects.count()} actualités ajoutées (à relire dans la console)."
        )
