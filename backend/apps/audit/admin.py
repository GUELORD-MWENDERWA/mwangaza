"""Administration Django : le journal de toutes les écoles, en lecture seule (support)."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.accounts.admin import ReadOnlyAdmin
from apps.audit.actions import Action
from apps.audit.models import AuditLog, PlatformAuditLog


class ActionFilter(admin.SimpleListFilter):
    title = _("action")
    parameter_name = "action"

    def lookups(self, request, model_admin):
        return Action.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(action=self.value())
        return queryset


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    list_display = ["created_at", "school", "action_label", "actor", "entity_label", "ip"]
    list_filter = ["school", ActionFilter]
    search_fields = ["entity_label", "actor__phone", "actor__last_name", "actor__first_name"]
    fields = [
        "id",
        "created_at",
        "school",
        "action",
        "actor",
        "impersonated_by",
        "entity_type",
        "entity_id",
        "entity_label",
        "before",
        "after",
        "ip",
        "user_agent",
    ]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        # Super-admin : toutes les écoles (pas d'école courante dans l'administration).
        return AuditLog.all_schools.select_related("school", "actor")

    @admin.display(description=_("action"), ordering="action")
    def action_label(self, log: AuditLog) -> str:
        return log.get_action_display()


@admin.register(PlatformAuditLog)
class PlatformAuditLogAdmin(ReadOnlyAdmin):
    """Journal de la plateforme (console du super-admin), en lecture seule."""

    list_display = ["created_at", "action_label", "actor", "entity_label", "ip"]
    search_fields = ["entity_label", "actor__phone", "actor__last_name", "actor__first_name"]
    fields = [
        "id",
        "created_at",
        "action",
        "actor",
        "entity_type",
        "entity_id",
        "entity_label",
        "before",
        "after",
        "ip",
        "user_agent",
    ]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("actor")

    @admin.display(description=_("action"), ordering="action")
    def action_label(self, log: PlatformAuditLog) -> str:
        return log.get_action_display()
