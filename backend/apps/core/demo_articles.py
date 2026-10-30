"""Actualités fictives du site (SITE.2, lot 2) : des articles longs sur des fonctions qui existent
vraiment, aucune école ni personne nommée, avec les photos libres de la photothèque (crédits :
`maquettes/assets/photos/README.md`). `make demo` les remet comme au départ."""

from datetime import timedelta
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image

from apps.core import site_content
from apps.core.models import Article, SitePhoto

PHOTO_DIR = Path(__file__).resolve().parent / "static/core/site/photos"
COMMONS = "https://commons.wikimedia.org/wiki/File:"

# clé = fichier de `static/core/site/photos/` ; (légende FR, EN, crédit, page source, licence)
DEMO_PHOTOS = {
    "eleves-rentree": (
        "Élèves en chemise blanche en classe",
        "Pupils in white shirts in class",
        "MONUSCO Photos",
        COMMONS + "Vive_la_rentr%C3%A9e_scolaire_!_(15155517546).jpg",
        "cc_by_sa",
    ),
    "classe-uniforme": (
        "Classe en uniforme bleu et blanc",
        "Class in blue and white uniforms",
        "Ken Wiegand (USAID)",
        COMMONS + "DRC_classroom.jpg",
        "public_domain",
    ),
    "eleves-kisangani": (
        "Élèves du secondaire en classe",
        "Secondary pupils in class",
        "BamLifa",
        COMMONS + "El%C3%A8vesDeCFMKisangani.jpg",
        "cc_by_sa",
    ),
    "cour-ecole-goma": (
        "Cour et bâtiments d'une école secondaire à Goma",
        "Yard and buildings of a secondary school in Goma",
        "Kaptainwiki",
        COMMONS + "Complexe_Scolaire_Mama_Mulezi_Secondaire_vue_de_la_cours.jpg",
        "cc0",
    ),
    "parent-telephone": (
        "Une mère au téléphone",
        "A mother on the phone",
        "Francish7",
        COMMONS + "Basankusu_woman_mobile_phone.jpg",
        "cc_by_sa",
    ),
    "directeur-ecole": (
        "Un directeur d'école à son bureau",
        "A school head at his desk",
        "Julien Harneis",
        COMMONS + "Le_Directeur_d%27Ecole.jpg",
        "cc_by_sa",
    ),
    "salle-de-classe": (
        "Salle de classe aux bancs en bois",
        "Classroom with wooden desks",
        "Sunway godianne",
        COMMONS + "Classe_du_coll%C3%A8ge_mwanga.jpg",
        "cc_by",
    ),
    "cour-interieure-ecole": (
        "Cour intérieure d'un complexe scolaire à étages",
        "Inner yard of a multi-storey school",
        "Juska Kanduvula",
        COMMONS + "C.SC._MANDELA.jpg",
        "cc0",
    ),
}

# (jours depuis la publication — négatif : programmé —, photo du haut, texte) ; `None` : brouillon.
# Dans le texte, `{photo:<clé>}` devient l'identifiant de la photo.
DEMO_ARTICLES = (
    (
        6,
        "cour-interieure-ecole",
        {
            "language": "fr",
            "title": "La caisse continue de fonctionner sans internet",
            "summary": "Coupure de réseau à l'heure des paiements : la caissière encaisse, "
            "imprime le reçu, et tout part au serveur au retour du réseau.",
            "body": "À Goma, le réseau tombe souvent au pire moment : le jour où les parents "
            "viennent payer en nombre. Une caisse qui s'arrête à ce moment-là, ce sont des files "
            "d'attente, des paiements notés sur un cahier et des erreurs à rattraper le soir.\n\n"
            "## Ce qui ne change pas pour la caissière\n"
            "Quand la connexion tombe, la caisse reste ouverte. La caissière fait exactement "
            "les mêmes gestes :\n"
            "- elle cherche l'élève, même sans réseau, parmi tous ceux de l'école ;\n"
            "- elle encaisse en francs ou en dollars, avec le taux de l'année ;\n"
            "- le reçu sort avec son **numéro définitif**, sans attendre le serveur ;\n"
            "- le solde de l'élève est à jour sur l'appareil.\n\n"
            "![Une cour d'école comme on en voit à Goma : le travail se fait là où l'on est]"
            "(photo:{cour-interieure-ecole})\n\n"
            "## Pas de doublon, pas de paiement perdu\n"
            "Chaque paiement porte un identifiant créé sur l'appareil. Quand le réseau revient, "
            "l'appareil envoie ses paiements, et le serveur reconnaît ceux qu'il a déjà reçus : "
            "un paiement n'est jamais compté deux fois, même si l'envoi est répété.\n\n"
            "## Ce que voit le comptable\n"
            "Au retour du réseau, tout apparaît dans la clôture de caisse, avec l'heure "
            "réelle de chaque encaissement. Un paiement ne se modifie pas : s'il y a une erreur, "
            "on l'annule avec un motif, et l'annulation reste visible.\n\n"
            "## À retenir\n"
            "Pour une école, la vraie question n'est pas « y a-t-il du réseau ? » mais « peut-on "
            "encaisser quand même ? ». Ici, la réponse est oui.",
        },
    ),
    (
        2,
        "parent-telephone",
        {
            "language": "fr",
            "title": "Les reçus arrivent sur le téléphone des parents",
            "summary": "Chaque paiement enregistré à la caisse apparaît dans l'espace des "
            "parents, avec son reçu et ce qui reste à payer.",
            "body": "Un parent ne devrait pas avoir à garder un petit papier pendant toute "
            "l'année pour prouver qu'il a payé. Avec l'espace des parents, le reçu le suit sur "
            "son téléphone.\n\n"
            "## Une inscription simple\n"
            "Le parent active son compte avec le **code famille** remis par l'école. Il n'a pas "
            "besoin d'un ordinateur : l'espace s'adapte au téléphone et reste léger, même avec "
            "une connexion lente.\n\n"
            "![Un parent consulte son téléphone]"
            "(photo:{parent-telephone})\n\n"
            "## Ce qu'il voit, pour chacun de ses enfants\n"
            "- les paiements et leurs reçus, à retrouver quand il veut ;\n"
            "- les échéances à venir et ce qu'il reste à payer ;\n"
            "- les annonces et les convocations de l'école ;\n"
            "- les bulletins, quand l'école les publie.\n\n"
            "## Ce que l'école garde la main sur\n"
            "Chaque parent ne voit que ses enfants. L'école décide de ce qu'elle publie et "
            "quand, et un parent ne peut rien modifier.\n\n"
            "Le détail est dans [la page des parents](/parents/).",
        },
    ),
    (
        -3,
        "eleves-rentree",
        {
            "language": "fr",
            "title": "Rappels d'échéance : l'école choisit quand prévenir",
            "summary": "Trois jours avant une tranche, puis en cas de retard : le parent reçoit "
            "un rappel sur son téléphone, si l'école l'active.",
            "body": "Beaucoup de retards de paiement ne sont pas des refus : ce sont des oublis. "
            "Un rappel envoyé au bon moment évite une conversation difficile au portail.\n\n"
            "## Réglé par chaque école\n"
            "Les rappels aux parents se règlent dans les paramètres de l'école : quand prévenir "
            "avant une tranche, et si l'on relance après la date. **Rien ne part sans son "
            "accord.**\n\n"
            "![Des élèves en classe, un jour de rentrée]"
            "(photo:{eleves-rentree})\n\n"
            "## Ce que dit le message\n"
            "- le nom de l'élève et la tranche concernée ;\n"
            "- le montant qui reste à payer ;\n"
            "- la date limite fixée par l'école.\n\n"
            "## Pour la direction\n"
            "La liste des impayés se lit en un coup d'œil, classe par classe, et le comptable "
            "sait qui a déjà été prévenu. Le but est simple : moins de relances à la main, et "
            "des parents qui ne sont jamais surpris.",
        },
    ),
    (
        9,
        "classe-uniforme",
        {
            "language": "fr",
            "title": "Du cahier de cotes au bulletin imprimé",
            "summary": "Les notes se saisissent classe par classe ; le bulletin se calcule et "
            "s'imprime sur le modèle exact de l'école, sans recopier une seule cote.",
            "body": "Pour un titulaire, la fin de période, ce sont des heures de recopie. Une "
            "cote mal reportée, et c'est un parent mécontent le jour de la remise des bulletins."
            "\n\n## Saisir une fois\n"
            "L'enseignant saisit ses notes pour chacune de ses classes, avec ou sans devoirs "
            "selon la façon de travailler de l'école. Les maxima de chaque cours sont ceux du "
            "programme ; une note ne peut pas dépasser son maximum.\n\n"
            "![Une classe en uniforme]"
            "(photo:{classe-uniforme})\n\n"
            "## Le bulletin se calcule seul\n"
            "- les totaux, les pourcentages et les places sont calculés par l'application ;\n"
            "- la conduite se note selon le barème de l'école ;\n"
            "- le règlement des études de l'école donne la décision proposée : réussite, "
            "examen de repêchage ou redoublement.\n\n"
            "## Imprimer comme l'école veut\n"
            "Le bulletin garde les mesures et la mise en page du formulaire que l'école utilise "
            "déjà. L'impression se fait au choix : une classe entière, ou un seul élève.\n\n"
            "Le titulaire relit, corrige s'il le faut, et signe. Il n'a plus qu'à remettre les "
            "bulletins.",
        },
    ),
    (
        14,
        "salle-de-classe",
        {
            "language": "fr",
            "title": "Un emploi du temps sans conflit de salle ni d'enseignant",
            "summary": "Un enseignant ne peut pas être dans deux classes à la fois : "
            "l'application le vérifie à votre place, et propose une première version.",
            "body": "L'emploi du temps est le casse-tête de chaque rentrée : des classes, des "
            "salles, des ateliers, et des enseignants qui n'ont pas les mêmes jours.\n\n"
            "## Ce que l'application vérifie\n"
            "- un enseignant n'est jamais placé dans deux classes à la même heure ;\n"
            "- une salle ou un atelier n'accueille qu'une classe à la fois ;\n"
            "- les jours et les heures où un enseignant n'est pas disponible sont respectés.\n\n"
            "![Une salle de classe, prête pour la rentrée]"
            "(photo:{salle-de-classe})\n\n"
            "## Une première version proposée\n"
            "L'application propose un premier emploi du temps à partir des cours de chaque "
            "classe et des disponibilités. Le préfet des études le corrige à la main, "
            "déplace un cours, et voit tout de suite si cela crée un conflit.\n\n"
            "## Chacun voit le sien\n"
            "Les enseignants consultent leur emploi du temps sur leur téléphone, et les "
            "parents celui de la classe de leur enfant. Une modification est visible partout "
            "dès qu'elle est enregistrée.",
        },
    ),
    (
        18,
        "directeur-ecole",
        {
            "language": "fr",
            "title": "La clôture de caisse : savoir ce qu'il y a dans le tiroir",
            "summary": "En fin de journée, le comptable compare l'argent compté à ce que dit "
            "l'application, devise par devise.",
            "body": "Une caisse d'école manipule du cash en francs et en dollars. Le soir, "
            "la seule question qui compte : **le tiroir correspond-il aux reçus ?**\n\n"
            "## Une clôture par caissier et par devise\n"
            "À la fin de la journée, le caissier compte l'argent et le saisit. L'application "
            "affiche ce qu'elle attend d'après les reçus émis, et l'écart éventuel apparaît "
            "tout de suite.\n\n"
            "![Le directeur à son bureau]"
            "(photo:{directeur-ecole})\n\n"
            "## Rien ne se modifie en cachette\n"
            "- un paiement enregistré ne se change jamais ;\n"
            "- une annulation est un nouvel enregistrement, avec son motif et son auteur ;\n"
            "- chaque clôture garde la date, l'heure et la personne.\n\n"
            "## Pour la direction\n"
            "Le promoteur et le préfet consultent les clôtures sans avoir à demander un état "
            "au comptable : l'information est la même pour tous, et à jour.",
        },
    ),
    (
        22,
        "cour-ecole-goma",
        {
            "language": "fr",
            "title": "Préparer la rentrée : inscriptions, frais et classes",
            "summary": "Les élèves de l'an dernier passent dans leur nouvelle classe en "
            "quelques clics, les frais de l'année sont prêts avant la première inscription.",
            "body": "La rentrée se prépare des semaines avant le premier jour de classe. Voici "
            "comment une école s'y prend avec l'application.\n\n"
            "## 1. Régler l'année\n"
            "L'école crée sa nouvelle année scolaire, ses classes et ses périodes, puis fixe "
            "les frais de chaque niveau : montant, devise, et tranches. Le taux de change de "
            "l'année est enregistré une fois.\n\n"
            "![La cour d'un lycée de Goma, avant l'arrivée des élèves]"
            "(photo:{cour-ecole-goma})\n\n"
            "## 2. Faire passer les élèves\n"
            "À partir des décisions de fin d'année, l'application propose le passage de classe "
            "de chaque élève. La direction vérifie, corrige les cas particuliers, puis "
            "confirme.\n\n"
            "## 3. Inscrire les nouveaux\n"
            "Les nouveaux élèves sont inscrits avec leur famille. Un frère ou une sœur déjà "
            "présent est retrouvé : la fratrie reste ensemble et la réduction prévue "
            "s'applique.\n\n"
            "## 4. Ouvrir la caisse\n"
            "Dès que les frais sont réglés, la caisse peut encaisser. Les parents voient ce "
            "qu'ils doivent sur leur téléphone, avec les dates des tranches.",
        },
    ),
    (
        None,
        None,
        {
            "language": "en",
            "title": "The cash desk keeps working without internet",
            "summary": "Network down at payment time: the cashier takes the payment, prints "
            "the receipt, and everything is sent when the network is back.",
            "body": "Payments are sent once each when the network comes back.",
        },
    ),
)


def create_demo_photos() -> dict[str, SitePhoto]:
    """La photothèque de démonstration (les photos libres du site), sans doublon."""
    made = {}
    for key, (alt_fr, alt_en, credit, source, licence) in DEMO_PHOTOS.items():
        photo = SitePhoto.objects.filter(source_url=source).first()
        if photo is None:
            large, small = PHOTO_DIR / f"{key}.webp", PHOTO_DIR / f"{key}-600.webp"
            with Image.open(large) as image:
                width, height = image.size
            photo = SitePhoto(
                width=width,
                height=height,
                alt_fr=alt_fr,
                alt_en=alt_en,
                credit=credit,
                source_url=source,
                license=licence,
            )
            photo.large.save(f"{photo.pk}-1600.webp", ContentFile(large.read_bytes()), save=False)
            photo.small.save(f"{photo.pk}-600.webp", ContentFile(small.read_bytes()), save=False)
            photo.save()
        made[key] = photo
    return made


def create_demo_articles() -> None:
    """Actualités fictives, remises comme au départ (celles de la console restent)."""
    photos = create_demo_photos()
    Article.objects.filter(title__in=[row["title"] for _d, _p, row in DEMO_ARTICLES]).delete()
    now = timezone.now().replace(minute=0, second=0, microsecond=0)
    for days, cover, fields in DEMO_ARTICLES:
        body = fields["body"]
        for key, photo in photos.items():
            body = body.replace("{" + key + "}", str(photo.pk))
        article = Article(
            author_name="", photo=photos[cover] if cover else None, **{**fields, "body": body}
        )
        if days is not None:
            article.status = Article.Status.PUBLISHED
            article.published_at = now - timedelta(days=days)
            article.slug = slugify(article.title)
        article.save()
    transaction.on_commit(site_content.clear)
