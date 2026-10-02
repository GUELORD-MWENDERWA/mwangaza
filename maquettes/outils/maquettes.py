"""Outils des maquettes Mwangaza (Python 3, sans dépendance).

    python3 maquettes/outils/maquettes.py menu    # réécrit le menu latéral de toutes les pages Gestion depuis MENU
    python3 maquettes/outils/maquettes.py index   # régénère maquettes/index.html depuis CATALOGUE

Les fonctions `page_gestion`, `page_auth`, `page_portail` et `ic` servent à écrire une nouvelle maquette
avec la même coquille que les autres. Captures PNG : `node maquettes/outils/captures.mjs`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- icônes (traits 1.8, 24 × 24)

ICONS = {
    # menu
    "home": '<path d="M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z"/>',
    "students": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/><circle cx="17" cy="9" r="2.6"/><path d="M16.5 14.6c2.4.2 4.2 1.9 5 4.9"/>',
    "book": '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M4 19V4.5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "cash": '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.8"/><path d="M6 9.5v5M18 9.5v5"/>',
    "alert": '<path d="M12 3 2 20h20z"/><path d="M12 10v4.5M12 17.5v.1"/>',
    "tag": '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8" r="1.4"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    "lock": '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
    "card": '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 10h18M16 15h2"/>',
    "megaphone": '<path d="M3 10v4l12 5V5z"/><path d="M15 9a3 3 0 0 1 0 6M6 14.5 7.5 20h3l-1.3-4.5"/>',
    "school": '<path d="M2 9 12 4l10 5-10 5z"/><path d="M6 11v5c0 1.5 3 3 6 3s6-1.5 6-3v-5"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
    "sync": '<path d="M20 11a8 8 0 0 0-14.3-4.3L4 8.5"/><path d="M4 4v4.5h4.5"/><path d="M4 13a8 8 0 0 0 14.3 4.3L20 15.5"/><path d="M20 20v-4.5h-4.5"/>',
    "credit": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v9M7.5 12h9"/>',
    "inbox": '<path d="M4 13h4l2 3h4l2-3h4"/><path d="M5.5 5h13L20 13v6H4v-6z"/>',
    "settings": '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
    "userplus": '<circle cx="10" cy="8" r="3.5"/><path d="M3.5 20c.8-3.6 3.4-5.5 6.5-5.5 1.6 0 3 .4 4.2 1.2"/><path d="M18 14v6M15 17h6"/>',
    "journal": '<rect x="5" y="3.5" width="14" height="17" rx="2"/><path d="M9 3.5V6h6V3.5M9 11h6M9 15h4"/>',
    # contenu
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    "print": '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M6 14h12v7H6z"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>',
    "upload": '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "check": '<path d="M4.5 12.5l5 5 10-11"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l2 2M15 8l2 2"/>',
    "phone": '<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    "wifioff": '<path d="M3 3l18 18"/><path d="M8.5 16.5a5 5 0 0 1 7 0M5 12.9a10 10 0 0 1 5-2.7M14.5 10.4a10 10 0 0 1 4.5 2.5M2 9.3a15 15 0 0 1 4.3-2.6M11 5.1A15 15 0 0 1 22 9.3"/><path d="M12 20h.01"/>',
    "chevron": '<path d="m9 6 6 6-6 6"/>',
    "chevdown": '<path d="m6 9 6 6 6-6"/>',
    "back": '<path d="m15 6-6 6 6 6"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "logout": '<path d="M15 4h4v16h-4"/><path d="M10 8l-4 4 4 4M6 12h10"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.5v.1"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.3-5.7L20 8.5"/><path d="M20 3.5v5h-5"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/><path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18.5 14.8c1.7.7 2.8 2.4 3.2 5.2"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4.5 4.3-6.5 8-6.5s7 2 8 6.5"/>',
    "bell": '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    "file": '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "excel": '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5"/><path d="m9.5 12 4 5M13.5 12l-4 5"/>',
    "qr": '<rect x="3.5" y="3.5" width="6" height="6" rx="1"/><rect x="14.5" y="3.5" width="6" height="6" rx="1"/><rect x="3.5" y="14.5" width="6" height="6" rx="1"/><path d="M14.5 14.5h2v2h-2zM18.5 18.5h2v2h-2zM18.5 14.5h2M14.5 18.5v2"/>',
    "sparkle": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    "wallet": '<path d="M4 7.5h14a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a1 1 0 0 1-1-1z"/><path d="M4 7.5 15 4v3.5M15.5 13.5h2"/>',
    "home2": '<path d="M12 3v2M5 21V11l7-5 7 5v10"/><path d="M9.5 21v-5h5v5"/>',
    "share": '<path d="M12 3v12M7.5 7.5 12 3l4.5 4.5"/><path d="M5 12v7.5h14V12"/>',
    "dots": '<circle cx="5.5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="18.5" cy="12" r="1.3"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
    "database": '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>',
}


def ic(name: str, size: int | None = 16, cls: str = "ic") -> str:
    """Icône SVG inline, même style que les maquettes existantes."""
    dims = f' width="{size}" height="{size}"' if size else ""
    return (
        f'<svg class="{cls}"{dims} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>'
    )


# --------------------------------------------------------------------------- menu latéral de la Gestion

# (section, [(fichier, libellé, icône, badge)]) — badge : "V1.1" / "V1.2" (plus tard) ou un nombre (à traiter).
MENU = [
    ("Pilotage", [("tableau-de-bord.html", "Tableau de bord", "home", None)]),
    ("Scolarité", [
        ("eleves-liste.html", "Élèves", "students", None),
        ("notes-saisie.html", "Notes et bulletins", "book", "V1.2"),
        ("presences-pointage-qr.html", "Présences", "clock", "V1.1"),
    ]),
    ("Finances", [
        ("caisse-encaissement.html", "Caisse", "cash", None),
        ("impayes.html", "Impayés", "alert", None),
        ("frais-baremes.html", "Frais et barèmes", "tag", None),
        ("annulations.html", "Annulations", "undo", 2),
        ("clotures-caisse.html", "Clôtures de caisse", "lock", None),
        ("credits-eleves.html", "Crédits d'élèves", "credit", 3),
        ("paie.html", "Personnel et paie", "card", "V1.1"),
    ]),
    ("Communication", [
        ("annonces.html", "Annonces", "megaphone", None),
        ("changements-coordonnees.html", "Demandes des parents", "inbox", 4),
    ]),
    ("Paramètres", [
        ("parametres-ecole.html", "Paramètres de l'école", "settings", None),
        ("organisation-scolaire.html", "Organisation scolaire", "school", None),
        ("personnel-comptes.html", "Comptes du personnel", "userplus", None),
        ("roles-permissions.html", "Rôles et permissions", "shield", None),
        ("appareils-synchro.html", "Appareils et synchro", "sync", None),
        ("journal-audit.html", "Journal d'audit", "journal", None),
    ]),
]

# Pages qui ont leur propre menu (plateforme) : jamais réécrites.
OWN_MENU = {"superadmin-ecoles.html"}

# Page → entrée de menu active, quand la page n'est pas elle-même dans le menu.
ACTIVE_FOR = {
    "eleve-fiche.html": "eleves-liste.html",
    "eleve-fiche-identite.html": "eleves-liste.html",
    "eleve-fiche-famille.html": "eleves-liste.html",
    "eleve-fiche-historique.html": "eleves-liste.html",
    "eleve-nouveau.html": "eleves-liste.html",
    "eleves-import.html": "eleves-liste.html",
    "eleve-reduction.html": "eleves-liste.html",
    "eleve-echeancier.html": "eleves-liste.html",
    "famille-fiche.html": "eleves-liste.html",
    "fiche-inscription.html": "eleves-liste.html",
    "liste-classe.html": "eleves-liste.html",
    "invitations-portail.html": "eleves-liste.html",
    "lettre-invitation.html": "eleves-liste.html",
    "situation-financiere.html": "impayes.html",
    "impayes-export.html": "impayes.html",
    "caisse-ouverture.html": "caisse-encaissement.html",
    "caisse-accueil.html": "caisse-encaissement.html",
    "demande-annulation.html": "caisse-encaissement.html",
    "recu.html": "caisse-encaissement.html",
    "recu-annulation.html": "annulations.html",
    "caisse-cloture.html": "caisse-encaissement.html",
    "bulletin.html": "notes-saisie.html",
    "bulletin-education-de-base.html": "notes-saisie.html",
    "cours-maxima.html": "notes-saisie.html",
    "guide-premiere-connexion.html": "caisse-encaissement.html",
}


def nav_html(active: str | None) -> str:
    parts = ['<nav class="nav">']
    for section, items in MENU:
        parts.append(f'<div class="navlabel">{section}</div>')
        for href, label, icon, badge in items:
            on = "on" if href == active else ""
            extra = ""
            if isinstance(badge, str):
                extra = f'<span class="soon">{badge}</span>'
            elif isinstance(badge, int):
                extra = f'<span class="count">{badge}</span>'
            parts.append(f'<a class="{on}" href="{href}">{ic(icon, None)}<span>{label}</span>{extra}</a>')
    parts.append("</nav>")
    return "".join(parts)


USERS = {
    "prefet": ("P. Emmanuel Bahati", "Préfet des études", "PE"),
    "comptable": ("Ir. Paluku Kasereka", "Comptable", "IP"),
    "caissiere": ("Jeanne Kavira", "Caissière · Caisse 1", "JK"),
    "secretaire": ("Masika Furaha", "Secrétaire", "MF"),
    "promoteur": ("Fr. Innocent Mugisho", "Promoteur", "IM"),
}

SYNC = {
    "online": '<div class="sync online"><span class="dot"></span>En ligne · à jour</div>',
    "offline": '<div class="sync offline"><span class="dot"></span>Hors-ligne · 4 en attente</div>',
}


def head(title: str, css: str = "../assets/styles.css") -> str:
    return (
        '<!DOCTYPE html>\n<html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title} — Mwangaza (maquette)</title>\n"
        f'<link rel="stylesheet" href="{css}"></head>\n'
    )


def page_gestion(title: str, active: str | None, user: str, content: str, sync: str = "online") -> str:
    name, role, initials = USERS[user]
    return (
        head(title)
        + '<body><div class="app"><aside class="side">\n'
        '  <div class="brand"><span class="mark"></span><b>Mwangaza</b></div>\n'
        '  <div class="school"><b>ITIG Don Bosco</b>Goma · Année 2026-2027</div>\n'
        f"  {nav_html(active)}\n"
        '  <div class="foot">Version 1.0 · Aide et guide</div>\n'
        '</aside><div class="main"><header class="top">\n'
        f'  <div class="search">{ic("search", 18)}<span>Rechercher un élève, un matricule, un reçu…</span>'
        '<span class="kbd" style="margin-left:auto">Ctrl K</span></div>\n'
        f"  {SYNC[sync]}\n"
        f'  <div class="user"><span class="hide-m" style="text-align:right"><b>{name}</b><br>'
        f'<span class="muted small">{role}</span></span><span class="avatar">{initials}</span></div>\n'
        '</header><main class="content">\n'
        + content.strip()
        + "\n</main></div></div></body></html>\n"
    )


def page_auth(title: str, content: str, school: bool = True, width: int = 440) -> str:
    """Écran hors application (connexion…) : panneau basalte à gauche, formulaire à droite."""
    left = (
        '<div class="stack" style="max-width:420px">\n'
        '    <div style="width:72px;height:72px;border-radius:14px;background:#fff;color:var(--basalt);'
        'display:grid;place-items:center;font-weight:700">ITIG</div>\n'
        '    <h1 style="font-size:2rem">ITIG Don Bosco Goma</h1>\n'
        '    <p style="color:#CFC7BF">Espace du personnel. Encaissez, suivez les élèves et informez les familles, '
        "même quand internet est coupé.</p>\n  </div>"
        if school
        else '<div class="stack" style="max-width:420px">\n'
        '    <h1 style="font-size:2rem">Espace du personnel</h1>\n'
        '    <p style="color:#CFC7BF">Un seul compte pour toutes les écoles où vous travaillez.</p>\n  </div>'
    )
    host = "itig.mwangaza.cd" if school else "app.mwangaza.cd"
    return (
        head(title)
        + '<body><div class="authgrid"><div class="authside">\n'
        '  <div class="brand" style="padding:0"><span class="mark"></span><b style="font-size:1.3rem">Mwangaza</b></div>\n'
        f"  {left}\n"
        f'  <p class="small" style="color:#A8A09A">{host} · Français | English</p>\n'
        f'</div><div class="authmain"><div style="width:100%;max-width:{width}px" class="col">\n'
        + content.strip()
        + "\n</div></div></div></body></html>\n"
    )


PNAV = [
    ("accueil.html", "Accueil", "home"),
    ("enfant-paiements.html", "Paiements", "card"),
    ("annonces.html", "Annonces", "bell"),
    ("profil.html", "Profil", "user"),
]


def page_portail(title: str, header: str, content: str, tab: str | None = None) -> str:
    nav = ""
    if tab is not None:
        links = "".join(
            f'<a class="{"on" if href == tab else ""}" href="{href}">{ic(icon, None)}{label}</a>'
            for href, label, icon in PNAV
        )
        nav = f'<nav class="pnav">{links}</nav>'
    return (
        head(title)
        + f'<body><div class="phone">{header.strip()}\n<div class="pbody">\n'
        + content.strip()
        + f"\n</div>{nav}</div></body></html>\n"
    )


# --------------------------------------------------------------------------- galerie index.html

# (fichier, titre, lot, groupe · référence, nouvelle maquette à valider ?)
GESTION = [
    ("connexion", "Connexion du personnel", "V1.0", "Accès · B4", False),
    ("connexion-double-authentification", "Double authentification", "V1.0", "Accès · B4", False),
    ("double-authentification-activation", "Activer la double authentification", "V1.0", "Accès · B4 · M1", True),
    ("choix-ecole", "Choisir l'école", "V1.0", "Accès · B3 · M2", True),
    ("deverrouillage-pin", "Déverrouillage PIN hors-ligne", "V1.0", "Accès · B5", False),
    ("mon-compte", "Mon compte", "V1.0", "Accès · B4–B5 · M4", True),
    ("tableau-de-bord", "Tableau de bord directeur", "V1.0", "Pilotage · G3", False),
    ("menu-mobile", "Menu sur téléphone et tablette", "V1.0", "Coquille · M7", True),
    ("pages-etat", "Pages d'état et d'erreur", "V1.0", "Coquille · M8", True),
    ("guide-premiere-connexion", "Guide de première connexion", "V1.0", "Transversal · I3 · M20", True),
    ("eleves-liste", "Liste des élèves", "V1.0", "Élèves · D2", False),
    ("eleve-fiche-identite", "Fiche élève, onglet Identité", "V1.0", "Élèves · D2–D3 · M9", True),
    ("eleve-fiche-famille", "Fiche élève, onglet Famille", "V1.0", "Élèves · D4 · M9", True),
    ("eleve-fiche", "Fiche élève, onglet Finances", "V1.0", "Élèves · D2–D4", False),
    ("eleve-fiche-historique", "Fiche élève, onglet Historique", "V1.0", "Élèves · I1 · M9", True),
    ("eleve-nouveau", "Inscrire un nouvel élève", "V1.0", "Élèves · D3–D4", False),
    ("eleves-import", "Import Excel (vérification)", "V1.0", "Élèves · D1", False),
    ("famille-fiche", "Fiche famille", "V1.0", "Élèves · D4, H1 · M10", True),
    ("fiche-inscription", "Fiche d'inscription (A4)", "V1.0", "Impression · D5 · M11", True),
    ("liste-classe", "Liste de classe (PDF, Excel)", "V1.0", "Impression · D5 · M11", True),
    ("invitations-portail", "Invitations au portail", "V1.0", "Élèves · H7", True),
    ("lettre-invitation", "Lettre d'invitation (2 par A4)", "V1.0", "Impression · H7", True),
    ("frais-baremes", "Frais, barèmes, taux du jour", "V1.0", "Finances · E1–E5", False),
    ("eleve-reduction", "Accorder une réduction", "V1.0", "Finances · E3 · M12", True),
    ("eleve-echeancier", "Échéancier particulier", "V1.0", "Finances · E4 · M12", True),
    ("caisse-ouverture", "Ouvrir une session de caisse", "V1.0", "Finances · F1 · M13", True),
    ("caisse-accueil", "Caisse : paiements du jour, reçus", "V1.0", "Finances · F1, F6 · M13", True),
    ("caisse-encaissement", "Caisse — encaissement hors-ligne", "V1.0", "Finances · F1–F5", False),
    ("recu", "Reçu 80 mm et A4", "V1.0", "Finances · F3–F6", False),
    ("demande-annulation", "Demander une annulation", "V1.0", "Finances · F7", True),
    ("annulations", "Annulations à valider", "V1.0", "Finances · F7", False),
    ("recu-annulation", "Reçu d'annulation", "V1.0", "Finances · F7 · M15", True),
    ("caisse-cloture", "Clôture de caisse", "V1.0", "Finances · F8", False),
    ("clotures-caisse", "Clôtures vues par le comptable", "V1.0", "Finances · F8 · M16", True),
    ("credits-eleves", "Crédits d'élèves (surpaiements)", "V1.0", "Finances · 3.6 · M14", True),
    ("impayes", "Impayés", "V1.0", "Finances · G1–G2", False),
    ("situation-financiere", "Situation financière imprimable", "V1.0", "Impression · G2 · M17", True),
    ("impayes-export", "Export des impayés (PDF, Excel)", "V1.0", "Impression · G1 · M17", True),
    ("annonces", "Annonces", "V1.0", "Communication · H4", False),
    ("changements-coordonnees", "Demandes des parents", "V1.0", "Communication · H5 · M18", True),
    ("parametres-ecole", "Paramètres de l'école", "V1.0", "Paramètres · A1 · M5", True),
    ("organisation-scolaire", "Organisation scolaire", "V1.0", "Paramètres · C1–C3", False),
    ("personnel-comptes", "Comptes du personnel", "V1.0", "Paramètres · B1–B3 · M3", True),
    ("roles-permissions", "Rôles et permissions", "V1.0", "Paramètres · B1–B2", False),
    ("appareils-synchro", "Appareils et synchronisation", "V1.0", "Paramètres · F5, B5", False),
    ("journal-audit", "Journal d'audit", "V1.0", "Paramètres · I1 · M6", True),
    ("superadmin-ecoles", "Super-admin — écoles", "V1.0", "Plateforme · A1–A3", False),
    ("session-support", "Session support « en tant qu'école »", "V1.0", "Plateforme · A3", False),
    ("paie", "Paie mensuelle", "V1.1", "Plus tard · 5.3", False),
    ("presences-pointage-qr", "Pointage QR à l'entrée", "V1.1", "Plus tard · 5.5", False),
    ("notes-saisie", "Saisie des notes", "V1.2", "Plus tard · 6.2", False),
    ("cours-maxima", "Cours et maxima par classe", "V1.2", "Plus tard · 6.1", True),
    ("bulletin", "Bulletin officiel — humanités techniques", "V1.2", "Plus tard · 6.3", True),
    ("bulletin-education-de-base", "Bulletin officiel — 7e-8e EB", "V1.2", "Plus tard · 6.3", True),
]

PORTAIL = [
    ("activation", "Activation du compte famille", "V1.0", "H1", False),
    ("connexion", "Se connecter", "V1.0", "H1 · M19", True),
    ("mot-de-passe-oublie", "Mot de passe oublié", "V1.0", "H1 · M19", True),
    ("installer", "Installer l'application", "V1.0", "H6 · M19", True),
    ("guide", "Guide de première connexion", "V1.0", "I3 · M20", True),
    ("accueil", "Accueil — mes enfants", "V1.0", "H2", False),
    ("enfant-paiements", "Paiements d'un enfant", "V1.0", "H3", False),
    ("annonces", "Annonces", "V1.0", "H4", False),
    ("profil", "Profil et coordonnées", "V1.0", "H5", False),
    ("verification-recu", "Vérification publique d'un reçu", "V1.0", "F4", False),
    ("enfant-scolarite", "Scolarité d'un enfant", "V1.2", "6.8", False),
]


# Console de la plateforme (super-admin, admin.<domaine>), son propre design (5.2).
CONSOLE = [
    ("tableau-de-bord", "Tableau de bord", "V1.1", "5.2", True),
    ("identite-plateforme", "Identité de la plateforme", "V1.1", "5.2.2", True),
]


def _card(app: str, name: str, title: str, lot: str, ref: str, new: bool) -> str:
    mobile = app == "portail"
    img = f"captures/{'mobile' if mobile else 'desktop'}/{app}-{name}.png"
    height = 300 if mobile else 170
    lot_cls = "" if lot == "V1.0" else "v"
    todo = ' <span class="pill warn">à valider</span>' if new else ""
    title_html = f'<b class="small">{title}</b>' if mobile else f"<b>{title}</b>"
    return (
        f'<a class="card" href="{app}/{name}.html" style="text-decoration:none;color:inherit;overflow:hidden">'
        f'<img src="{img}" alt="" style="width:100%;height:{height}px;object-fit:cover;object-position:top;'
        'border-bottom:1px solid var(--line)"><div class="bd"><div class="row between">'
        f'{title_html}<span class="tag {lot_cls}">{lot}</span></div>'
        f'<span class="small muted">{ref}</span>{todo}</div></a>'
    )


def build_index() -> str:
    todo = sum(1 for *_, new in GESTION + PORTAIL + CONSOLE if new)
    gestion = "".join(_card("gestion", *row) for row in GESTION)
    portail = "".join(_card("portail", *row) for row in PORTAIL)
    console = "".join(_card("console", *row) for row in CONSOLE)
    return (
        head("Maquettes", "assets/styles.css")
        + '<body><div style="background:var(--basalt);color:var(--basalt-ink);padding:36px 32px">'
        '<div class="brand" style="padding:0"><span class="mark"></span><b>Mwangaza</b></div>\n'
        '<h1 style="margin-top:16px;font-size:2rem">Maquettes de l\'application</h1>'
        '<p style="color:#CFC7BF;margin-top:6px">Application Gestion (personnel) et Portail (familles). '
        "Données fictives. Cliquez une vignette pour ouvrir l'écran. "
        f"« à valider » : {todo} maquettes dessinées par Claude le 2026-09-26, en attente de validation.</p></div>\n"
        '<main class="content" style="margin:0 auto">\n'
        f'<h2>Application Gestion — {len(GESTION)} écrans</h2><div class="grid" '
        f'style="grid-template-columns:repeat(auto-fill,minmax(280px,1fr))">{gestion}</div>\n'
        f'<h2 style="margin-top:12px">Portail familles — {len(PORTAIL)} écrans (mobile)</h2><div class="grid" '
        f'style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))">{portail}</div>\n'
        f'<h2 style="margin-top:12px">Console de la plateforme — {len(CONSOLE)} écrans</h2><div class="grid" '
        f'style="grid-template-columns:repeat(auto-fill,minmax(280px,1fr))">{console}</div>\n'
        "</main></body></html>"
    )


# --------------------------------------------------------------------------- commandes

def cmd_menu() -> None:
    """Réécrit le menu latéral de chaque page Gestion en gardant son entrée active."""
    known = {href for _, items in MENU for href, *_ in items}
    for path in sorted((ROOT / "gestion").glob("*.html")):
        if path.name in OWN_MENU:
            continue
        html = path.read_text(encoding="utf-8")
        match = re.search(r'<nav class="nav">.*?</nav>', html, re.S)
        if not match:
            continue
        current = re.search(r'<a class="on" href="([^"]+)"', match.group(0))
        active = ACTIVE_FOR.get(path.name) or (path.name if path.name in known else None)
        if active is None and current:
            active = current.group(1)
        new = html[: match.start()] + nav_html(active) + html[match.end():]
        if new != html:
            path.write_text(new, encoding="utf-8")
            print(f"menu mis à jour : gestion/{path.name} (actif : {active})")


def cmd_index() -> None:
    (ROOT / "index.html").write_text(build_index(), encoding="utf-8")
    print("index.html régénéré")


if __name__ == "__main__":
    commands = {"menu": cmd_menu, "index": cmd_index}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
