"""Administration Django (dépannage) : l'IA en lecture seule. On règle avec la console (IA.1.2) ou
`manage.py ai_allowance` : les deux passent par les services et le journal de la plateforme."""

from django.contrib import admin

from apps.accounts.admin import ReadOnlyAdmin
from apps.ai.models import AiAllowance, AiBalance, AiCall, AiSettings, AiUsageMonth


class AllSchoolsReadOnly(ReadOnlyAdmin):
    def get_queryset(self, request):
        return self.model.all_schools.select_related("school")


@admin.register(AiSettings)
class AiSettingsAdmin(ReadOnlyAdmin):
    list_display = ["enabled", "monthly_cap_micro", "hourly_limit"]


@admin.register(AiAllowance)
class AiAllowanceAdmin(AllSchoolsReadOnly):
    list_display = ["school", "uses", "monthly_credits", "paused"]


@admin.register(AiBalance)
class AiBalanceAdmin(AllSchoolsReadOnly):
    list_display = ["school", "month", "granted_micro", "spent_micro"]
    list_filter = ["month"]


@admin.register(AiUsageMonth)
class AiUsageMonthAdmin(AllSchoolsReadOnly):
    list_display = ["school", "month", "use", "calls", "kept", "abandoned", "cost_micro"]
    list_filter = ["month", "use"]


@admin.register(AiCall)
class AiCallAdmin(AllSchoolsReadOnly):
    list_display = ["created_at", "school", "use", "model", "state", "refusal", "cost_micro"]
    list_filter = ["state", "use"]
