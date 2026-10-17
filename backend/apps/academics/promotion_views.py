"""API du passage de classe (8.4.5) : résumé par classe de l'année finie, élèves d'une classe
(décision figée, place proposée, réponse du parent, inscription de l'année suivante), et trois
actions en lot : proposer, retirer, inscrire. Droit : `students.edit` (secrétariat, direction),
module `academics` ; comme partout, le serveur vérifie."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import promotion
from apps.academics.models import DeliberationDecision, PlaceConfirmation
from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import STUDENTS_EDIT
from apps.core.errors import ErrorSerializer
from apps.schools.models import ClassGroup

ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}


class YearSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    starts_on = serializers.DateField()


class ClassRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class CountsSerializer(serializers.Serializer):
    students = serializers.IntegerField(default=0)
    offered = serializers.IntegerField(default=0, help_text="Places proposées, pas inscrites.")
    yes = serializers.IntegerField(default=0, help_text="Le parent a répondu : revient.")
    no = serializers.IntegerField(default=0, help_text="Le parent a répondu : ne revient pas.")
    no_answer = serializers.IntegerField(default=0)
    enrolled = serializers.IntegerField(default=0, help_text="Inscrits l'année suivante.")


class ClassSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(source="group.pk")
    name = serializers.CharField(source="group.name")
    proclaimed_on = serializers.DateField(
        allow_null=True, help_text="Date de la dernière proclamation ; vide : pas proclamée."
    )
    counts = CountsSerializer()


class PromotionSerializer(serializers.Serializer):
    year = YearSerializer(allow_null=True, help_text="Année finie.")
    following = YearSerializer(allow_null=True, help_text="Année suivante ; vide : à créer.")
    classes = ClassSummarySerializer(many=True)


class PlaceSerializer(serializers.Serializer):
    class_group = serializers.UUIDField(source="class_group.pk")
    class_name = serializers.CharField(source="class_group.name")
    status = serializers.ChoiceField(choices=PlaceConfirmation.Status.choices)
    answer = serializers.ChoiceField(choices=[*PlaceConfirmation.Answer.values, ""])
    answered_at = serializers.DateTimeField(allow_null=True)


class PassageRowSerializer(serializers.Serializer):
    enrollment = serializers.UUIDField(source="enrollment.pk")
    student = serializers.UUIDField(source="enrollment.student_id")
    full_name = serializers.CharField(source="enrollment.student.full_name")
    matricule = serializers.CharField(source="enrollment.student.matricule")
    decision = serializers.ChoiceField(
        choices=[*DeliberationDecision.Decision.values, ""],
        help_text="Décision de la dernière proclamation ; vide : pas encore proclamée.",
    )
    percent = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    proposal = serializers.ChoiceField(choices=promotion.PROPOSALS)
    proposed_class = serializers.UUIDField(
        source="proposed_class.pk", allow_null=True, help_text="Vide : à choisir ou sans place."
    )
    place = PlaceSerializer(allow_null=True)
    enrolled_class = serializers.CharField(
        source="enrolled_class.name",
        allow_null=True,
        help_text="Classe de l'inscription de l'année suivante, si elle existe.",
    )
    on_portal = serializers.BooleanField(help_text="La famille a un compte du Portail actif.")


class ClassPassageSerializer(serializers.Serializer):
    class_name = serializers.CharField(source="group.name")
    year = YearSerializer()
    following = YearSerializer(allow_null=True)
    proclaimed_on = serializers.DateField(allow_null=True)
    targets = ClassRefSerializer(many=True, help_text="Classes de l'année suivante.")
    counts = CountsSerializer()
    students = PassageRowSerializer(many=True, source="rows")


class OfferItemSerializer(serializers.Serializer):
    enrollment = serializers.UUIDField()
    class_group = serializers.UUIDField(help_text="Classe de l'année suivante.")


class OfferSerializer(serializers.Serializer):
    places = OfferItemSerializer(many=True, allow_empty=False, max_length=500)


class EnrollmentsSerializer(serializers.Serializer):
    enrollments = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, max_length=500
    )


class _View(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = STUDENTS_EDIT


def _answer(group: ClassGroup) -> Response:
    return Response(ClassPassageSerializer(promotion.class_passage(group)).data)


def _group(pk) -> ClassGroup:
    return get_object_or_404(ClassGroup.objects.select_related("level", "track"), pk=pk)


@extend_schema(tags=["promotion"])
class PromotionView(_View):
    @extend_schema(responses={200: PromotionSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Classes de l'année finie : proclamée ou non, élèves, places proposées et réponses,
        inscrits l'année suivante. Année finie = la dernière qui a une année suivante, sans
        dépasser l'année en cours."""
        year, following = promotion.years()
        classes = promotion.summary(year, following) if year else []
        return Response(
            PromotionSerializer({"year": year, "following": following, "classes": classes}).data
        )


@extend_schema(tags=["promotion"])
class ClassPromotionView(_View):
    @extend_schema(responses={200: ClassPassageSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Élèves de la classe : décision figée, place proposée d'après elle, place déjà proposée
        et réponse du parent, inscription de l'année suivante."""
        return _answer(_group(pk))


@extend_schema(tags=["promotion"])
class OfferPlacesView(_View):
    @extend_schema(request=OfferSerializer, responses={200: ClassPassageSerializer, **ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Propose (ou change) la place de ces élèves ; le parent la voit au Portail et en est
        prévenu. Admis, doublant ou réorienté seulement."""
        group = _group(pk)
        data = OfferSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        places = data.validated_data["places"]
        choices = {item["enrollment"]: item["class_group"] for item in places}
        promotion.offer(group, choices, actor=request.user)
        return _answer(group)


@extend_schema(tags=["promotion"])
class WithdrawPlacesView(_View):
    @extend_schema(request=EnrollmentsSerializer, responses={200: ClassPassageSerializer, **ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Retire les places encore proposées de ces élèves."""
        group = _group(pk)
        data = EnrollmentsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        promotion.withdraw(group, data.validated_data["enrollments"], actor=request.user)
        return _answer(group)


@extend_schema(tags=["promotion"])
class EnrollPlacesView(_View):
    @extend_schema(request=EnrollmentsSerializer, responses={200: ClassPassageSerializer, **ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Inscrit l'année suivante, dans la classe proposée, les élèves dont la place est
        proposée : frais dus d'après les barèmes de cette année-là, matricule gardé."""
        group = _group(pk)
        data = EnrollmentsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        promotion.enroll(group, data.validated_data["enrollments"], actor=request.user)
        return _answer(group)
