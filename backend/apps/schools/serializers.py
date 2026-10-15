import re
from copy import copy
from pathlib import Path

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from apps.accounts.models import User
from apps.core import health
from apps.core.images import CleanedFileField, clean_signature
from apps.core.money import Currency
from apps.schools import organisation, receipts, signatures
from apps.schools.matricule import MAX_LENGTH as MAX_MATRICULE_LENGTH
from apps.schools.models import (
    TRACK_CODE_PATTERN,
    AcademicYear,
    ClassGroup,
    Level,
    School,
    Term,
    Track,
)
from apps.schools.organisation import TermNode, YearTemplate

LOGO_ADDRESSES = {"logo": "/api/school/logo/", "logo_monochrome": "/api/school/logo-monochrome/"}


def logo_url(school: School, field: str = "logo") -> str | None:
    """Adresse d'un logo sur l'adresse de l'école ; elle change avec chaque logo (cache)."""
    file = getattr(school, field)
    if not file:
        return None
    return f"{LOGO_ADDRESSES[field]}?v={Path(file.name).stem.rsplit('-', 1)[-1]}"


class _LogoMixin(serializers.Serializer):
    text_color = serializers.CharField(
        read_only=True, help_text="Couleur du texte posé sur `primary_color` : blanc ou encre."
    )
    logo = serializers.SerializerMethodField(
        help_text="Adresse du logo (`GET /api/school/logo/`, public) ; null sans logo."
    )

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_logo(self, school: School) -> str | None:
        return logo_url(school)


class ReceiptSettingsSerializer(serializers.Serializer):
    """Réglages du reçu (M5, `receipts.py`). Écriture partielle : les autres restent."""

    printer = serializers.ChoiceField(
        choices=receipts.PRINTERS,
        help_text="Thermique 58 ou 80 mm, ou imprimante ordinaire avec une feuille A4.",
    )
    sheet_size = serializers.ChoiceField(
        choices=receipts.SHEET_SIZES,
        help_text="Sur une feuille A4 : A6 (4 par feuille), A5 (2), petit format ≈ 10 x 7 cm (8).",
    )
    copies = serializers.ChoiceField(
        choices=receipts.COPIES, help_text="1 (élève) ou 2 (élève et souche pour l'école)."
    )
    header = serializers.CharField(
        max_length=300,
        allow_blank=True,
        trim_whitespace=False,
        help_text="Lignes d'en-tête : adresse, téléphone, e-mail (5 lignes au plus).",
    )
    footer = serializers.CharField(
        max_length=200, allow_blank=True, help_text="Mention en bas du reçu."
    )

    def validate_header(self, value: str) -> str:
        lines = [line.strip() for line in value.strip().splitlines()]
        if len(lines) > receipts.HEADER_MAX_LINES:
            message = _("At most %(count)d header lines.") % {"count": receipts.HEADER_MAX_LINES}
            raise serializers.ValidationError(message, code="too_many_lines")
        return "\n".join(lines)


class AlertSettingsSerializer(serializers.Serializer):
    """Seuils d'alerte au directeur (M5, `alerts.py`). Écriture partielle : les autres restent."""

    difference_minor = serializers.DictField(
        child=serializers.IntegerField(min_value=0),
        help_text="Écart de caisse au-delà duquel une clôture est signalée, par devise "
        "(plus petite unité : centimes, francs).",
    )
    cancellations_per_day = serializers.IntegerField(
        min_value=0,
        max_value=100,
        help_text="Annulations demandées par un caissier dans une journée au-delà desquelles "
        "il est signalé.",
    )
    closing_time = serializers.TimeField(
        format="%H:%M",
        input_formats=["%H:%M"],
        help_text="Heure (HH:MM) à laquelle une caisse encore ouverte est signalée.",
    )

    def validate_difference_minor(self, value: dict) -> dict:
        if unknown := set(value) - set(Currency.values):
            raise serializers.ValidationError(
                _("Unknown currency: %(codes)s.") % {"codes": ", ".join(sorted(unknown))},
                code="unknown_currency",
            )
        return value


class PortalSettingsSerializer(serializers.Serializer):
    """Ce que le portail montre aux parents (`portal.py`, 5.7)."""

    teacher_phone = serializers.BooleanField(
        help_text="Montrer aux parents le téléphone du titulaire de la classe de leur enfant."
    )


class ReminderSettingsSerializer(serializers.Serializer):
    """Relances aux parents (`reminders.py`, 5.6.2). Écriture partielle : les autres restent."""

    enabled = serializers.BooleanField(
        help_text="Envoyer aux parents les notifications d'échéance proche et de retard."
    )
    days_before = serializers.IntegerField(
        min_value=1,
        max_value=30,
        help_text="Jours avant la date limite où part « Échéance proche ».",
    )
    overdue_every_days = serializers.IntegerField(
        min_value=1,
        max_value=60,
        help_text="Jours entre deux rappels d'un retard au même parent.",
    )


class CurrentSchoolSerializer(_LogoMixin, serializers.ModelSerializer):
    """Informations publiques de l'école : écran de connexion (nom, couleur, logo) ; fuseau et
    devises pour les écrans (dates, montants)."""

    enabled_currencies = serializers.ListField(
        child=serializers.ChoiceField(choices=Currency.choices), read_only=True
    )
    logo_monochrome = serializers.SerializerMethodField(
        help_text="Adresse du logo noir et blanc des reçus thermiques (public) ; null sans lui."
    )
    receipt = serializers.SerializerMethodField()
    setup_done = serializers.SerializerMethodField(
        help_text="Liste « Mise en route » terminée : le tableau de bord ne la demande plus."
    )

    class Meta:
        model = School
        fields = [
            "code",
            "name",
            "primary_color",
            "text_color",
            "environment",
            "logo",
            "logo_monochrome",
            "timezone",
            "enabled_currencies",
            "default_currency",
            "auto_matricule",
            "receipt",
            "setup_done",
        ]

    def get_setup_done(self, school: School) -> bool:
        return school.setup_completed_at is not None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_logo_monochrome(self, school: School) -> str | None:
        return logo_url(school, "logo_monochrome")

    @extend_schema_field(ReceiptSettingsSerializer)
    def get_receipt(self, school: School) -> dict:
        return ReceiptSettingsSerializer(receipts.receipt_settings(school.settings)).data


class SchoolSettingsSerializer(_LogoMixin, serializers.ModelSerializer):
    """Paramètres de l'école (M5). Le code (adresse) ne change que par le support Mwangaza."""

    enabled_currencies = serializers.ListField(
        child=serializers.ChoiceField(choices=Currency.choices),
        allow_empty=False,
        required=False,
        help_text="Devises de l'école (au moins une).",
    )
    logo_monochrome = serializers.SerializerMethodField(
        help_text="Adresse du logo noir et blanc des reçus thermiques (public) ; null sans lui."
    )
    stamp = serializers.SerializerMethodField(
        help_text="Adresse du cachet (personnel connecté seulement) ; null sans lui (DOC.1)."
    )
    head_signature = serializers.SerializerMethodField(
        help_text="Adresse de la signature du chef d'établissement ; null sans elle (DOC.1)."
    )
    receipt = ReceiptSettingsSerializer(required=False)
    alerts = AlertSettingsSerializer(required=False)
    reminders = ReminderSettingsSerializer(required=False)
    portal = PortalSettingsSerializer(required=False)

    class Meta:
        model = School
        fields = [
            "code",
            "name",
            "official_name",
            "primary_color",
            "text_color",
            "logo",
            "logo_monochrome",
            "timezone",
            "enabled_currencies",
            "default_currency",
            "stamp",
            "head_name",
            "head_title",
            "head_signature",
            "receipt",
            "alerts",
            "reminders",
            "portal",
        ]
        read_only_fields = ["code"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_logo_monochrome(self, school: School) -> str | None:
        return logo_url(school, "logo_monochrome")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_stamp(self, school: School) -> str | None:
        return signatures.school_image_url(school, "stamp")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_head_signature(self, school: School) -> str | None:
        return signatures.school_image_url(school, "head_signature")

    def validate(self, data):
        # Mêmes règles que l'administration (`School.clean`) : devise principale parmi celles de
        # l'école, couleur écrite `#RRGGBB`.
        school = copy(self.instance)
        for field, value in data.items():
            if field not in ("receipt", "alerts", "reminders", "portal"):
                setattr(school, field, value)
        try:
            school.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(get_error_detail(exc)) from None
        for field in ("primary_color", "enabled_currencies"):
            if field in data:
                data[field] = getattr(school, field)
        return data


class LogoUploadSerializer(serializers.Serializer):
    logo = CleanedFileField(help_text="PNG ou JPEG, 1 Mo et 2 048 pixels de côté au plus.")


class SignatureUploadSerializer(serializers.Serializer):
    image = CleanedFileField(
        clean=clean_signature,
        help_text="Cachet ou signature : PNG ou JPEG, 1 Mo et 2 048 pixels de côté au plus ; "
        "enregistré en PNG, le fond blanc rendu transparent.",
    )


class DocumentSignersSerializer(serializers.Serializer):
    """Ce que la Gestion pose sur les documents qu'elle imprime (DOC.1) : adresses servies au
    seul personnel connecté de l'école ; null : ligne à signer à la main."""

    stamp = serializers.CharField(allow_null=True)
    head_name = serializers.CharField()
    head_title = serializers.CharField()
    head_signature = serializers.CharField(allow_null=True)
    signature = serializers.CharField(
        allow_null=True, help_text="Signature du compte connecté dans cette école (Mon compte)."
    )


# Organisation scolaire (C1-C3)


class TermLeafSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=Term.Kind.choices)
    name = serializers.CharField(
        help_text="Vide : l'interface affiche le nom traduit d'après le genre et la place "
        "(« 1re période », « Examens du 1er semestre »)."
    )
    starts_on = serializers.DateField(allow_null=True)
    ends_on = serializers.DateField(allow_null=True)


class TermSerializer(TermLeafSerializer):
    children = TermLeafSerializer(many=True, help_text="Périodes et examens du semestre.")


def term_tree(year: AcademicYear) -> list[dict]:
    """Découpage de l'année en arbre : semestres (ou trimestres) et leurs périodes, dans
    l'ordre."""
    nodes: dict = {}
    roots: list[dict] = []
    for term in year.terms.all():
        node = {
            "id": term.pk,
            "kind": term.kind,
            "name": term.name,
            "starts_on": term.starts_on,
            "ends_on": term.ends_on,
            "children": [],
        }
        nodes[term.pk] = node
        parent = nodes.get(term.parent_id)
        (parent["children"] if parent else roots).append(node)
    return roots


class AcademicYearSerializer(serializers.ModelSerializer):
    terms = serializers.SerializerMethodField(help_text="Découpage de l'année.")

    class Meta:
        model = AcademicYear
        fields = ["id", "name", "starts_on", "ends_on", "is_current", "status", "terms"]
        read_only_fields = fields

    @extend_schema_field(TermSerializer(many=True))
    def get_terms(self, year: AcademicYear) -> list[dict]:
        return TermSerializer(term_tree(year), many=True).data


class AcademicYearCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        help_text="Vide : d'après les dates (« 2026-2027 »).",
    )
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    template = serializers.ChoiceField(
        choices=YearTemplate.choices, default=YearTemplate.SECONDARY, help_text="Découpage (C1)."
    )
    copy_classes_from = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects,
        required=False,
        allow_null=True,
        help_text="Année dont on reprend les classes (sans les titulaires).",
    )
    copy_fees = serializers.BooleanField(
        default=False,
        help_text="Reprendre aussi les barèmes de cette année (droit `finance.configure_fees`).",
    )

    def validate(self, data):
        if data["copy_fees"] and not data.get("copy_classes_from"):
            raise serializers.ValidationError(
                {"copy_fees": _("Choose the school year to copy from.")}, code="no_source_year"
            )
        return data


class AcademicYearUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=20, required=False)
    starts_on = serializers.DateField(required=False)
    ends_on = serializers.DateField(required=False)


class TermInputLeafSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        required=False, allow_null=True, help_text="Élément existant ; absent : nouveau."
    )
    kind = serializers.ChoiceField(choices=Term.Kind.choices)
    name = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    starts_on = serializers.DateField(required=False, allow_null=True, default=None)
    ends_on = serializers.DateField(required=False, allow_null=True, default=None)


class TermInputSerializer(TermInputLeafSerializer):
    children = TermInputLeafSerializer(many=True, required=False, default=list)


class TermsUpdateSerializer(serializers.Serializer):
    """Tout le découpage : ce qui n'y est plus est retiré."""

    terms = TermInputSerializer(many=True, allow_empty=True)

    def nodes(self) -> list[TermNode]:
        def node(data: dict) -> TermNode:
            return TermNode(
                kind=data["kind"],
                name=data["name"],
                starts_on=data["starts_on"],
                ends_on=data["ends_on"],
                id=data.get("id"),
                children=[node(child) for child in data.get("children", [])],
            )

        return [node(item) for item in self.validated_data["terms"]]


class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = ["id", "name", "cycle", "order"]
        read_only_fields = ["id", "order"]


class LevelUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=40, required=False)
    cycle = serializers.ChoiceField(choices=Level.Cycle.choices, required=False)


class LevelReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.UUIDField(), help_text="Tous les niveaux de l'école, dans l'ordre voulu."
    )


class TrackSerializer(serializers.ModelSerializer):
    # Sans le validateur du modèle : tapé en minuscules, le code est d'abord mis en majuscules.
    code = serializers.CharField(
        max_length=10, help_text="Majuscules et chiffres (matricule `{OPT}`)."
    )

    class Meta:
        model = Track
        fields = ["id", "name", "code"]
        read_only_fields = ["id"]

    def validate_code(self, value: str) -> str:
        # Tapé en minuscules : accepté, gardé en majuscules.
        value = value.strip().upper()
        if not re.fullmatch(TRACK_CODE_PATTERN, value):
            raise serializers.ValidationError(
                _("1 to 10 capital letters or digits."), code="invalid_code"
            )
        return value


class TrackUpdateSerializer(TrackSerializer):
    code = serializers.CharField(max_length=10, required=False)

    class Meta(TrackSerializer.Meta):
        extra_kwargs = {"name": {"required": False}}


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "last_name", "middle_name", "first_name"]


class ClassGroupSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True, help_text="« 3e Électricité A ».")
    homeroom_teacher = PersonSerializer(read_only=True, allow_null=True)
    student_count = serializers.IntegerField(
        read_only=True, help_text="Élèves inscrits et actifs (effectif)."
    )

    class Meta:
        model = ClassGroup
        fields = [
            "id",
            "academic_year",
            "level",
            "track",
            "section",
            "name",
            "capacity",
            "student_count",
            "homeroom_teacher",
        ]
        read_only_fields = fields


@extend_schema_field(OpenApiTypes.UUID)
class HomeroomTeacherField(serializers.PrimaryKeyRelatedField):
    """Une personne du personnel actif de l'école de l'adresse : une autre est « introuvable »."""

    def get_queryset(self):
        return organisation.homeroom_candidates()


class ClassGroupUpdateSerializer(serializers.Serializer):
    # Les managers (sans `.all()`) : lus à chaque requête, dans l'école de l'adresse seulement.
    level = serializers.PrimaryKeyRelatedField(queryset=Level.objects, required=False)
    track = serializers.PrimaryKeyRelatedField(
        queryset=Track.objects, required=False, allow_null=True
    )
    section = serializers.CharField(
        max_length=10, required=False, allow_blank=True, help_text="Ex. A ; gardée en majuscules."
    )
    capacity = serializers.IntegerField(
        min_value=1, max_value=1000, required=False, allow_null=True
    )
    homeroom_teacher = HomeroomTeacherField(
        required=False, allow_null=True, help_text="Titulaire (`id` du compte)."
    )


class ClassGroupCreateSerializer(ClassGroupUpdateSerializer):
    academic_year = serializers.PrimaryKeyRelatedField(queryset=AcademicYear.objects)
    level = serializers.PrimaryKeyRelatedField(queryset=Level.objects)


class ClassGroupFilterSerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects, required=False, help_text="Absent : l'année en cours."
    )


class MatriculeFormatInputSerializer(serializers.Serializer):
    matricule_format = serializers.CharField(
        max_length=MAX_MATRICULE_LENGTH,
        help_text="Ex. ABC-{AAAA}-{0000} : {AAAA} ou {AA} (année), {0000} (numéro, 3 à 6 "
        "chiffres), {OPT} (code de l'option).",
    )


class MatriculeFormatSerializer(MatriculeFormatInputSerializer):
    example = serializers.CharField(
        help_text="Prochain matricule : année en cours, première option (C3)."
    )


AUTO_MATRICULE_HELP = (
    "Non : ni l'inscription ni l'import ne donnent de matricule ; l'école garde les siens "
    "(importés ou saisis sur la fiche) ou n'en a pas (C5)."
)


class MatriculeSettingsInputSerializer(MatriculeFormatInputSerializer):
    auto_matricule = serializers.BooleanField(help_text=AUTO_MATRICULE_HELP)


class MatriculeSettingsSerializer(MatriculeFormatSerializer):
    auto_matricule = serializers.BooleanField(help_text=AUTO_MATRICULE_HELP)


# Console de la plateforme (5.2)


class ConsoleSchoolCountsSerializer(serializers.Serializer):
    active = serializers.IntegerField()
    trial = serializers.IntegerField()
    suspended = serializers.IntegerField()
    trial_ending = serializers.IntegerField(help_text="Essais qui finissent dans les 30 jours.")


class ConsoleAmountSerializer(serializers.Serializer):
    currency = serializers.ChoiceField(choices=Currency.choices)
    amount_minor = serializers.IntegerField()


class ConsoleCollectedSerializer(ConsoleAmountSerializer):
    count = serializers.IntegerField()


class ConsoleActiveSchoolSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    status = serializers.ChoiceField(choices=School.Status.choices)
    payments = serializers.IntegerField()
    today = ConsoleAmountSerializer(many=True)


class HealthCheckSerializer(serializers.Serializer):
    name = serializers.ChoiceField(choices=health.CHECKS)
    status = serializers.ChoiceField(choices=health.STATUSES)
    value = serializers.IntegerField(
        allow_null=True,
        help_text="Millisecondes (base, Redis), travailleurs (tâches), pourcentage libre (disque).",
    )


class ServerHealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=health.STATUSES)
    checks = HealthCheckSerializer(many=True)


class PlatformSchedulerSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=health.STATUSES)
    last_tick_at = serializers.DateTimeField(allow_null=True)
    queue_size = serializers.IntegerField(allow_null=True)


class PlatformBackupSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=health.STATUSES)
    done_at = serializers.DateTimeField(allow_null=True)
    copied_status = serializers.ChoiceField(choices=health.STATUSES)
    copied_at = serializers.DateTimeField(allow_null=True)


class PlatformSyncSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    last_sync_at = serializers.DateTimeField(allow_null=True)


class PlatformHealthSerializer(serializers.Serializer):
    scheduler = PlatformSchedulerSerializer()
    backup = PlatformBackupSerializer()
    syncs = PlatformSyncSerializer(many=True)


class ConsoleDashboardSerializer(serializers.Serializer):
    day = serializers.DateField()
    schools = ConsoleSchoolCountsSerializer()
    students = serializers.IntegerField()
    today = ConsoleCollectedSerializer(many=True)
    payments_today = serializers.IntegerField()
    active_schools = ConsoleActiveSchoolSerializer(many=True)
    health = ServerHealthSerializer()
    platform = PlatformHealthSerializer()


class SetupStepSerializer(serializers.Serializer):
    key = serializers.ChoiceField(
        choices=["year", "classes", "fees", "staff", "cash", "students", "prior", "invitations"]
    )
    done = serializers.BooleanField()
    optional = serializers.BooleanField(help_text="Ne retient pas la fin de la liste.")


class SetupSerializer(serializers.Serializer):
    """Liste « Mise en route » (C4) : étapes dans l'ordre ; vide une fois terminée."""

    steps = SetupStepSerializer(many=True)
    ready = serializers.BooleanField(help_text="Toutes les étapes obligatoires sont faites.")
    finished_at = serializers.DateTimeField(allow_null=True)
