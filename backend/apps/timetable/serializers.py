from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.core.documents import PAPERS, PrintOptionsSerializer
from apps.timetable import assistant, review
from apps.timetable.checks import LEVELS
from apps.timetable.constraints import UnavailableSerializer, clean
from apps.timetable.models import (
    MAX_LESSON_MINUTES,
    MAX_LESSONS_PER_DAY,
    MAX_RUN_SECONDS,
    MAX_TEACHER_WEEK_HOURS,
    MAX_UNAVAILABLE,
    MIN_LESSON_MINUTES,
    MIN_RUN_SECONDS,
    RUN_SECONDS,
    Room,
    TimeGrid,
    TimeSlot,
    Timetable,
    TimetableEntry,
    TimetableRule,
    TimetableRun,
)
from apps.timetable.prints import KINDS

# 7 jours de 12 heures et 11 récréations au plus.
MAX_SLOTS = 7 * (2 * MAX_LESSONS_PER_DAY - 1)


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ["id", "weekday", "index", "kind", "start", "end"]


class TimeGridSerializer(serializers.ModelSerializer):
    slots = TimeSlotSerializer(many=True, read_only=True)
    lesson_count = serializers.IntegerField(help_text="Heures de cours par semaine (places).")
    class_count = serializers.IntegerField(help_text="Classes de l'année en cours qui la suivent.")

    class Meta:
        model = TimeGrid
        fields = [
            "id",
            "name",
            "lesson_minutes",
            "start_time",
            "is_default",
            "lesson_count",
            "class_count",
            "slots",
        ]


class TimeSlotInputSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=1, max_value=7)
    index = serializers.IntegerField(
        min_value=1,
        max_value=MAX_LESSONS_PER_DAY,
        allow_null=True,
        required=False,
        help_text="Numéro de l'heure dans le jour ; vide pour une récréation.",
    )
    kind = serializers.ChoiceField(choices=TimeSlot.Kind.choices)
    start = serializers.TimeField()
    end = serializers.TimeField()

    def validate(self, attrs: dict) -> dict:
        if attrs["kind"] == TimeSlot.Kind.BREAK:
            attrs["index"] = None
        elif attrs.get("index") is None:
            raise serializers.ValidationError({"index": "Une heure de cours a son numéro."})
        return attrs


class TimeGridWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    lesson_minutes = serializers.IntegerField(
        min_value=MIN_LESSON_MINUTES, max_value=MAX_LESSON_MINUTES
    )
    start_time = serializers.TimeField()
    is_default = serializers.BooleanField(default=False)
    slots = TimeSlotInputSerializer(many=True, max_length=MAX_SLOTS)


class TimeGridCreateSerializer(TimeGridWriteSerializer):
    # Sans valeur : celles de la grille proposée (`services.PRESET_*`, question Q16), posées par
    # la vue.
    lesson_minutes = serializers.IntegerField(
        min_value=MIN_LESSON_MINUTES, max_value=MAX_LESSON_MINUTES, required=False
    )
    start_time = serializers.TimeField(required=False)
    is_default = serializers.BooleanField(required=False)
    slots = TimeSlotInputSerializer(
        many=True,
        max_length=MAX_SLOTS,
        required=False,
        help_text="Sans cases : la semaine proposée, calculée avec cette durée et ce début.",
    )


class TimetableClassSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    time_grid = serializers.UUIDField(allow_null=True, help_text="Vide : grille par défaut.")
    home_room = serializers.UUIDField(allow_null=True)
    course_hours = serializers.IntegerField(help_text="Heures par semaine des cours enseignés.")
    missing_hours = serializers.IntegerField(help_text="Cours enseignés sans heures saisies.")
    capacity = serializers.IntegerField(
        allow_null=True, help_text="Heures de cours de sa grille ; vide sans grille."
    )


class TimetableClassUpdateSerializer(serializers.Serializer):
    time_grid = serializers.UUIDField(allow_null=True, required=False)
    home_room = serializers.UUIDField(allow_null=True, required=False)


class RoomSerializer(serializers.ModelSerializer):
    classes = serializers.SerializerMethodField(
        help_text="Classes de l'année en cours qui y ont leur salle habituelle."
    )

    class Meta:
        model = Room
        fields = ["id", "name", "kind", "capacity", "is_active", "classes"]

    def get_classes(self, room: Room) -> list[str]:
        return [group.name for group in room.current_classes]


class RoomCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    kind = serializers.ChoiceField(choices=Room.Kind.choices)
    capacity = serializers.IntegerField(min_value=1, max_value=500, allow_null=True, required=False)


class RoomUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80, required=False)
    kind = serializers.ChoiceField(choices=Room.Kind.choices, required=False)
    capacity = serializers.IntegerField(min_value=1, max_value=500, allow_null=True, required=False)
    is_active = serializers.BooleanField(required=False)


class TimetableRulesSerializer(serializers.Serializer):
    max_same_course_per_day = serializers.IntegerField(min_value=1, max_value=6)
    teacher_max_day_hours = serializers.IntegerField(min_value=1, max_value=MAX_LESSONS_PER_DAY)
    no_gaps = serializers.BooleanField()
    main_courses_early = serializers.BooleanField()


class TeacherProfileSerializer(serializers.Serializer):
    teacher = serializers.UUIDField(source="teacher_id", read_only=True)
    max_week_hours = serializers.IntegerField(
        min_value=1,
        max_value=MAX_TEACHER_WEEK_HOURS,
        allow_null=True,
        help_text="Charge au plus par semaine (contrat) ; vide : pas de limite.",
    )
    max_day_hours = serializers.IntegerField(
        min_value=1,
        max_value=MAX_LESSONS_PER_DAY,
        allow_null=True,
        help_text="Vide : règle de l'école.",
    )
    unavailable = UnavailableSerializer(many=True, max_length=MAX_UNAVAILABLE)


class CheckIssueSerializer(serializers.Serializer):
    check = serializers.IntegerField(
        help_text=(
            "1 classes, 2 enseignants, 3 cours, 4 salles, 5 cours incomplets, 6 verrous en "
            "conflit, 7 règles qui se contredisent ou sans objet."
        )
    )
    code = serializers.CharField(help_text="Ex. class_overloaded, teacher_over_max.")
    level = serializers.ChoiceField(choices=LEVELS, help_text="error : rouge ; warning : orange.")
    subject = serializers.CharField(
        help_text="Classe, enseignant, cours, salle, ou type de salle (code)."
    )
    values = serializers.DictField(help_text="Chiffres et noms de la phrase.")
    class_group = serializers.UUIDField(allow_null=True)
    teacher = serializers.UUIDField(allow_null=True)
    room = serializers.UUIDField(allow_null=True)
    rule = serializers.UUIDField(allow_null=True, help_text="La règle à modifier (contrôles 6, 7).")
    entry = serializers.UUIDField(allow_null=True, help_text="La séance d'un brouillon (EDT.2a).")


class ChecksSerializer(serializers.Serializer):
    errors = serializers.IntegerField()
    warnings = serializers.IntegerField()
    classes = serializers.IntegerField()
    teachers = serializers.IntegerField()
    rooms = serializers.IntegerField()
    rules = serializers.IntegerField(help_text="Règles actives.")
    issues = CheckIssueSerializer(many=True)


class TimetableRuleSerializer(serializers.ModelSerializer):
    params = serializers.DictField(help_text="Paramètres, selon le kind (spec § 5).")

    class Meta:
        model = TimetableRule
        fields = [
            "id",
            "kind",
            "params",
            "strength",
            "weight",
            "active",
            "source",
            "text",
            "updated_at",
        ]


class TimetableRuleWriteSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TimetableRule.Kind.choices)
    params = serializers.DictField(help_text="Vérifiés par le schéma du kind.")
    strength = serializers.ChoiceField(
        choices=TimetableRule.Strength.choices, required=False, help_text="Vide : celle du kind."
    )
    weight = serializers.IntegerField(
        min_value=1, max_value=10, required=False, help_text="Souhait : 1 à 10 ; vide : du kind."
    )
    active = serializers.BooleanField(default=True)

    def validate(self, attrs: dict) -> dict:
        return clean(attrs)


class RuleKindSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TimetableRule.Kind.choices)
    strengths = serializers.ListField(
        child=serializers.ChoiceField(choices=TimetableRule.Strength.choices)
    )
    strength = serializers.ChoiceField(choices=TimetableRule.Strength.choices)
    weight = serializers.IntegerField()


class RuleCourseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    category = serializers.CharField()
    class_group = serializers.UUIDField()
    class_name = serializers.CharField()
    teacher = serializers.UUIDField(allow_null=True)
    weekly_hours = serializers.IntegerField()
    sessions = serializers.ListField(child=serializers.IntegerField())


class RuleTeacherSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class RuleChoicesSerializer(serializers.Serializer):
    kinds = RuleKindSerializer(many=True)
    courses = RuleCourseSerializer(many=True)
    teachers = RuleTeacherSerializer(many=True)


# Brouillons de l'horaire (EDT.2a)


class DraftSerializer(serializers.ModelSerializer):
    hours = serializers.IntegerField(help_text="Heures placées.")

    class Meta:
        model = Timetable
        fields = ["id", "name", "status", "based_on", "hours", "updated_at"]


class DraftCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    based_on = serializers.UUIDField(
        allow_null=True,
        default=None,
        help_text="Version de l'année à copier (brouillon, publiée, archivée) ; vide : verrous des "
        "règles.",
    )


class VersionSerializer(serializers.ModelSerializer):
    hours = serializers.IntegerField(help_text="Heures placées.")
    published_by = serializers.SerializerMethodField(help_text="Nom de qui l'a publiée.")

    class Meta:
        model = Timetable
        fields = ["id", "name", "status", "valid_from", "published_at", "published_by", "hours"]

    def get_published_by(self, timetable: Timetable) -> str | None:
        return str(timetable.published_by) if timetable.published_by_id else None


class PrintQuerySerializer(PrintOptionsSerializer):
    """Impression de l'horaire (EDT.4c) ; sens habituel : paysage."""

    kind = serializers.ChoiceField(choices=KINDS)
    subject = serializers.UUIDField(
        required=False,
        help_text="La classe, l'enseignant ou la salle ; absent : tous (une page chacun).",
    )
    timetable = serializers.UUIDField(
        required=False,
        help_text="La version (brouillon, publiée ou archivée) ; absent : la publiée.",
    )
    output = serializers.ChoiceField(choices=["pdf", "html"], default="pdf")
    paper = serializers.ChoiceField(
        choices=("a3", *PAPERS), default="a4", help_text="A3 : horaire général sur une seule page."
    )


class PublishSerializer(serializers.Serializer):
    valid_from = serializers.DateField(
        help_text="En vigueur dès ce jour : dans l'année, pas avant la version en vigueur."
    )


class EntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableEntry
        fields = ["id", "course", "weekday", "first", "length", "room", "locked"]


class LeftSerializer(serializers.Serializer):
    course = serializers.UUIDField()
    lengths = serializers.ListField(
        child=serializers.IntegerField(), help_text="Séances restant à placer (heures)."
    )


class ClassLoadSerializer(serializers.Serializer):
    class_group = serializers.UUIDField()
    placed = serializers.IntegerField()
    due = serializers.IntegerField()


class TeacherLoadSerializer(serializers.Serializer):
    teacher = serializers.UUIDField()
    name = serializers.CharField()
    placed = serializers.IntegerField()
    due = serializers.IntegerField()
    max = serializers.IntegerField(allow_null=True, help_text="Maximum de son contrat.")


class DraftStateSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    status = serializers.ChoiceField(choices=Timetable.Status.choices)
    based_on = serializers.UUIDField(allow_null=True)
    can_undo = serializers.BooleanField()
    valid_from = serializers.DateField(
        allow_null=True, help_text="Version publiée : en vigueur dès."
    )
    published_at = serializers.DateTimeField(allow_null=True)
    published_by = serializers.CharField(allow_null=True, help_text="Nom de qui l'a publiée.")
    errors = serializers.IntegerField()
    warnings = serializers.IntegerField()
    entries = EntrySerializer(many=True)
    left = LeftSerializer(many=True)
    classes = ClassLoadSerializer(many=True)
    teachers = TeacherLoadSerializer(many=True)
    issues = CheckIssueSerializer(many=True)


class PlaceSerializer(serializers.Serializer):
    course = serializers.UUIDField()
    weekday = serializers.IntegerField(min_value=1, max_value=7)
    first = serializers.IntegerField(min_value=1, max_value=MAX_LESSONS_PER_DAY)
    length = serializers.IntegerField(min_value=1, max_value=MAX_LESSONS_PER_DAY)


class EntryChangeSerializer(serializers.Serializer):
    """Un seul geste : déplacer (`weekday` et `first`), salle (`room`, vide : à choisir) ou
    verrou (`locked`)."""

    weekday = serializers.IntegerField(min_value=1, max_value=7, required=False)
    first = serializers.IntegerField(min_value=1, max_value=MAX_LESSONS_PER_DAY, required=False)
    room = serializers.UUIDField(allow_null=True, required=False)
    locked = serializers.BooleanField(required=False)

    def validate(self, attrs: dict) -> dict:
        move = "weekday" in attrs or "first" in attrs
        gestures = move + ("room" in attrs) + ("locked" in attrs)
        if gestures != 1 or (move and not ("weekday" in attrs and "first" in attrs)):
            raise serializers.ValidationError(
                _("One change at a time: a move (day and first lesson), a room or the lock."),
                code="one_change",
            )
        return attrs


class SwapSerializer(serializers.Serializer):
    entry = serializers.UUIDField()
    other = serializers.UUIDField()


class TimetableCourseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    category = serializers.CharField()
    class_group = serializers.UUIDField()
    teacher = serializers.UUIDField(allow_null=True)
    teacher_name = serializers.CharField()
    sessions = serializers.ListField(child=serializers.IntegerField())
    room = serializers.UUIDField(allow_null=True)
    room_kind = serializers.CharField()
    spans_break = serializers.BooleanField()
    max_per_day = serializers.IntegerField()


class RunCreateSerializer(serializers.Serializer):
    request_id = serializers.UUIDField(
        help_text="UUID v7 créé par l'écran : la même demande renvoyée ne relance rien."
    )
    timetable = serializers.UUIDField(help_text="Brouillon de départ (il ne change pas).")
    scope = serializers.ChoiceField(
        choices=TimetableRun.Scope.choices, default=TimetableRun.Scope.ALL
    )
    target = serializers.UUIDField(
        allow_null=True, default=None, help_text="Classe ou enseignant recalculé (le reste reste)."
    )
    time_limit = serializers.IntegerField(
        min_value=MIN_RUN_SECONDS, max_value=MAX_RUN_SECONDS, default=RUN_SECONDS
    )


class RunUnmetSerializer(serializers.Serializer):
    code = serializers.CharField(
        help_text="rule (règle `rule`), morning (cours du matin l'après-midi), moved (séance "
        "déplacée par rapport au brouillon de départ)."
    )
    count = serializers.IntegerField()
    rule = serializers.UUIDField(required=False)


class RunBlockingSerializer(serializers.Serializer):
    code = serializers.CharField(
        help_text="rule, absence, teacher_day, course_day, no_gaps, locks, frozen (le reste de "
        "l'horaire gardé tel quel), unit (un cours qui ne tient nulle part)."
    )
    subject = serializers.CharField(required=False, help_text="Règle, enseignant, cours, classe.")
    rule = serializers.UUIDField(required=False)
    kind = serializers.CharField(required=False)
    teacher = serializers.UUIDField(required=False)
    course = serializers.UUIDField(required=False)
    class_group = serializers.UUIDField(required=False)
    values = serializers.DictField(required=False, help_text="Chiffres de la phrase.")


class RunSerializer(serializers.ModelSerializer):
    unmet = RunUnmetSerializer(many=True, help_text="Souhaits non tenus.")
    blocking = RunBlockingSerializer(
        many=True, help_text="Règles qui rendent le calcul impossible."
    )

    class Meta:
        model = TimetableRun
        fields = [
            "id",
            "request_id",
            "timetable",
            "result",
            "status",
            "scope",
            "target",
            "time_limit",
            "created_at",
            "started_at",
            "finished_at",
            "duration_ms",
            "score",
            "unmet",
            "blocking",
            "peak_mb",
        ]


class RunListSerializer(serializers.Serializer):
    time_limit_max = serializers.IntegerField(
        help_text="Temps de calcul le plus long permis à l'école, en secondes (réglé dans la "
        "console)."
    )
    runs = RunSerializer(many=True)


# Lecture de l'horaire publié (EDT.4b)


class ScheduleLessonSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(help_text="1 = lundi … 7 = dimanche.")
    first = serializers.IntegerField(help_text="Numéro de la première heure.")
    length = serializers.IntegerField(help_text="Heures qui se suivent.")
    start = serializers.TimeField(
        allow_null=True, format="%H:%M", help_text="Vide : la grille ne porte plus ces heures."
    )
    end = serializers.TimeField(allow_null=True, format="%H:%M")
    course = serializers.CharField()
    class_group = serializers.CharField()
    teacher = serializers.CharField(help_text="Nom de l'enseignant ; vide sans nom.")
    room = serializers.CharField(help_text="Vide : sans salle.")


class PublishedTimetableSerializer(serializers.Serializer):
    name = serializers.CharField()
    valid_from = serializers.DateField(allow_null=True, help_text="En vigueur dès.")
    published_at = serializers.DateTimeField(allow_null=True)


class HomeroomScheduleSerializer(serializers.Serializer):
    class_group = serializers.CharField()
    lessons = ScheduleLessonSerializer(many=True)


class MyTimetableSerializer(serializers.Serializer):
    timetable = PublishedTimetableSerializer(
        allow_null=True, help_text="Vide : aucun horaire publié cette année."
    )
    lessons = ScheduleLessonSerializer(many=True, help_text="Séances du compte.")
    homeroom = HomeroomScheduleSerializer(
        allow_null=True, help_text="Classe dont le compte est titulaire cette année."
    )


class AssistAskSerializer(serializers.Serializer):
    request_id = serializers.UUIDField(
        help_text="Fabriqué par l'écran : le même clic ne coûte qu'une fois."
    )
    text = serializers.CharField(max_length=assistant.TEXT_MAX, trim_whitespace=True)


class AssistProposalSerializer(serializers.Serializer):
    sentence = serializers.CharField()
    rule = TimetableRuleWriteSerializer(allow_null=True, help_text="Vide : pas compris (`reason`).")
    reason = serializers.CharField(allow_blank=True)


class AssistCallSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    state = serializers.CharField(
        help_text="queued, running, done, error, refused, kept, abandoned."
    )
    refusal = serializers.CharField(allow_blank=True, help_text="Code du refus ou de l'erreur.")
    proposals = AssistProposalSerializer(many=True, allow_null=True)


class AssistKeepItemSerializer(serializers.Serializer):
    sentence = serializers.CharField(max_length=assistant.SENTENCE_MAX)
    rule = TimetableRuleWriteSerializer()


class AssistKeepSerializer(serializers.Serializer):
    items = AssistKeepItemSerializer(many=True, min_length=1, max_length=20)


class ReviewAskSerializer(serializers.Serializer):
    request_id = serializers.UUIDField(
        help_text="Fabriqué par l'écran : le même clic ne coûte qu'une fois."
    )
    timetable = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Horaire calculé à analyser ; absent : le diagnostic de l'année.",
    )


class ReviewActionSerializer(serializers.Serializer):
    key = serializers.CharField(help_text="`kind:identifiant`, à renvoyer pour appliquer.")
    kind = serializers.ChoiceField(choices=review.KINDS)
    id = serializers.UUIDField(allow_null=True, help_text="Règle ou cours visé.")
    label = serializers.CharField(allow_blank=True)
    pattern = serializers.CharField(required=False, help_text="Séances proposées (set_pattern).")
    note = serializers.CharField(allow_blank=True)


class ReviewProposalSerializer(serializers.Serializer):
    explanation = serializers.CharField(allow_blank=True)
    actions = ReviewActionSerializer(many=True)


class ReviewCallSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    state = serializers.CharField(
        help_text="queued, running, done, error, refused, kept, abandoned."
    )
    refusal = serializers.CharField(allow_blank=True, help_text="Code du refus ou de l'erreur.")
    proposal = ReviewProposalSerializer(allow_null=True)


class ReviewApplySerializer(serializers.Serializer):
    key = serializers.CharField(max_length=80)


class ReviewFinishSerializer(serializers.Serializer):
    applied = serializers.BooleanField()
