"""Écoles dans l'administration Django (super-admin, A1 et A2).

Créer une école avec son premier directeur, suivre la liste (statut, abonnement saisi à la main,
dernière activité), suspendre ou réactiver, ouvrir une session support (A3). Chaque changement
passe par `services.py` et va dans le journal de l'école. On ne supprime pas une école : on la
suspend.
"""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.template.response import TemplateResponse
from django.utils import formats, timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.accounts.phone import INVALID_PHONE_MESSAGE, InvalidPhoneError, normalize_phone
from apps.audit.models import AuditLog
from apps.core.money import Currency
from apps.schools import services
from apps.schools.models import School
from apps.students.models import Enrollment


class SchoolForm(forms.ModelForm):
    enabled_currencies = forms.TypedMultipleChoiceField(
        label=_("Currencies"), choices=Currency.choices, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = School
        fields = [
            "code",
            "name",
            "official_name",
            "logo",
            "primary_color",
            "timezone",
            "enabled_currencies",
            "default_currency",
            "status",
            "plan",
            "trial_ends_on",
            "paid_until",
        ]
        widgets = {"primary_color": forms.TextInput(attrs={"type": "color"})}


class SchoolCreationForm(SchoolForm):
    """+ le premier directeur (A1). Numéro déjà connu : ses noms ne changent pas."""

    director_phone = forms.CharField(
        label=_("Head: phone"), max_length=64, help_text=_("e.g. 0971234567.")
    )
    director_last_name = forms.CharField(
        label=_("Head: last name"),
        max_length=100,
        required=False,
        help_text=_("Required for a phone number without an account."),
    )
    director_middle_name = forms.CharField(
        label=_("Head: middle name"), max_length=100, required=False
    )
    director_first_name = forms.CharField(
        label=_("Head: first name"), max_length=100, required=False
    )

    def clean_director_phone(self) -> str:
        try:
            return normalize_phone(self.cleaned_data["director_phone"])
        except InvalidPhoneError:
            raise ValidationError(INVALID_PHONE_MESSAGE, code="invalid_phone") from None

    def clean(self):
        data = super().clean()
        phone = data.get("director_phone")
        known = phone and User.objects.filter(phone=phone).exists()
        if phone and not known and not data.get("director_last_name", "").strip():
            self.add_error(
                "director_last_name", _("This phone number has no account yet: enter the name.")
            )
        return data

    def director(self) -> services.Director:
        data = self.cleaned_data
        return services.Director(
            phone=data["director_phone"],
            last_name=data["director_last_name"].strip(),
            middle_name=data["director_middle_name"].strip(),
            first_name=data["director_first_name"].strip(),
        )


_IDENTITY = (
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
)
_SUBSCRIPTION = (_("Subscription"), {"fields": ["status", "plan", "trial_ends_on", "paid_until"]})


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    form = SchoolForm
    list_display = [
        "name_and_address",
        "status",
        "student_count",
        "subscription",
        "last_activity",
        "support_link",
    ]
    list_filter = ["status"]
    search_fields = ["code", "name", "official_name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    actions = ["suspend", "reactivate"]
    fieldsets = [_IDENTITY, _SUBSCRIPTION, (_("Dates"), {"fields": readonly_fields})]
    add_fieldsets = [
        _IDENTITY,
        (
            _("Head of the school"),
            {
                "fields": [
                    "director_phone",
                    "director_last_name",
                    "director_middle_name",
                    "director_first_name",
                ]
            },
        ),
        _SUBSCRIPTION,
    ]

    def get_queryset(self, request):
        # Dernière activité : dernière entrée du journal de l'école qui n'est pas du support.
        last = (
            AuditLog.all_schools.filter(school=OuterRef("pk"), impersonated_by__isnull=True)
            .exclude(actor__is_platform_admin=True)
            .order_by("-created_at")
            .values("created_at")[:1]
        )
        # Élèves : inscriptions actives de l'année en cours de l'école (A2).
        students = (
            Enrollment.all_schools.filter(
                school=OuterRef("pk"), status="active", academic_year__is_current=True
            )
            .order_by()
            .values("school")
            .annotate(count=Count("pk"))
            .values("count")
        )
        return (
            super()
            .get_queryset(request)
            .annotate(
                last_activity_at=Subquery(last),
                student_count=Coalesce(Subquery(students), 0),
            )
        )

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = SchoolCreationForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        return self.add_fieldsets if obj is None else self.fieldsets

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def save_model(self, request, obj, form, change):
        if change:
            services.save_school(obj, actor=request.user)
            return
        membership, password = services.create_school(
            obj, actor=request.user, director=form.director()
        )
        request._new_director = (membership, password)

    def response_add(self, request, obj, post_url_continue=None):
        """Mot de passe provisoire du directeur affiché une seule fois, sur cette page."""
        membership, password = request._new_director
        return TemplateResponse(
            request,
            "admin/schools/school/created.html",
            {
                **self.admin_site.each_context(request),
                "title": _("School created"),
                "opts": self.opts,
                "school": obj,
                "director": membership.user,
                "temporary_password": password,
            },
        )

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
        if school.status == School.Status.SUSPENDED:
            return "—"
        # Écran « Session support » de la Gestion, à l'adresse de l'école (A3) : connexion d'abord.
        return format_html(
            '<a href="{}/app/support" target="_blank" rel="noopener">{}</a>',
            school.url,
            _("Open as the school"),
        )

    @admin.action(description=_("Suspend the selected schools (nothing is deleted)"))
    def suspend(self, request, queryset):
        for school in queryset:
            services.suspend(school, actor=request.user)
        self.message_user(request, _("Suspended: nobody can log in any more."), messages.SUCCESS)

    @admin.action(description=_("Reactivate the selected schools"))
    def reactivate(self, request, queryset):
        for school in queryset:
            services.reactivate(school, actor=request.user)
        self.message_user(request, _("Reactivated."), messages.SUCCESS)
