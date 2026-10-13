# Tâche S.4 — Fichiers envoyés

**But** : plus aucune image venue d'une école n'est gardée telle quelle. Logo, logo noir et blanc, photo d'élève, logo et icône de la plateforme : PNG ou JPEG, 1 Mo et 2 048 px de côté au plus, décodés puis **ré-encodés** (`core/images.py` : seuls les pixels sont repris — ni EXIF, ni GPS, ni octets cachés ; orientation appliquée avant). Logo d'école : SVG refusé (ceux déjà enregistrés restent servis en `sandbox`) ; SVG filtré gardé pour le logo de la plateforme (super-admin). Pièce jointe : PDF, 5 Mo, servie en `attachment`. Caddy : corps de requête de 10 Mo au plus.

**Hors périmètre** : antivirus ; imports Excel (vérifié : déjà 5 Mo, 5 000 lignes, lecture en flux) ; conversion des SVG existants ; réduction des images par le serveur (refus au-delà de 2 048 px ; la Gestion réduit déjà les photos à 800 px).

**Regard senior** : Pillow devient une dépendance déclarée — il est déjà installé (WeasyPrint en dépend), rien ne grossit, et on ne ré-encode pas sans décoder. Dimensions lues dans l'en-tête **avant** de décoder (au pire 2 048² × 4 octets = 16 Mo, serveur à 2 Go) ; deux décodeurs seulement (liste blanche). Ré-encodage à la frontière (champ DRF) : les services gardent « fichier déjà vérifié ». Codes d'erreur communs (`image_too_large`, `image_type`, `image_dimensions`) au lieu d'un jeu par écran. Administration Django (dépannage, super-admin) : vérifié, pas ré-encodé.

**Critères d'acceptation** : SVG refusé pour une école, accepté pour la plateforme ; image enregistrée sans métadonnée ; image trop lourde, trop grande ou d'un autre format refusée avec un message clair ; PDF joint téléchargé ; un envoi de plus de 10 Mo est arrêté par Caddy.

**Tests obligatoires** : `core/tests/test_images.py` (EXIF et GPS retirés, orientation gardée, transparence gardée, refus : poids, dimensions, bombe, GIF, fichier tronqué) ; logo d'école (SVG refusé, ancien SVG servi en `sandbox`, isolation et permission déjà en place) ; photo et icône ré-encodées ; pièce jointe en `attachment` ; limite Caddy.

**Documents** : `03` (journal des décisions : Pillow), `05`, `06`, `reference.md`, `A-FAIRE.md`, `maquettes/README.md` (M5 : plus de SVG), skill `backend`.

**Risques / à vérifier** : tests existants avec de faux PNG (à refaire en vraies images) ; `logo_kind` sert encore aux fichiers enregistrés (PDF, type servi) ; migration `core` (validateur du logo de la plateforme) ; note mémoire : purge du cache de construction dans `deployer.sh` (PR qui touche `infra/`).
