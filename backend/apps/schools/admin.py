from django.contrib import admin

from apps.schools.models import School


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["code", "name"]
    readonly_fields = ["id", "created_at", "updated_at"]
