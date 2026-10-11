"""Écoles dans l'administration Django, en lecture seule (dépannage) : on les crée, modifie,
suspend et réactive dans la console de la plateforme (5.3). Liste avec statut, abonnement,
élèves, dernière activité et lien « Ouvrir en tant qu'école » (session support, A3).
"""

from django.contrib import admin
from django.utils import formats, timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.schools import console
from apps.schools.models import School


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = [
        "name_and_address",
        "status",
        "student_count",
        "subscription",
        "last_activity",
        "support_link",
    ]
    list_filter = ["environment", "status"]
    search_fields = ["code", "name", "official_name"]
    fieldsets = [
        (
            _("Identity"),
            {
                "fields": [
                    "code",
                    "name",
                    "official_name",
                    "logo",
                    "primary_color",
                    "timezone",
                    "enabled_currencies",
                    "default_currency",
                ]
            },
        ),
        (_("Subscription"), {"fields": ["status", "plan", "trial_ends_on", "paid_until"]}),
        (_("Dates"), {"fields": ["id", "created_at", "updated_at"]}),
    ]

    def get_queryset(self, request):
        return console.schools()

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description=_("school"), ordering="name")
    def name_and_address(self, school: School):
        return format_html("{}<br><small>{}</small>", school.name, school.url)

    @admin.display(description=_("subscription"))
    def subscription(self, school: School) -> str:
        parts = [school.plan] if school.plan else []
        if school.status == School.Status.TRIAL and school.trial_ends_on:
            parts.append(_("trial until %(date)s") % {"date": f"{school.trial_ends_on:%d/%m/%Y}"})
        if school.paid_until:
            parts.append(_("paid until %(date)s") % {"date": f"{school.paid_until:%d/%m/%Y}"})
        return " · ".join(str(part) for part in parts) or "—"

    @admin.display(description=_("students"), ordering="student_count")
    def student_count(self, school: School) -> int:
        return school.student_count

    @admin.display(description=_("last activity"), ordering="last_activity_at")
    def last_activity(self, school: School) -> str:
        if school.last_activity_at is None:
            return "—"
        # Date et heure dans la langue de l'administration (pas de texte « il y a » à traduire).
        return formats.date_format(
            timezone.localtime(school.last_activity_at), "SHORT_DATETIME_FORMAT"
        )

    @admin.display(description=_("support"))
    def support_link(self, school: School):
        if school.is_closed:
            return "—"
        # Écran « Session support » de la Gestion, à l'adresse de l'école (A3) : connexion d'abord.
        return format_html(
            '<a href="{}/app/support" target="_blank" rel="noopener">{}</a>',
            school.url,
            _("Open as the school"),
        )
