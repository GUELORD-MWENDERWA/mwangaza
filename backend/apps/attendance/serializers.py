from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Membership
from apps.attendance import cards
from apps.attendance.cards import staff
from apps.attendance.models import AbsenceJustification, AttendanceCorrection, IdCard
from apps.schools.models import ClassGroup
from apps.students.models import Enrollment, Student
from apps.students.serializers import photo_url


class CardSerializer(serializers.ModelSerializer):
    """Carte, sans jamais son jeton (le serveur ne l'a pas) : ses 4 derniers signes."""

    issued_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = IdCard
        fields = ["id", "last4", "issued_at", "valid_until", "revoked_at", "revoke_reason"]
        read_only_fields = fields


def _cards(person) -> tuple[IdCard | None, IdCard | None]:
    """Carte active et dernière carte révoquée, depuis `cards` préchargées (plus récente
    d'abord)."""
    found = list(person.cards.all())
    current = next((card for card in found if card.revoked_at is None), None)
    revoked = next((card for card in found if card.revoked_at is not None), None)
    return current, revoked


class _HolderSerializer(serializers.Serializer):
    card = serializers.SerializerMethodField(help_text="Carte active ; null sans carte.")
    last_revoked = serializers.SerializerMethodField(
        help_text="Dernière carte révoquée (perdue, remplacée, départ) ; null sinon."
    )

    def person(self, instance):
        raise NotImplementedError

    @extend_schema_field(CardSerializer(allow_null=True))
    def get_card(self, instance) -> dict | None:
        current, _revoked = _cards(self.person(instance))
        return CardSerializer(current).data if current else None

    @extend_schema_field(CardSerializer(allow_null=True))
    def get_last_revoked(self, instance) -> dict | None:
        _current, revoked = _cards(self.person(instance))
        return CardSerializer(revoked).data if revoked else None


class CardStudentSerializer(_HolderSerializer):
    """Élève inscrit de l'année et sa carte (écran « Cartes », onglet Élèves)."""

    student = serializers.UUIDField(source="student_id")
    name = serializers.CharField(source="student.full_name")
    matricule = serializers.CharField(source="student.matricule")
    class_group = serializers.UUIDField(source="class_group_id")
    class_name = serializers.CharField(source="class_group.name")
    photo = serializers.SerializerMethodField(help_text="Photo seulement avec le consentement.")

    def person(self, instance):
        return instance.student

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_photo(self, instance: Enrollment) -> str | None:
        return photo_url(instance.student) if instance.student.photo_consent else None


class CardStaffSerializer(_HolderSerializer):
    """Membre du personnel et sa carte (onglet Personnel)."""

    member = serializers.UUIDField(source="pk")
    name = serializers.CharField(source="user.get_full_name")
    roles = serializers.SerializerMethodField()

    def person(self, instance):
        return instance

    def get_roles(self, instance) -> list[str]:
        return sorted(role.name for role in instance.roles.all())


class CardListQuerySerializer(serializers.Serializer):
    class_group = serializers.PrimaryKeyRelatedField(
        queryset=ClassGroup.objects, required=False, help_text="Élèves d'une classe."
    )
    search = serializers.CharField(required=False, max_length=80, help_text="Nom ou matricule.")
    card = serializers.ChoiceField(
        choices=[("active", "active"), ("none", "none")],
        required=False,
        help_text="active : avec une carte active ; none : sans carte.",
    )


class CardSummarySerializer(serializers.Serializer):
    students = serializers.IntegerField(help_text="Élèves inscrits dans l'année en cours.")
    active = serializers.IntegerField(help_text="Élèves inscrits qui ont une carte active.")
    missing = serializers.IntegerField(help_text="Élèves inscrits sans carte.")
    lost_this_year = serializers.IntegerField(help_text="Cartes perdues depuis la rentrée.")


class CardPrintSerializer(serializers.Serializer):
    """Une seule façon de choisir : une sélection (`students`, `members`), une classe
    (`class_group`, avec `missing_only`), ou les personnes sans carte (`missing`)."""

    students = serializers.ListField(
        child=serializers.UUIDField(), max_length=cards.MAX_PER_PRINT, default=list
    )
    members = serializers.ListField(
        child=serializers.UUIDField(),
        max_length=cards.MAX_PER_PRINT,
        default=list,
        help_text="Membres du personnel (`member` de la liste du personnel).",
    )
    class_group = serializers.PrimaryKeyRelatedField(queryset=ClassGroup.objects, required=False)
    missing_only = serializers.BooleanField(
        default=False, help_text="Avec `class_group` : seulement les élèves sans carte."
    )
    missing = serializers.ChoiceField(
        choices=[("students", "students"), ("staff", "staff")],
        required=False,
        help_text=f"Les {cards.MAX_PER_PRINT} premiers sans carte ; `remaining` : les autres.",
    )
    layout = serializers.ChoiceField(
        choices=[(cards.SHEET, "A4 sheet of 10"), (cards.CARD, "one card per page")],
        default=cards.SHEET,
    )

    def validate(self, data):
        modes = [
            bool(data["students"] or data["members"]),
            "class_group" in data,
            "missing" in data,
        ]
        if sum(modes) != 1:
            raise serializers.ValidationError(
                _("Choose people, a class, or the people without a card.")
            )
        return data


class CardPrintResultSerializer(serializers.Serializer):
    issued = serializers.IntegerField(help_text="Cartes émises (les anciennes sont remplacées).")
    remaining = serializers.IntegerField(help_text="Personnes encore sans carte (`missing`).")
    url = serializers.CharField(help_text="Adresse du PDF à ouvrir tout de suite (10 minutes).")


class CardRevokeSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(
        choices=[(IdCard.RevokeReason.LOST, "lost"), (IdCard.RevokeReason.LEFT, "left")]
    )


class RosterQuerySerializer(serializers.Serializer):
    after = serializers.UUIDField(required=False, help_text="`next` de la page précédente.")
    version = serializers.CharField(
        required=False, max_length=32, help_text="Version déjà sur l'appareil."
    )


class RosterStudentSerializer(serializers.Serializer):
    student = serializers.UUIDField(source="student_id")
    name = serializers.CharField(source="student.full_name")
    matricule = serializers.CharField(source="student.matricule")
    class_name = serializers.CharField(source="class_group.name")
    card_hash = serializers.CharField(help_text="Empreinte SHA-256 du jeton ; vide sans carte.")
    card_last4 = serializers.CharField()
    photo = serializers.SerializerMethodField(help_text="Photo seulement avec le consentement.")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_photo(self, instance: Enrollment) -> str | None:
        return photo_url(instance.student) if instance.student.photo_consent else None


class RosterStaffSerializer(serializers.Serializer):
    member = serializers.UUIDField(source="pk")
    name = serializers.CharField(source="user.get_full_name")
    card_hash = serializers.CharField()
    card_last4 = serializers.CharField()


class RosterSerializer(serializers.Serializer):
    """Liste gardée par l'appareil de pointage pour décider seul, même sans réseau."""

    version = serializers.CharField(help_text="À renvoyer : rien n'est envoyé s'il n'a pas changé.")
    unchanged = serializers.BooleanField()
    students = RosterStudentSerializer(many=True)
    staff = RosterStaffSerializer(many=True, help_text="Première page seulement.")
    next = serializers.UUIDField(allow_null=True, help_text="Page suivante (`after`).")


# Suivi (6.5)

# Choix nommés une fois (`ENUM_NAME_OVERRIDES`) : état d'un absent, état d'une personne un jour.
ABSENCE_STATES = [
    ("absent", _("Absent")),
    ("pending", _("Justification pending")),
    ("justified", _("Justified")),
]
DAY_STATUSES = AttendanceCorrection.Status.choices


class DayQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=False, help_text="Jour suivi ; vide : aujourd'hui.")


class AbsencesQuerySerializer(DayQuerySerializer):
    class_group = serializers.PrimaryKeyRelatedField(queryset=ClassGroup.objects, required=False)
    state = serializers.ChoiceField(
        choices=ABSENCE_STATES,
        required=False,
        help_text="Vide : tous les absents (justifiés compris).",
    )


class PeriodQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    class_group = serializers.PrimaryKeyRelatedField(queryset=ClassGroup.objects, required=False)

    def validate(self, data):
        if data["date_from"] > data["date_to"]:
            raise serializers.ValidationError(_("The start comes after the end."))
        if (data["date_to"] - data["date_from"]).days > 366:
            raise serializers.ValidationError(_("Choose one school year at most."))
        return data


class CorrectionQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class DayClassSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    enrolled = serializers.IntegerField()
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    absent = serializers.IntegerField(help_text="Absents, justifiés compris.")
    justified = serializers.IntegerField()


class DaySerializer(serializers.Serializer):
    """Un jour à l'entrée : compteurs de l'école, du personnel et de chaque classe."""

    date = serializers.DateField()
    school_day = serializers.BooleanField(
        help_text="Faux : personne n'a pointé ce jour-là, ou congé ; aucun absent."
    )
    holiday = serializers.BooleanField()
    enrolled = serializers.IntegerField()
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    absent = serializers.IntegerField(help_text="Absents, justifiés compris.")
    justified = serializers.IntegerField()
    pending = serializers.IntegerField(help_text="Absents dont la justification est en attente.")
    rate = serializers.IntegerField(allow_null=True, help_text="Présents et retards, en %.")
    staff_present = serializers.IntegerField(help_text="Personnel arrivé (retards compris).")
    staff_total = serializers.IntegerField()
    late_after = serializers.CharField(help_text="Heure limite d'arrivée de l'école (HH:MM).")
    parents_notified_at = serializers.DateTimeField(
        allow_null=True, help_text="Heure où les parents des absents ont été prévenus ce jour-là."
    )
    alert_after = serializers.IntegerField(help_text="Seuil d'alerte ; 0 : aucune alerte.")
    classes = DayClassSerializer(many=True)


class AbsenceSerializer(serializers.Serializer):
    student_id = serializers.UUIDField(source="student.id")
    name = serializers.CharField(source="student.full_name")
    matricule = serializers.CharField(source="student.matricule")
    class_name = serializers.CharField(source="class_group.name")
    state = serializers.ChoiceField(choices=ABSENCE_STATES)
    unjustified = serializers.IntegerField(
        help_text="Absences non justifiées depuis le début de l'année (ce jour compris)."
    )
    parent_on_portal = serializers.BooleanField(
        help_text="Faux : la famille n'a pas de compte du Portail, il faut l'appeler."
    )
    justification_id = serializers.UUIDField(
        allow_null=True, help_text="Justification qui couvre ce jour (en attente ou acceptée)."
    )


class StaffDaySerializer(serializers.Serializer):
    member_id = serializers.UUIDField(source="id")
    name = serializers.CharField(source="user.get_full_name")
    status = serializers.ChoiceField(choices=DAY_STATUSES)
    seen_at = serializers.DateTimeField(allow_null=True, help_text="Heure du passage, s'il y en a.")


class CorrectionSerializer(serializers.ModelSerializer):
    """Ligne du journal des corrections."""

    date = serializers.DateField(source="session.date", read_only=True)
    student = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects, required=False, allow_null=True
    )
    member = serializers.PrimaryKeyRelatedField(
        queryset=Membership.objects, required=False, allow_null=True
    )
    name = serializers.SerializerMethodField()
    author = serializers.CharField(source="created_by.get_full_name", read_only=True)

    class Meta:
        model = AttendanceCorrection
        fields = [
            "id",
            "date",
            "student",
            "member",
            "name",
            "status",
            "previous_status",
            "reason",
            "author",
            "created_at",
        ]
        read_only_fields = ["id", "previous_status", "created_at"]

    def get_name(self, correction) -> str:
        return str(correction.student or correction.member.user)


@extend_schema_field(OpenApiTypes.UUID)
class StaffField(serializers.PrimaryKeyRelatedField):
    """Membre actif du personnel de l'école courante, lu à la validation (`Membership` n'est
    pas limité à une école tout seul)."""

    def get_queryset(self):
        return staff()


class CorrectionWriteSerializer(serializers.Serializer):
    """Une personne (élève ou membre du personnel), un jour de classe, le nouvel état."""

    date = serializers.DateField()
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects, required=False)
    member = StaffField(required=False)
    status = serializers.ChoiceField(choices=AttendanceCorrection.Status.choices)
    reason = serializers.CharField(max_length=200)

    def validate(self, data):
        if ("student" in data) == ("member" in data):
            raise serializers.ValidationError(_("Choose one student or one staff member."))
        return data


class JustificationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    has_document = serializers.SerializerMethodField()
    decided_by_name = serializers.CharField(
        source="decided_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = AbsenceJustification
        fields = [
            "id",
            "student",
            "student_name",
            "starts_on",
            "ends_on",
            "reason",
            "source",
            "status",
            "has_document",
            "decided_at",
            "decided_by_name",
            "decision_note",
            "created_at",
        ]
        read_only_fields = fields

    def get_has_document(self, justification) -> bool:
        return bool(justification.document)


class JustificationQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=AbsenceJustification.Status.choices, required=False)
    student = serializers.UUIDField(required=False)


class JustificationWriteSerializer(serializers.Serializer):
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    reason = serializers.CharField(max_length=300)
    document = serializers.FileField(
        required=False, help_text="Certificat : photo ou PDF, 5 Mo au plus."
    )


class SchoolJustificationSerializer(JustificationWriteSerializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects)


class JustificationDecisionSerializer(serializers.Serializer):
    accept = serializers.BooleanField()
    note = serializers.CharField(
        max_length=300, required=False, default="", allow_blank=True, help_text="Réponse au parent."
    )


# Portail (6.6)


class ChildTotalsSerializer(serializers.Serializer):
    days = serializers.IntegerField(help_text="Jours de classe depuis l'inscription.")
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    absent = serializers.IntegerField()
    justified = serializers.IntegerField()
    pending = serializers.IntegerField()
    rate = serializers.IntegerField(allow_null=True)


class ChildAbsenceSerializer(serializers.Serializer):
    date = serializers.DateField()
    state = serializers.ChoiceField(choices=ABSENCE_STATES)


class PortalJustificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbsenceJustification
        fields = ["id", "starts_on", "ends_on", "reason", "status", "decision_note", "created_at"]
        read_only_fields = fields


class ChildAttendanceSerializer(serializers.Serializer):
    """Présences de l'année d'un enfant : totaux, absences récentes (60 au plus), justifications
    envoyées (20 au plus)."""

    class_group = serializers.CharField()
    totals = ChildTotalsSerializer()
    absences = ChildAbsenceSerializer(many=True)
    justifications = PortalJustificationSerializer(many=True)
