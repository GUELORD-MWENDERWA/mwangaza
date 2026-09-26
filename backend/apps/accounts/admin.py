"""Administration Django : réservée au super-admin (`User.is_platform_admin`).

Comptes : création et modification, réinitialisation de la double authentification (support,
pour un compte qui sert dans plusieurs écoles). Rôles et appartenances : lecture seule, toutes
écoles ; les changements passent par l'API de l'école et ses règles (école séparée, dernier
gestionnaire des rôles).
"""

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from apps.accounts import services
from apps.accounts.models import Membership, Role, User

# Les groupes de Django ne servent pas : les droits dans une école viennent de ses rôles.
admin.site.unregister(Group)


class UserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("phone", "last_name", "middle_name", "first_name")


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm
    list_display = [
        "phone",
        "last_name",
        "middle_name",
        "first_name",
        "is_active",
        "totp_enabled",
        "is_platform_admin",
    ]
    list_filter = ["is_active", "is_platform_admin", "language"]
    search_fields = ["phone", "last_name", "middle_name", "first_name"]
    ordering = ["last_name", "middle_name", "first_name"]
    filter_horizontal = []
    readonly_fields = ["id", "totp_enabled_at", "last_login", "created_at", "updated_at"]
    actions = ["reset_totp"]
    fieldsets = [
        (None, {"fields": ["id", "phone", "password"]}),
        (_("Name"), {"fields": ["last_name", "middle_name", "first_name", "language"]}),
        (
            _("Access"),
            {
                "fields": [
                    "is_active",
                    "is_platform_admin",
                    "must_change_password",
                    "totp_enabled_at",
                ]
            },
        ),
        (_("Dates"), {"fields": ["last_login", "created_at", "updated_at"]}),
    ]
    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": [
                    "phone",
                    "last_name",
                    "middle_name",
                    "first_name",
                    "usable_password",
                    "password1",
                    "password2",
                ],
            },
        )
    ]

    @admin.display(boolean=True, description=_("two-factor authentication"))
    def totp_enabled(self, user: User) -> bool:
        return user.totp_enabled

    @admin.action(description=_("Reset two-factor authentication (lost phone)"))
    def reset_totp(self, request, queryset):
        for user in queryset:
            services.reset_totp(user)
        self.message_user(
            request,
            _("Two-factor authentication reset: to be turned on again at the next login."),
            messages.SUCCESS,
        )


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Role)
class RoleAdmin(ReadOnlyAdmin):
    list_display = ["__str__", "school", "code", "permission_count"]
    list_filter = ["school"]
    fields = ["id", "school", "code", "name", "permissions", "created_at", "updated_at"]

    def get_queryset(self, request):
        # Super-admin : toutes les écoles (pas d'école courante dans l'administration).
        return Role.all_schools.select_related("school")

    @admin.display(description=_("permissions"))
    def permission_count(self, role: Role) -> int:
        return len(role.permissions)


@admin.register(Membership)
class MembershipAdmin(ReadOnlyAdmin):
    list_display = ["user", "school", "role_names", "is_active"]
    list_filter = ["school", "is_active"]
    search_fields = ["user__phone", "user__last_name", "user__first_name"]
    fields = ["id", "user", "school", "role_names", "is_active", "created_at", "updated_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "school")

    @admin.display(description=_("roles"))
    def role_names(self, membership: Membership) -> str:
        roles = Role.all_schools.filter(memberships=membership, school_id=membership.school_id)
        return ", ".join(str(role) for role in roles)
