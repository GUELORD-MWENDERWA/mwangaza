"""Cycle de vie d'une école (CON.2) : chaque changement d'état (lecture seule, suspension, arrêt,
réouverture) écrit au journal de la plateforme (`services.py`) **et** prévient l'école par e-mail,
à l'adresse de contact de sa fiche. À l'arrêt, l'e-mail porte le lien de l'export complet.

Envoi en tâche de fond, après validation de la transaction : jamais dans la requête. Sans adresse de
contact ou sans serveur d'envoi, rien n'est envoyé (le journal reste la trace). Espaces d'essai et
de démonstration : aucun e-mail."""

from django.conf import settings
from django.core.mail import send_mail
from django.utils import translation
from django.utils.translation import gettext as _

from apps.core.models import PlatformSettings
from apps.schools import exports
from apps.schools.models import School, SchoolExport

READ_ONLY, SUSPENDED, STOPPED, REOPENED, EXPORT = (
    "readonly",
    "suspended",
    "stopped",
    "reopened",
    "export",
)


def email_configured() -> bool:
    return bool(settings.EMAIL_HOST and settings.EMAIL_HOST_USER)


def _messages(event: str, school: School) -> tuple[str, str]:
    name = school.official_name or school.name
    subjects = {
        READ_ONLY: _("%(school)s: your space is now read-only"),
        SUSPENDED: _("%(school)s: your space is suspended"),
        STOPPED: _("%(school)s: your space is closed"),
        REOPENED: _("%(school)s: your space is open again"),
        EXPORT: _("%(school)s: your data export is ready"),
    }
    bodies = {
        READ_ONLY: _(
            "An invoice is overdue. You can still read and print everything, but nothing can be "
            "written until it is paid."
        ),
        SUSPENDED: _("Nobody can sign in to your space for now. None of your data is deleted."),
        STOPPED: _("Your space is closed and nobody can sign in. Your data is kept."),
        REOPENED: _("Your space is open again: you can sign in as before."),
        EXPORT: _("The export of all your data is ready."),
    }
    return subjects[event] % {"school": name}, str(bodies[event])


def send(school_id, event: str, export_id=None, reason: str = "") -> None:
    """Corps de la tâche `tasks.email_school`."""
    school = School.objects.filter(pk=school_id).first()
    if school is None or not school.contact_email or not email_configured():
        return
    if school.environment != School.Environment.LIVE:
        return
    platform = PlatformSettings.load()
    with translation.override(settings.LANGUAGE_CODE):
        subject, body = _messages(event, school)
        if reason:
            body += "\n\n" + _("Reason: %(reason)s") % {"reason": reason}
        export = SchoolExport.objects.filter(pk=export_id).first() if export_id else None
        if export is not None and export.state == SchoolExport.State.READY:
            address = settings.SCHOOL_URL.format(code="admin")
            link = f"{address}/api/platform/school-exports/{exports.token(export)}/"
            body += "\n\n" + _("Download your data (valid %(days)s days): %(link)s") % {
                "days": exports.VALID_DAYS,
                "link": link,
            }
        body += "\n\n" + platform.name
    send_mail(
        subject, body, f"{platform.name} <{settings.EMAIL_HOST_USER}>", [school.contact_email]
    )
