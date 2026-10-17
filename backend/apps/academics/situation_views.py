"""Situations de fin d'année imprimables (8.4.4) : d'une classe et de toute l'école, au critère
choisi à chaque édition. Droit `grades.validate` (direction des études) ; options d'impression de
8.3.4 ; chaque PDF est noté au journal (il contient les résultats d'élèves)."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.academics import situations
from apps.accounts.permissions import HasSchoolPermission
from apps.accounts.roles import GRADES_VALIDATE
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import (
    PRINT_RESPONSE,
    PrintOptionsSerializer,
    print_options,
    render,
    school_header,
)
from apps.core.errors import ErrorSerializer
from apps.core.tenancy import require_current_school
from apps.schools import organisation
from apps.schools.models import ClassGroup

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
COURSES, RANKING, MATRICULE, DEVIATIONS = "courses", "ranking", "matricule", "deviations"


class SituationPrintSerializer(PrintOptionsSerializer):
    criterion = serializers.ChoiceField(
        choices=situations.CRITERIA,
        default=situations.RULES,
        help_text="`rules` : décision de la délibération (repêchage compris) ; `average` : "
        "moyenne seule, 50 % de l'année et plus.",
    )
    columns = serializers.MultipleChoiceField(
        choices=[COURSES, RANKING, MATRICULE, DEVIATIONS],
        required=False,
        help_text="Parties à imprimer (paramètre répété) : classe, `courses` (par cours), "
        "`ranking` (palmarès), `matricule` ; école, `deviations` (liste des écarts).",
    )
    output = serializers.ChoiceField(choices=["pdf", "html"], default="pdf")


class _View(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = GRADES_VALIDATE

    def options(self, request: Request) -> dict:
        params = SituationPrintSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return params.validated_data

    def answer(self, request, data, context, label, name) -> HttpResponse:
        if data["output"] == "pdf":
            audit.record(
                Action.GRADES_SITUATION_PRINTED,
                context.get("class_group"),
                actor=request.user,
                label=label,
            )
        context = {**school_header(require_current_school()), **context}
        return render(
            "academics/situation.html",
            context,
            data["output"],
            f"{name}.pdf",
            print_options(data, "portrait"),
        )


@extend_schema(tags=["deliberation"])
class ClassSituationView(_View):
    @extend_schema(
        parameters=[SituationPrintSerializer],
        responses={**PRINT_RESPONSE, 400: ErrorSerializer, **ERRORS},
    )
    def get(self, request: Request, pk) -> HttpResponse:
        """Situation d'une classe en PDF ou en aperçu HTML : inscrits, abandons, délibérés,
        admis, repêchage, doublants, réorientés, exclus, taux, écarts ; par cours et palmarès au
        choix. Dernière proclamation figée, sinon la délibération en cours (« provisoire »)."""
        data = self.options(request)
        group = get_object_or_404(
            ClassGroup.objects.select_related("academic_year", "level", "track"), pk=pk
        )
        columns = data.get("columns", set())
        context = situations.class_situation(
            group,
            data["criterion"],
            courses=COURSES in columns,
            ranking=RANKING in columns,
        )
        context.update(kind="class", class_group=group, year=group.academic_year, columns=columns)
        return self.answer(
            request,
            data,
            context,
            f"{group.name} · {data['criterion']}",
            f"situation-{slugify(group.name)}",
        )


@extend_schema(tags=["deliberation"])
class SchoolSituationView(_View):
    @extend_schema(
        parameters=[SituationPrintSerializer],
        responses={**PRINT_RESPONSE, 400: ErrorSerializer, **ERRORS},
    )
    def get(self, request: Request) -> HttpResponse:
        """Situation de l'école pour l'année en cours, en PDF ou en aperçu HTML : lauréat et sa
        classe, par classe (taux, écarts, meilleur élève), sous-totaux par niveau et total ; les
        classes pas encore proclamées restent hors des totaux. Liste des écarts au choix."""
        data = self.options(request)
        year = organisation.current_year()
        context = (
            situations.school_situation(year, data["criterion"])
            if year
            else {"criterion": data["criterion"], "levels": [], "total": situations.Counts()}
        )
        context.update(kind="school", year=year, columns=data.get("columns", set()))
        return self.answer(
            request,
            data,
            context,
            f"{year.name if year else ''} · {data['criterion']}",
            "situation-ecole",
        )
