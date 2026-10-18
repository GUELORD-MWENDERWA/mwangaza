"""Contenus du site public qui changent plus souvent que la mise en page (WEB.1b) : ce que fait
chaque module du catalogue, « Prochainement », écoles de référence. Ils passeront dans la console,
tenus par la communication (SITE.1) ; d'ici là, une seule liste ici, jamais dans les gabarits."""

from django.utils.translation import gettext_lazy as _

# Ce que fait chaque module de `accounts/modules.py` (même clé). Un module ajouté au catalogue
# apparaît seul sur la page Modules, avec son nom ; ses points s'ajoutent ici.
MODULE_ICONS = {
    "students": "students",
    "finance": "cash",
    "academics": "book",
    "portal": "users",
    "communication": "megaphone",
    "notifications": "bell",
    "offline": "wifioff",
}
MODULE_FEATURES = {
    "students": (
        _("Excel import with an error report"),
        _("Families, siblings and family code"),
        _("Registration forms and class lists"),
    ),
    "finance": (
        _("Fee scales in USD and FC, instalments, discounts"),
        _("Cash desk, 58 / 80 mm or A4 receipts, cash counts"),
        _("Unpaid fees, statements, approved cancellations"),
    ),
    "academics": (
        _("Courses, maximum marks and marks by term"),
        _("Conduct, deliberation, resits"),
        _("Report cards with an authenticity QR code, mark sheets, summaries"),
    ),
    "portal": (
        _("Payments, receipts and due dates"),
        _("Notices, calendar, summons"),
        _("Several children, several schools"),
    ),
    "communication": (
        _("To families or to staff"),
        _("Printable circular"),
        _("School calendar"),
    ),
    "notifications": (
        _("Payment received alert on the phone"),
        _("Due date reminder to parents, if the school wants it"),
        _("Cash desks left open"),
    ),
    "offline": (
        _("Cash desk and student search offline"),
        _("Sent automatically, never twice"),
        _("PIN code on known devices"),
    ),
}

# D'après la file de `docs/05-plan-de-travail.md`, jamais de date ; une ligne s'en va quand son
# module entre au catalogue.
UPCOMING = (
    (
        _("Mobile Money payments"),
        _("Parents pay the fees from their phone; the receipt arrives by itself."),
    ),
    (_("School finances"), _("Expenses, budget and the school's own cash, next to student fees.")),
    (_("Timetable"), _("Built with no room or teacher clash.")),
    (_("Attendance"), _("Roll call in class and student card.")),
    (_("Library and workshops"), _("Lending of books, tools and workshop equipment.")),
    (_("School website"), _("A public page kept by the school itself.")),
)

# Écoles présentées sur l'accueil (faits publics, logo et photo avec l'accord de l'école).
# `quote` : les vrais mots d'une personne de l'école, avec son nom, sa fonction et l'accord écrit
# de l'école ; jamais inventés. Vide : la carte s'affiche sans citation.
REFERENCES = (
    {
        "name": "ITIG Don Bosco Goma",
        "kind": _("Industrial technical institute · Goma, North Kivu"),
        "logo": "core/site/photos/itig-logo.webp",
        "photo": "itig-cour",
        "photo_alt": _(
            "ITIG Don Bosco Goma students gathered in the courtyard, in front of the flag"
        ),
        "facts": (
            (_("1,000+"), _("students")),
            ("4", _("technical options")),
            ("1981", _("founded")),
        ),
        "quote": "",
        "quote_by": "",
    },
)
