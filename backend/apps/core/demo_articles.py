"""Actualités fictives du site (SITE.2, lot 2) : des articles longs sur des fonctions qui existent
vraiment, aucune école ni personne nommée, avec des photos récentes et libres de la photothèque
(2021 à 2026 ; crédits : `maquettes/assets/photos/README.md`). `make demo` les remet comme au
départ et retire les anciennes photos (`RETIRED_SOURCES`)."""

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

# Anciennes photos de démonstration (2007 à 2014), retirées de la photothèque : l'adresse de leur
# page source, comme les gardait `SitePhoto.source_url`.
RETIRED_SOURCES = (
    COMMONS + "Vive_la_rentr%C3%A9e_scolaire_!_(15155517546).jpg",
    COMMONS + "DRC_classroom.jpg",
    COMMONS + "El%C3%A8vesDeCFMKisangani.jpg",
    COMMONS + "Basankusu_woman_mobile_phone.jpg",
    COMMONS + "Le_Directeur_d%27Ecole.jpg",
)

# clé = fichier de `static/core/site/photos/` ; (légende FR, EN, crédit, page source, licence)
DEMO_PHOTOS = {
    "eleves-anis": (
        "Élèves en chemise blanche, à leurs bancs, à Lubumbashi",
        "Pupils in white shirts at their desks, in Lubumbashi",
        "Bahá'í Media Bank",
        COMMONS + "Students_at_Anis_School-_a_Baha%27i-inspired_School_in_Lubumbashi-DRC.jpg",
        "cc_by_sa",
    ),
    "classe-bleue": (
        "Une classe de lycée en uniforme bleu",
        "A secondary class in blue uniforms",
        "Destijes",
        COMMONS + "Les_sentinelles_au_lyc%C3%A9e_LVA_04.jpg",
        "cc0",
    ),
    "classe-tableau": (
        "Une salle de classe, élèves en bleu face au tableau",
        "A classroom, pupils in blue facing the blackboard",
        "Destijes",
        COMMONS + "Les_sentinelles_au_lyc%C3%A9e_LVA_02.jpg",
        "cc0",
    ),
    "ecole-bleue": (
        "Bâtiment bleu d'une école secondaire",
        "Blue building of a secondary school",
        "Tuyishimejosue",
        COMMONS + "Secondary_school.jpg",
        "cc0",
    ),
    "classe-ordinateurs": (
        "Élèves en bleu devant leurs ordinateurs, dans une salle intelligente",
        "Pupils in blue at their laptops in a smart classroom",
        "Joachim Hauschopp",
        COMMONS + "Juru_Secondary_School_Smart_Classroom.jpg",
        "cc0",
    ),
    "recreation": (
        "Récréation dans la cour d'une école",
        "Break time in a school yard",
        "SERGE MBULA",
        COMMONS + "%C3%89cole_elikya.jpg",
        "cc_by_sa",
    ),
    "ecole-muja": (
        "Salles de classe d'une école secondaire de Goma",
        "Classrooms of a secondary school in Goma",
        "Guillain Punzu",
        COMMONS + "Ecole_secondaire_Muja_Goma.jpg",
        "cc0",
    ),
    "cour-ecole-goma": (
        "Cour et bâtiments d'une école secondaire à Goma",
        "Yard and buildings of a secondary school in Goma",
        "Kaptainwiki",
        COMMONS + "Complexe_Scolaire_Mama_Mulezi_Secondaire_vue_de_la_cours.jpg",
        "cc0",
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
        "ecole-bleue",
        {
            "language": "fr",
            "title": "La caisse continue de fonctionner sans internet",
            "summary": "Coupure de réseau à l'heure des paiements : la caissière encaisse, "
            "imprime le reçu, et tout part au serveur au retour du réseau.",
            "body": """À Goma, comme dans beaucoup de villes de l'Est, le réseau tombe souvent au pire moment : le jour où les parents viennent payer en nombre, la veille des examens, ou le dernier jour avant l'échéance d'une tranche. Une caisse qui s'arrête à cet instant, ce sont des files d'attente qui s'allongent, des paiements notés sur un cahier « pour plus tard » et des erreurs qu'il faudra rattraper le soir, en refaisant les comptes à la main.

Une école ne peut pas attendre que le réseau revienne pour encaisser. C'est pourquoi la caisse de l'application a été pensée **d'abord pour fonctionner sans internet**, et non comme une option qu'on active en cas de problème.

## Ce qui ne change pas pour la caissière

Quand la connexion tombe, la caisse reste ouverte, sans message d'erreur ni écran bloqué. La caissière fait exactement les mêmes gestes que d'habitude :

- elle cherche l'élève par son nom, son matricule ou sa classe, même sans réseau, parmi tous les élèves de l'école ;
- elle voit ce que l'élève doit encore : les tranches échues, celles à venir, et les réductions déjà accordées ;
- elle encaisse en francs congolais ou en dollars, avec le taux de change fixé par l'école pour l'année ;
- le reçu sort avec son **numéro définitif**, sans attendre le serveur ;
- le solde de l'élève est mis à jour tout de suite sur l'appareil.

Un petit indicateur discret dit simplement si l'appareil est en ligne ou non, et combien de paiements attendent d'être envoyés. Il n'y a rien à faire de plus.

![La cour d'un complexe scolaire : l'école travaille là où elle est, avec ou sans réseau](photo:{cour-interieure-ecole})

## Comment le numéro de reçu reste unique

C'est la question que pose tout comptable : si deux caisses encaissent en même temps sans se parler, comment éviter deux reçus avec le même numéro ? Chaque appareil reçoit de l'école son propre préfixe. Le numéro d'un reçu est fait de ce préfixe et d'un compteur propre à l'appareil : deux appareils ne peuvent donc jamais produire le même numéro, même s'ils ne se sont jamais connectés l'un à l'autre.

Sur le papier, le reçu a la même apparence qu'un reçu émis en ligne : l'en-tête de l'école, le nom de l'élève, le montant, la devise, le taux utilisé, la tranche payée, le nouveau solde, le nom du caissier. Le parent repart avec un document complet, et la différence se voit seulement dans le journal de l'application.

## Pas de doublon, pas de paiement perdu

Chaque paiement porte un identifiant unique créé sur l'appareil au moment où le caissier valide. Quand le réseau revient, l'appareil envoie ses paiements au serveur, un par un. Le serveur reconnaît ceux qu'il a déjà reçus : **un paiement n'est jamais compté deux fois**, même si l'envoi est interrompu puis repris, même si le téléphone se met en veille au milieu.

Si l'appareil est éteint avant que le réseau ne revienne, rien n'est perdu : les paiements sont gardés dans la mémoire du navigateur, comme des brouillons, et partiront au prochain démarrage connecté. L'application demande d'ailleurs au navigateur de ne pas effacer ces données, pour qu'elles survivent même quand le téléphone manque de place.

## Ce que voit le comptable

Au retour du réseau, tout apparaît dans la clôture de caisse, avec **l'heure réelle** de chaque encaissement, et non l'heure de l'envoi. Le comptable voit sur quel appareil et par quel caissier chaque paiement a été saisi, et peut comparer l'argent compté dans le tiroir avec ce que dit l'application, devise par devise.

Un paiement ne se modifie jamais. S'il y a une erreur de saisie, on **l'annule avec un motif** : l'annulation est un nouvel enregistrement, lié au premier, avec le nom de la personne qui l'a faite. Rien ne disparaît, rien n'est récrit en cachette, et le journal garde toute l'histoire.

## Quelques conseils pour les écoles

- **Ouvrez la caisse une fois en ligne**, le matin, avant que les parents n'arrivent : l'appareil télécharge alors la liste des élèves et des soldes, qui servira toute la journée.
- Gardez au moins **deux appareils** à la caisse les jours de forte affluence : si l'un tombe en panne, l'autre continue, et chacun a son propre préfixe de reçu.
- Branchez les appareils sur secteur ou sur une batterie externe : le réseau n'est pas le seul fournisseur qui manque dans une journée de rentrée.
- Faites la **clôture de caisse le soir**, même si une partie des paiements est encore en attente d'envoi : elle se complète d'elle-même quand tout arrive.

## À retenir

Pour une école, la vraie question n'est pas « y a-t-il du réseau ? » mais « peut-on encaisser quand même ? ». Avec cette caisse, la réponse est oui : le parent repart avec son reçu, le caissier garde sa file sous contrôle, et le comptable retrouve ses comptes justes le lendemain matin.""",
        },
    ),
    (
        2,
        "classe-tableau",
        {
            "language": "fr",
            "title": "Les reçus arrivent sur le téléphone des parents",
            "summary": "Chaque paiement enregistré à la caisse apparaît dans l'espace des "
            "parents, avec son reçu et ce qui reste à payer.",
            "body": """Un parent ne devrait pas avoir à garder un petit papier pendant toute l'année pour prouver qu'il a payé. Les reçus se perdent, se mouillent, s'effacent au soleil, et la discussion recommence au guichet au moment le moins opportun. Avec l'espace des parents, le reçu suit la famille sur son téléphone.

Cet espace est pensé pour les téléphones qu'on trouve vraiment dans les familles : pas besoin d'un ordinateur, pas de grosse application à télécharger, et un affichage qui reste léger même avec une connexion lente.

## Une inscription simple

L'école remet à chaque famille un **code famille**. Le parent ouvre l'espace des parents, saisit le code et son numéro de téléphone, et son compte est activé. Pas de formulaire interminable, pas d'adresse e-mail obligatoire : la plupart des parents n'en ont pas.

Une famille qui a plusieurs enfants dans la même école les retrouve tous sous le même compte. Si un autre enfant est inscrit dans une deuxième école qui utilise aussi l'application, le parent peut l'ajouter avec le code de cette école : chaque école garde ses données, et le parent n'a qu'un seul endroit où regarder.

![Des élèves à leurs bancs : pour le parent, tout ce qui touche à l'école de son enfant tient dans un seul espace](photo:{eleves-anis})

## Ce qu'il voit, pour chacun de ses enfants

- les paiements déjà faits et **leurs reçus**, à retrouver quand il veut, sans rien demander au secrétariat ;
- les **échéances** à venir, les montants et ce qu'il reste à payer pour la période en cours ;
- les annonces de l'école, les circulaires et les convocations, avec leur date ;
- le calendrier de l'école : vacances, examens, réunions de parents ;
- les bulletins, dès que l'école décide de les publier ;
- l'emploi du temps de la classe de son enfant.

Tout est classé par enfant : un parent qui a trois enfants dans trois classes différentes n'a pas à fouiller dans une longue liste mélangée.

## Un reçu qui vaut preuve

Le reçu affiché dans l'espace des parents est **le même** que celui remis à la caisse : même numéro, même montant, même devise, même taux de change. Il peut être présenté à l'école ou vérifié par elle : chaque reçu porte un numéro qui permet à la caisse de retrouver le paiement en quelques secondes.

Un parent qui paie en dollars voit le montant en dollars, et un parent qui paie en francs voit le montant en francs. L'application n'invente jamais un montant converti : elle montre ce qui a été réellement versé, et le taux utilisé ce jour-là.

## Ce que l'école garde sous son contrôle

Chaque parent ne voit **que ses propres enfants**, jamais ceux d'une autre famille, et jamais ceux d'une autre école. L'école décide de ce qu'elle publie et quand : un bulletin n'apparaît que lorsqu'elle l'a publié, et elle peut le retenir tant que les frais ne sont pas réglés, selon sa propre règle.

Un parent ne peut rien modifier lui-même : ni un montant, ni un reçu, ni une note. S'il constate une erreur, il écrit à l'école depuis l'espace des parents, et la direction répond ; si ses coordonnées ont changé, il les envoie, et l'école les applique après vérification.

## Quand le parent n'a pas de téléphone à lui

Dans beaucoup de familles, un seul téléphone sert à tout le monde. L'espace des parents n'exige pas un appareil par personne : le parent peut ouvrir son compte sur le téléphone d'un voisin ou d'un proche, puis se déconnecter. Rien n'est gardé sur l'appareil après la déconnexion.

## Pour le secrétariat et la caisse

Moins de demandes de duplicata, moins de contestations, moins de « j'ai payé mais je n'ai plus mon reçu ». Le secrétariat consacre ce temps gagné à ce qui compte vraiment : accueillir les familles et tenir à jour les dossiers.

Le détail de l'espace des parents est présenté dans [la page des parents](/parents/).""",
        },
    ),
    (
        -3,
        "recreation",
        {
            "language": "fr",
            "title": "Rappels d'échéance : l'école choisit quand prévenir",
            "summary": "Trois jours avant une tranche, puis en cas de retard : le parent reçoit "
            "un rappel sur son téléphone, si l'école l'active.",
            "body": """Beaucoup de retards de paiement ne sont pas des refus : ce sont des oublis. Un parent qui travaille toute la semaine, qui change de téléphone, ou qui pense avoir encore quelques jours devant lui, dépasse la date sans le vouloir. Un rappel envoyé au bon moment évite alors une conversation difficile à la porte de l'école, et épargne au parent la honte d'un enfant renvoyé en classe.

Du côté de l'école, relancer à la main demande du temps : sortir la liste, appeler, noter qui a été joint. C'est un travail ingrat, que personne n'aime faire, et qu'on finit par repousser.

## Réglé par chaque école, jamais imposé

Les rappels aux parents se règlent dans les paramètres de l'école. La direction choisit :

- **combien de jours avant** une tranche on prévient les parents (trois jours, une semaine, ou pas du tout) ;
- si l'on **relance après la date**, et au bout de combien de jours ;
- sur quel canal : dans l'espace des parents, et sur le téléphone du parent s'il a activé les notifications.

**Rien ne part sans l'accord de l'école.** Une école qui préfère relancer elle-même, ou qui juge qu'un rappel automatique ne convient pas à ses familles, laisse simplement l'option éteinte, et le reste de l'application fonctionne exactement de la même manière.

![La cour d'une école avant la sonnerie : le bon moment pour penser à la prochaine tranche](photo:{cour-ecole-goma})

## Ce que dit le message

Le message est court, poli, et sans reproche. Il contient seulement ce qu'un parent a besoin de savoir :

- le **nom de l'élève** et la tranche concernée ;
- le **montant qui reste à payer**, dans la devise de la tranche ;
- la **date limite** fixée par l'école ;
- le moyen de retrouver les reçus déjà obtenus.


## Un message vérifié au moment de l'envoi

Un parent qui a déjà payé entre-temps ne reçoit pas de rappel : l'application vérifie le solde **au moment de l'envoi**, et non la veille. Elle ne donne jamais le détail des autres familles, ni ce que doit l'école dans son ensemble : chaque parent ne voit que ses propres enfants.

## Pour la direction et le comptable

La liste des impayés se lit en un coup d'œil, **classe par classe**, avec le montant dû et la date de la tranche. Le comptable sait qui a déjà été prévenu, quand, et quelle a été la réponse : un parent qui a payé, un parent qui a promis, un parent qu'on n'a pas pu joindre.

Cette liste sert aussi à décider, en connaissance de cause : accorder un délai, proposer un échéancier particulier à une famille en difficulté, ou accorder une réduction. Chaque décision laisse une trace dans le journal, avec le nom de la personne qui l'a prise.

## Un rappel n'est pas une sanction

Une bonne politique de rappels commence par le ton. Les écoles qui obtiennent les meilleurs résultats sont celles qui préviennent **avant** la date, de façon régulière et prévisible, et qui réservent la relance après la date aux familles qui n'ont pas répondu. Le but est simple : moins de relances à la main, moins de tension au guichet, et des parents qui ne sont jamais surpris par une échéance qu'ils auraient voulu respecter.""",
        },
    ),
    (
        9,
        "classe-bleue",
        {
            "language": "fr",
            "title": "Du cahier de cotes au bulletin imprimé",
            "summary": "Les notes se saisissent classe par classe ; le bulletin se calcule et "
            "s'imprime sur le modèle exact de l'école, sans recopier une seule cote.",
            "body": """Pour un titulaire, la fin de période, ce sont des heures de recopie : reporter les cotes de chaque cours dans le bulletin, additionner, calculer les pourcentages, établir les places, vérifier une deuxième fois. Une cote mal reportée, et c'est un parent mécontent le jour de la remise des bulletins, ou pire, une décision de fin d'année contestée.

L'application supprime la recopie. Les notes sont saisies **une seule fois**, à l'endroit où elles naissent, et tout le reste en découle.

## Saisir une fois, au bon endroit

Chaque enseignant voit ses classes et ses cours, et saisit ses notes directement. L'école choisit sa façon de travailler : avec le détail des devoirs et des interrogations, ou en saisissant seulement le total de la période et l'examen. Les deux méthodes existent, et c'est la direction qui décide.

Les **maxima** de chaque cours sont ceux du programme, réglés une fois pour toutes par l'école : une note ne peut pas dépasser son maximum, et l'application refuse la saisie d'une cote impossible. Un enseignant qui tape 18 sur 10 le voit tout de suite, au lieu de le découvrir à la remise des bulletins.

![Une salle de classe : chaque élève a ses cotes, saisies une seule fois par l'enseignant du cours](photo:{classe-tableau})

## Un suivi pour la direction

Le préfet des études ou le directeur des études voit, classe par classe et cours par cours, **quelles notes sont saisies et lesquelles manquent**. Plus besoin de passer de salle en salle pour savoir si le professeur de chimie a rendu ses cotes : l'écran le dit, avec le nom de l'enseignant et la date de la dernière saisie.

Quand une note est modifiée après coup, **la modification est tracée** : l'ancienne valeur, la nouvelle, la date et la personne. Rien n'est effacé en silence.

## Le bulletin se calcule seul

Une fois les notes saisies, l'application calcule :

- les **totaux** de chaque période et de l'année, cours par cours et au général ;
- les **pourcentages**, avec l'arrondi que l'école a choisi ;
- les **places** dans la classe, avec la règle des ex æquo ;
- la **conduite**, notée selon le barème de l'école, et non selon un barème imposé ;
- la **décision proposée** : réussite, examen de repêchage ou redoublement, selon le règlement des études de l'école.

Le règlement des études est un réglage de l'école : seuils de réussite, nombre de cours échoués toléré, règles propres à chaque niveau. L'application applique cette règle partout de la même façon et **propose** une décision. C'est le conseil de classe qui décide, et qui peut corriger.

## Imprimer comme l'école imprime

Le bulletin garde **les mesures, la police et la mise en page** du formulaire que l'école utilise déjà : en-tête avec le logo et les lignes centrées, tableau des cours, cases pour chaque période, signatures. Une école technique qui a des cours pratiques d'atelier les voit apparaître dans leur section, comme sur son formulaire papier.

L'impression se fait **au choix** : une classe entière d'un coup, un seul élève, ou une sélection. Chaque bulletin porte un numéro de référence, et le PDF est généré sur le serveur, pour qu'il sorte identique quel que soit l'appareil qui le demande.

## La fiche de cotes de chaque classe

Pour les classes où l'école veut garder une fiche papier, l'application imprime aussi la **fiche de cotes** : la grille de la classe avec tous les cours et toutes les périodes, à signer par le titulaire. Elle sert d'archive, et de preuve en cas de contestation.

## Les bulletins arrivent chez les parents

Quand l'école publie les bulletins, chaque parent peut les consulter dans son espace, avec la décision de la période. L'école peut aussi décider de **retenir** un bulletin tant que les frais échus ne sont pas réglés : c'est sa politique, et elle s'applique d'elle-même, sans qu'une secrétaire ait à surveiller la liste.

## Ce que le titulaire gagne

Le titulaire relit, corrige s'il le faut, ajoute son appréciation et signe. Il n'a plus qu'à remettre les bulletins. Les jours de recopie deviennent une relecture d'une heure, et la qualité des bulletins ne dépend plus de la fatigue de la veille.""",
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
            "body": """L'emploi du temps est le casse-tête de chaque rentrée : des classes, des salles, des ateliers, et des enseignants qui n'ont pas les mêmes jours ni les mêmes heures. Dans un institut technique, il faut en plus réserver des ateliers pour de longues séances pratiques, et s'assurer qu'une classe n'a pas deux heures d'atelier séparées par une demi-heure de théorie.

On le fait souvent à la main, avec une grande feuille, des gommes et beaucoup de patience, pendant des jours. Et il suffit d'un déplacement tardif pour tout défaire.

## Ce que l'application vérifie

Avant tout, l'application **empêche les conflits** :

- un enseignant n'est jamais placé dans deux classes à la même heure ;
- une salle ou un atelier n'accueille qu'une classe à la fois ;
- les jours et les heures où un enseignant n'est pas disponible sont respectés ;
- une classe n'a pas plus d'heures que sa grille horaire n'en prévoit, et chaque cours reçoit le nombre d'heures du programme.

Ces vérifications se font **en continu** : dès qu'on déplace un cours, l'application dit si le déplacement crée un conflit, et lequel.

![Un bâtiment de classes : un emploi du temps, c'est d'abord une salle à un moment donné](photo:{ecole-bleue})

## Ce qu'il faut renseigner une fois

Pour proposer un emploi du temps, l'application a besoin de quelques informations qu'elle réutilise ensuite chaque année :

- la **grille horaire** de l'école : les jours de classe, les heures de début et de fin, les récréations ;
- les **salles** et les **ateliers**, avec leur capacité et leur type ;
- les **cours** de chaque classe et leur nombre d'heures par semaine ;
- les **charges** des enseignants : quels cours, dans quelles classes ;
- les **disponibilités** : un enseignant qui n'enseigne que lundi, mardi et jeudi, ou qui a un autre établissement le mercredi.

Rien de tout cela n'est imposé : chaque école règle sa propre grille et ses propres règles.

## Les ateliers en longs blocs

Dans un institut technique, un atelier de mécanique ou d'électricité ne se découpe pas en séances d'une heure : il faut trois ou quatre heures d'affilée. L'application sait placer les cours pratiques en **longs blocs**, dans un atelier réservé à cet usage, et empêche qu'on les coupe en morceaux inutilisables.

Le préfet des études peut aussi **verrouiller** un cours à une place précise : un atelier le lundi matin, par exemple, parce que l'atelier est partagé avec une autre classe. L'application organise tout le reste autour.

## Une première version proposée

À partir des cours de chaque classe, des charges et des disponibilités, l'application **calcule un premier emploi du temps** complet. Ce n'est qu'une proposition : le préfet des études la parcourt, déplace un cours, échange deux enseignants, et voit tout de suite si cela crée un conflit.

On peut calculer plusieurs versions, les comparer et ne **publier** que celle qui convient. Tant qu'elle n'est pas publiée, aucun enseignant, aucun parent ne voit rien changer : le travail se fait au calme, en brouillon.

## Chacun voit le sien

Une fois publié, l'emploi du temps est visible partout :

- chaque **enseignant** consulte son horaire sur son téléphone, jour par jour ;
- chaque **parent** voit l'emploi du temps de la classe de son enfant ;
- le **secrétariat** peut l'imprimer, classe par classe ou enseignant par enseignant.

Une modification en cours d'année est visible partout dès qu'elle est enregistrée, et la date d'entrée en vigueur est précisée : on sait à partir de quand le nouveau schéma s'applique.

## Un gain de temps pour toute l'école

Ce qui prenait des jours se fait en une matinée, et surtout, les conflits ne se découvrent plus le premier jour de classe devant trente élèves qui attendent. Le préfet garde la main sur chaque décision ; l'application s'occupe de ce qu'elle fait le mieux : ne rien oublier.""",
        },
    ),
    (
        18,
        "classe-ordinateurs",
        {
            "language": "fr",
            "title": "La clôture de caisse : savoir ce qu'il y a dans le tiroir",
            "summary": "En fin de journée, le comptable compare l'argent compté à ce que dit "
            "l'application, devise par devise.",
            "body": """Une caisse d'école manipule du cash en francs congolais et en dollars, souvent dans le même tiroir, souvent entre les mains de plusieurs personnes dans la même journée. Le soir, la seule question qui compte : **le tiroir correspond-il aux reçus ?**

Dans beaucoup d'écoles, la réponse se trouve en refaisant les comptes à la main, tard, avec la fatigue d'une longue journée. Un écart de quelques milliers de francs, et c'est une heure de recherche : une erreur de rendu de monnaie, un reçu oublié, un billet faux, un paiement noté deux fois.

## Une clôture par caissier et par devise

À la fin de la journée, chaque caissier **compte l'argent** de son tiroir et saisit le total, devise par devise. L'application affiche alors, juste à côté, ce qu'elle attend d'après les reçus émis : le total des encaissements en francs, le total en dollars, et la part de chaque mode de paiement.

L'écart éventuel apparaît **tout de suite**, avant que le caissier ne rentre chez lui, quand les souvenirs de la journée sont encore frais : « j'ai rendu 500 francs à un parent » est une information qu'on retrouve en dix minutes, pas en dix jours.

![Une salle de classe aux bancs en bois : à la fin de la journée, la clôture se fait à l'écran, sans refaire les comptes à la main](photo:{salle-de-classe})

## Ce que contient une clôture

Chaque clôture garde, de façon définitive :

- la **date** et l'**heure** de la clôture ;
- le **nom du caissier** et de la caisse concernée ;
- le montant attendu et le montant compté, devise par devise ;
- l'écart, s'il y en a un, et la **justification** qu'on lui a donnée ;
- la liste des paiements et des annulations de la journée.

Une clôture n'est pas un simple total : c'est un document complet, qu'on peut relire un an plus tard.

## Rien ne se modifie en cachette

Les règles de l'application sont simples et sans exception :

- **un paiement enregistré ne se change jamais** : ni son montant, ni sa devise, ni son élève ;
- une erreur se corrige par une **annulation**, qui est un nouvel enregistrement lié au premier, avec son motif et son auteur ;
- une annulation demande une **permission particulière** : tous les caissiers ne l'ont pas ;
- chaque clôture garde la date, l'heure et la personne, et ne se réécrit pas non plus.

Ces règles protègent tout le monde : le caissier honnête contre le soupçon, l'école contre l'erreur, et le parent contre la contestation.

## Les paiements faits avant l'application

Une école qui adopte l'application en cours d'année a déjà encaissé une partie des frais. Ces paiements anciens sont repris comme des **reprises** : ils comptent dans le solde de chaque élève, mais n'apparaissent dans aucune clôture et n'ont pas de reçu : ils n'ont pas été encaissés avec l'application, et l'application ne prétend pas le contraire.

## Pour la direction

Le promoteur et le préfet consultent les clôtures **sans avoir à demander un état** au comptable : l'information est la même pour tous, et elle est à jour. On voit en un coup d'œil les jours où les écarts sont fréquents, les caissiers qui annulent beaucoup, ou les devises qui posent problème.

Le comptable, lui, gagne le temps qu'il passait à recompter. Il peut se concentrer sur ce qu'il fait de plus utile : suivre les impayés, préparer les dépôts à la banque, et répondre aux questions des parents avec des chiffres exacts.

## Un conseil pratique

Faites la clôture **chaque jour**, même les jours calmes. C'est une habitude de trois minutes, qui évite les mauvaises surprises de fin de mois. Une caisse qu'on ne clôture qu'une fois par semaine accumule des écarts qu'on ne sait plus expliquer.""",
        },
    ),
    (
        22,
        "ecole-muja",
        {
            "language": "fr",
            "title": "Préparer la rentrée : inscriptions, frais et classes",
            "summary": "Les élèves de l'an dernier passent dans leur nouvelle classe en "
            "quelques clics, les frais de l'année sont prêts avant la première inscription.",
            "body": """La rentrée se prépare des semaines avant le premier jour de classe. Il faut ouvrir la nouvelle année, composer les classes, régler les frais de chaque niveau, faire passer les élèves de l'an dernier, inscrire les nouveaux, et ouvrir la caisse. Faite à la main, cette préparation occupe le secrétariat pendant tout le mois d'août.

Voici comment une école s'y prend avec l'application, étape par étape.

## 1. Régler l'année

La direction crée la **nouvelle année scolaire**, avec ses dates et ses périodes. Elle crée ou reprend ses **classes** : les niveaux, les options pour les humanités, les sections (6e A, 6e B) et leur capacité. Elle désigne les **titulaires**.

Ensuite viennent les **frais** de chaque niveau : le minerval, les frais d'inscription, les frais d'examen. Pour chacun, l'école fixe le montant, la devise, et la façon de payer : en une fois, ou en **tranches** avec leurs dates. Le **taux de change** de l'année est enregistré une seule fois, et s'applique ensuite à tous les paiements en devise étrangère.

![Des salles de classe alignées autour d'une cour : chaque classe de l'année est créée avant l'arrivée des élèves](photo:{cour-ecole-goma})

## 2. Faire passer les élèves

À partir des décisions de fin d'année, l'application **propose le passage de classe** de chaque élève : réussite, repêchage, redoublement. La direction parcourt la liste, corrige les cas particuliers, puis confirme.

Les élèves qui ont réussi sont placés dans leur nouvelle classe sans ressaisie. Les parents peuvent être invités à **confirmer la place** de leur enfant pour la rentrée, ce qui aide l'école à savoir combien d'élèves reviendront réellement.

## 3. Inscrire les nouveaux

Les nouveaux élèves sont inscrits avec leur famille. L'application demande ce dont l'école a besoin : l'identité, la classe demandée, le tuteur, et les pièces que l'école réclame. Elle peut aussi **importer une liste** depuis un tableur, pour une école qui a déjà ses élèves dans un fichier.

Un frère ou une sœur **déjà présent** dans l'école est retrouvé : la fratrie reste ensemble sous la même famille, et la **réduction** prévue par l'école pour les fratries s'applique d'elle-même sur les frais.

## 4. Savoir ce que chacun doit

Dès l'inscription, chaque élève reçoit ses **frais** : ce qu'il doit pour l'année, découpé en tranches, avec les réductions éventuelles. Pas de calcul à refaire : l'application sait, pour chaque élève, ce qu'il doit, ce qu'il a payé et ce qui reste.

Une famille en difficulté peut avoir un **échéancier particulier**, décidé par la direction, qui remplace l'échéancier habituel pour cet élève seulement.

![Les élèves reprennent leurs places : à la rentrée, la liste de chaque classe est déjà prête](photo:{eleves-anis})

## 5. Ouvrir la caisse

Dès que les frais sont réglés, la caisse peut encaisser. Les parents voient ce qu'ils doivent sur leur téléphone, avec les dates des tranches, et reçoivent leurs reçus au fur et à mesure. Les premiers jours de rentrée, ce sont aussi les plus chargés : c'est là que la caisse hors ligne montre son utilité.

## 6. Imprimer ce qui doit l'être

L'application imprime les **listes de classe**, les **fiches d'inscription**, les **lettres d'invitation** aux parents et les **circulaires** de la direction, avec l'en-tête de l'école : son logo, son nom officiel, ses références. Chaque document porte un numéro, pour qu'on puisse le retrouver.

## Un calendrier de rentrée

Pour garder la tête froide, voici un ordre simple, qui fonctionne bien :

- **fin juillet** : régler l'année, les classes, les frais et le taux de change ;
- **début août** : faire passer les élèves et inviter les parents à confirmer leur place ;
- **mi-août** : inscrire les nouveaux et vérifier les fratries ;
- **fin août** : imprimer les listes, tester la caisse, former les caissiers ;
- **jour de la rentrée** : encaisser, avec les appareils chargés et un deuxième appareil en réserve.

Une école organisée de cette façon arrive le premier jour de classe avec des listes justes, des frais prêts et une caisse qui fonctionne : le secrétariat peut enfin accueillir les familles au lieu de courir après les papiers.""",
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


def retire_photos() -> int:
    """Retire de la photothèque les anciennes photos de démonstration (`RETIRED_SOURCES`), fichiers
    compris, sauf celles qu'un article ou une page du site montre encore (clé protégée) : la
    console peut les remplacer, puis elles partiront au passage suivant."""
    gone = 0
    for photo in SitePhoto.objects.filter(source_url__in=RETIRED_SOURCES):
        if photo.articles.exists() or photo.pages.exists():
            continue
        photo.large.delete(save=False)
        photo.small.delete(save=False)
        photo.delete()
        gone += 1
    return gone


def create_demo_photos() -> dict[str, SitePhoto]:
    """La photothèque de démonstration (les photos libres du site), sans doublon."""
    retire_photos()
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
