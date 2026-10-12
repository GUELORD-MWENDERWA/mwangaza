# Tâche 5.7 — Communication (faite d'un coup, à la demande de l'utilisateur)

**Serveur** (`notifications`, migration unique) :
- `Announcement.audience = staff` : lue par tout le personnel (`GET /api/staff-announcements/`), notification `staff_announcement` ; jamais dans le portail.
- Circulaire : `GET /api/announcements/{id}/circular/` — l'annonce en lettre PDF à en-tête de l'école (à imprimer pour les familles sans téléphone).
- `SchoolEvent` (calendrier : titre, sorte, du… au…, heure, pour tous ou personnel seulement) : `/api/calendar-events/`, lu par tout le personnel.
- `Summons` (convocation : élève, motif, date et heure, auprès de qui ; jamais modifiée, seulement annulée) : `/api/summons/`, lettre PDF, journal d'audit, notification `summons` au parent, « vue le ».
- Portail : `GET /api/portal/calendar/` (événements + convocations des enfants), `POST /api/portal/summons/seen/`, titulaire dans la fiche de l'enfant ; téléphone du titulaire seulement si l'école l'a choisi (`School.settings["portal"]`).
- `make demo` : annonce au personnel, événements, convocations, téléphone du titulaire montré à l'ITIG.

**Gestion** : destinataire « Personnel » et « Circulaire » dans Annonces ; écrans « Annonces de l'école » (tout le personnel), « Calendrier », « Convocations » ; réglage du portail dans Paramètres.
**Portail** : écran « Calendrier » (événements, convocations), bandeau de convocation à l'accueil, titulaire sur la page de l'enfant.

**Regard senior — retiré ou simplifié** :
- « Messages à une classe » : c'est déjà l'annonce « Certaines classes » de la 4.3 (avec notification depuis 5.6.1) ; rien de plus.
- Pas de nouveau droit : `announcements.publish` couvre annonces, calendrier et convocations (aucune migration des rôles).
- Pas de « lu par » pour le personnel ni de notification à chaque événement du calendrier (bruit, écritures) ; pas de rappel la veille (planificateur).
- « Enseignants avec contacts » : seul le titulaire existe ; les enseignants par cours arrivent avec la V1.4.
- Périodes et examens de l'année : pas recopiés dans le calendrier (l'école y note ses dates).

**Tests** : isolation entre deux écoles (événements, convocations, annonces du personnel, portail), droits (403), annonce du personnel absente du portail, convocation d'un autre parent invisible, téléphone du titulaire caché par défaut, audit des convocations.
