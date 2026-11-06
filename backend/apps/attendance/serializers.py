from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.attendance import cards
from apps.attendance.models import IdCard
from apps.schools.models import ClassGroup
from apps.students.models import Enrollment
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
