"""API de la délibération d'une classe (8.4.2, NB.5) : tableau de chaque session (période,
semestre ou trimestre, fin d'année), date, conseil (présents, président, secrétaire,
observations), décision d'un élève et application des propositions (fin d'année), proclamation,
réouverture et procès-verbal ; reprise des résultats d'une année sans notes, importés d'un fichier
(8.4.7).

Secret des délibérations (NB.5) : le tableau et le procès-verbal ne se lisent que par les membres
du conseil (droit `grades.validate`, titulaire, enseignants de la classe : 403 `not_a_member`
pour tout autre compte) ; tout le reste demande `grades.validate`. Comme partout, le serveur
vérifie."""

from collections import Counter
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics import council, deliberation, prior_results, resits
from apps.academics.grades import term_label
from apps.academics.models import Deliberation, DeliberationDecision
from apps.accounts.permissions import HasSchoolPermission, school_access
from apps.accounts.roles import GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import (
    PRINT_RESPONSE,
    XLSX,
    XLSX_RESPONSE,
    PrintOptionsSerializer,
    file_response,
    print_options,
    render,
    school_header,
)
from apps.core.errors import BusinessError, ErrorSerializer
from apps.core.tenancy import require_current_school
from apps.schools.models import ClassGroup, Term
from apps.students.models import Enrollment

ERRORS = {400: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}
DECISIONS = DeliberationDecision.Decision.values
OUTCOMES = [
    "passed",
    "resit",
    "failed",
    "incomplete",
    "unranked",
    "orient",
    "exclude",
]
# Lire le tableau : tout compte qui peut être membre du conseil ; `council.check_member` tranche.
COUNCIL_READ = (GRADES_ENTER, GRADES_ENTER_ANY, GRADES_VALIDATE)
KINDS = ["year", "second", Term.Kind.PERIOD, Term.Kind.SEMESTER, Term.Kind.TRIMESTER]


class ResitLineSerializer(serializers.Serializer):
    course = serializers.CharField()
    percent = serializers.DecimalField(max_digits=5, decimal_places=1, help_text="Année du cours.")
    resit_percent = serializers.DecimalField(
        max_digits=5, decimal_places=1, allow_null=True, help_text="Vide : note attendue."
    )
    passed = serializers.BooleanField(allow_null=True)


class RowSerializer(serializers.Serializer):
    enrollment = serializers.UUIDField(source="enrollment.pk")
    full_name = serializers.CharField(source="enrollment.student.full_name")
    percent = serializers.DecimalField(
        max_digits=5, decimal_places=1, allow_null=True, help_text="Pourcentage de l'année."
    )
    outcome = serializers.ChoiceField(choices=OUTCOMES, help_text="Issue des règles (8.4.1).")
    proposed = serializers.CharField(
        help_text="Décision proposée (mêmes valeurs que `decision`) ; vide sans proposition."
    )
    rule = serializers.ChoiceField(
        choices=resits.RULES, help_text="Règle du règlement de l'école qui donne la proposition."
    )
    rule_params = serializers.DictField(
        help_text="Valeurs citées avec la règle (percent, threshold, count, max, courses, age…)."
    )
    decision = serializers.ChoiceField(
        choices=[*DECISIONS, ""], help_text="Vide : pas encore prise."
    )
    reason = serializers.CharField()
    deviates = serializers.BooleanField(help_text="La décision diffère de la proposition.")
    resits = ResitLineSerializer(many=True, help_text="Seconde session : cours repassés.")


class SessionResultSerializer(serializers.Serializer):
    enrollment = serializers.UUIDField(source="enrollment.pk")
    full_name = serializers.CharField(source="enrollment.student.full_name")
    percent = serializers.DecimalField(
        max_digits=5, decimal_places=1, allow_null=True, source="total.percent"
    )
    place = serializers.IntegerField(allow_null=True, source="total.place")
    conduct = serializers.CharField(help_text="Cote de conduite retenue (période) ; vide sinon.")
    application = serializers.CharField(help_text="Cote d'application (période) ; vide sinon.")
    passed = serializers.BooleanField(help_text="Pourcentage au seuil de passage au moins.")


class ProclamationSerializer(serializers.Serializer):
    version = serializers.IntegerField()
    held_on = serializers.DateField()
    proclaimed_at = serializers.DateTimeField()
    proclaimed_by = serializers.CharField(source="proclaimed_by.get_full_name")
    reason = serializers.CharField()


class MemberSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    direction = serializers.BooleanField(help_text="Valide les notes (direction des études).")
    homeroom = serializers.BooleanField(help_text="Titulaire de la classe.")
    courses = serializers.ListField(
        child=serializers.CharField(), help_text="Cours qu'il donne dans la classe."
    )
    present = serializers.BooleanField()


class CouncilSerializer(serializers.Serializer):
    members = MemberSerializer(many=True)
    chair = serializers.UUIDField(allow_null=True, help_text="Président de séance.")
    secretary = serializers.UUIDField(allow_null=True, help_text="Secrétaire de séance.")
    remarks = serializers.CharField(help_text="Observations du conseil.")


class SessionStateSerializer(serializers.Serializer):
    term = serializers.UUIDField(source="term_id", allow_null=True, help_text="Vide : fin d'année.")
    second_session = serializers.BooleanField()
    status = serializers.ChoiceField(choices=Deliberation.Status.choices)
    version = serializers.IntegerField()


class ClassDeliberationSerializer(serializers.Serializer):
    class_name = serializers.CharField()
    term = serializers.UUIDField(allow_null=True, help_text="Session ; vide : fin d'année.")
    kind = serializers.ChoiceField(choices=KINDS)
    can_edit = serializers.BooleanField(
        help_text="Droit `grades.validate` ; sinon lecture seule (membre du conseil)."
    )
    status = serializers.ChoiceField(choices=Deliberation.Status.choices)
    held_on = serializers.DateField(allow_null=True)
    version = serializers.IntegerField(help_text="Dernière version proclamée (0 : aucune).")
    ready = serializers.BooleanField(
        help_text="Période ou semestre : bulletins dits prêts par le titulaire ; "
        "fin d'année : vrai."
    )
    pass_percent = serializers.IntegerField(
        allow_null=True, help_text="Seuil de passage (période ou semestre)."
    )
    counts = serializers.DictField(child=serializers.IntegerField())
    deviations = serializers.IntegerField()
    latest = ProclamationSerializer(allow_null=True, help_text="Dernière proclamation figée.")
    students = RowSerializer(many=True, help_text="Fin d'année : décisions ; vide sinon.")
    results = SessionResultSerializer(many=True, help_text="Période ou semestre ; vide sinon.")
    council = CouncilSerializer()
    sessions = SessionStateSerializer(many=True, help_text="État de chaque session ouverte.")
    has_second_session = serializers.BooleanField(
        help_text="La dernière proclamation de fin d'année envoie des élèves au repêchage."
    )
    exam_on = serializers.DateField(
        allow_null=True, help_text="Seconde session : date de l'examen de repêchage."
    )


class SessionQuerySerializer(serializers.Serializer):
    term = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Session : une période, un semestre ou un trimestre ; absente : fin d'année.",
    )
    second = serializers.BooleanField(
        default=False, help_text="Seconde session (NB.6), sans `term`."
    )


def _session(request: Request, group: ClassGroup) -> tuple[Term | None, bool]:
    """(période ou semestre, seconde session) ; (None, False) : fin d'année."""
    params = SessionQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    pk, second = params.validated_data.get("term"), params.validated_data["second"]
    term = get_object_or_404(Term, pk=pk) if pk else None
    deliberation.check_session(group, term, second=second)
    return term, second


def _council(group: ClassGroup, current: Deliberation | None) -> dict:
    saved = (current.council if current else None) or {}
    present = set(saved.get("present", []))
    return {
        "members": [
            {
                "id": m.user_id,
                "name": m.name,
                "direction": m.direction,
                "homeroom": m.homeroom,
                "courses": m.courses,
                "present": str(m.user_id) in present,
            }
            for m in council.members(group)
        ],
        "chair": saved.get("chair") or None,
        "secretary": saved.get("secretary") or None,
        "remarks": current.remarks if current else "",
    }


def _answer(
    request: Request, group: ClassGroup, term: Term | None = None, second: bool = False
) -> Response:
    if term is None:
        year = deliberation.overview(group, second=second)
        current, latest, ready, threshold = year.deliberation, year.latest, True, None
        students, results, counts, deviations = year.rows, [], year.counts, year.deviations
        state = year.status
    else:
        session = deliberation.session_overview(group, term)
        current, latest = session.deliberation, session.latest
        ready, threshold = session.ready, session.pass_percent
        students, results, counts, deviations = [], session.rows, {}, 0
        state = session.status
    return Response(
        ClassDeliberationSerializer(
            {
                "class_name": group.name,
                "term": term.pk if term else None,
                "kind": term.kind if term else "second" if second else "year",
                "can_edit": GRADES_VALIDATE in school_access(request).permissions,
                "status": state,
                "held_on": current.held_on if current else None,
                "version": current.version if current else 0,
                "ready": ready,
                "pass_percent": threshold,
                "counts": counts,
                "deviations": deviations,
                "latest": latest,
                "students": students,
                "results": results,
                "council": _council(group, current),
                "sessions": deliberation.sessions(group),
                "has_second_session": bool(resits.proclaimed_resits(group)),
                "exam_on": current.exam_on if current else None,
            }
        ).data
    )


def _group(pk) -> ClassGroup:
    return get_object_or_404(
        ClassGroup.objects.select_related("school", "level", "academic_year", "homeroom_teacher"),
        pk=pk,
    )


class _View(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "academics"
    required_permission = GRADES_VALIDATE


class _CouncilView(_View):
    """Lecture par les membres du conseil, écriture par la direction des études."""

    @property
    def required_permission(self):
        return COUNCIL_READ if self.request.method == "GET" else GRADES_VALIDATE

    def member_group(self, request: Request, pk) -> ClassGroup:
        group = _group(pk)
        council.check_member(request.user, school_access(request).permissions, group)
        return group


class DateSerializer(serializers.Serializer):
    held_on = serializers.DateField()


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=DECISIONS)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300)
    percent = serializers.DecimalField(
        max_digits=4,
        decimal_places=1,
        required=False,
        allow_null=True,
        help_text="Pourcentage repris (8.4.7) : seulement pour un élève sans aucune note cette "
        "année (issue `unranked`) ; absent ou nul : aucun.",
    )


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


class CouncilInputSerializer(serializers.Serializer):
    present = serializers.ListField(
        child=serializers.UUIDField(), max_length=200, help_text="Membres présents."
    )
    chair = serializers.UUIDField(required=False, allow_null=True)
    secretary = serializers.UUIDField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=2000)


SESSION = {"parameters": [SessionQuerySerializer]}


@extend_schema(tags=["deliberation"])
class ClassDeliberationView(_CouncilView):
    @extend_schema(**SESSION, responses={200: ClassDeliberationSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Tableau de la session pour les membres du conseil. Fin d'année : pourcentage de
        l'année, décision proposée d'après les règles de l'école, décision prise, écart et motif.
        Période ou semestre : pourcentage, place, conduite, application. Avec l'état, la date, le
        conseil (membres et présents), la dernière version proclamée et l'état des sessions."""
        group = self.member_group(request, pk)
        return _answer(request, group, *_session(request, group))

    @extend_schema(
        **SESSION, request=DateSerializer, responses={200: ClassDeliberationSerializer, **ERRORS}
    )
    def put(self, request: Request, pk) -> Response:
        """Fixe la date de la délibération (session non proclamée)."""
        group = _group(pk)
        term, second = _session(request, group)
        data = DateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        held_on = data.validated_data["held_on"]
        deliberation.set_date(group, held_on, actor=request.user, term=term, second=second)
        return _answer(request, group, term, second)


@extend_schema(tags=["deliberation"])
class CouncilView(_View):
    @extend_schema(
        **SESSION,
        request=CouncilInputSerializer,
        responses={200: ClassDeliberationSerializer, **ERRORS},
    )
    def put(self, request: Request, pk) -> Response:
        """Présents, président et secrétaire de séance (parmi les présents), observations du
        conseil ; session non proclamée. Figés à la proclamation, repris au procès-verbal."""
        group = _group(pk)
        term, second = _session(request, group)
        data = CouncilInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        council.set_council(
            deliberation.open_session(group, term, second=second),
            present=values["present"],
            chair=values.get("chair"),
            secretary=values.get("secretary"),
            remarks=values.get("remarks", ""),
            actor=request.user,
        )
        return _answer(request, group, term, second)


@extend_schema(tags=["deliberation"])
class EnrollmentDecisionView(_View):
    @extend_schema(
        **SESSION,
        request=DecisionSerializer,
        responses={200: ClassDeliberationSerializer, **ERRORS},
    )
    def put(self, request: Request, pk) -> Response:
        """Décision de fin d'année pour un élève ; un écart avec la proposition demande un motif.
        Élève sans aucune note cette année : pourcentage repris, de 0 à 100 (8.4.7). Avec
        `second` : décision finale de seconde session (`resit_again` pour un nouveau repêchage)."""
        enrollment = get_object_or_404(
            Enrollment.objects.select_related(
                "student",
                "class_group__school",
                "class_group__level",
                "class_group__academic_year",
                "class_group__homeroom_teacher",
            ),
            pk=pk,
        )
        _term, second = _session(request, enrollment.class_group)
        data = DecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        deliberation.decide(
            enrollment,
            data.validated_data["decision"],
            data.validated_data.get("reason", ""),
            actor=request.user,
            percent=data.validated_data.get("percent"),
            second=second,
        )
        return _answer(request, enrollment.class_group, None, second)


@extend_schema(tags=["deliberation"])
class ApplyProposalsView(_View):
    @extend_schema(**SESSION, request=None, responses={200: ClassDeliberationSerializer, **ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Fin d'année ou seconde session : prend la proposition du système pour chaque élève
        sans décision."""
        group = _group(pk)
        _term, second = _session(request, group)
        deliberation.apply_proposals(group, actor=request.user, second=second)
        return _answer(request, group, None, second)


@extend_schema(tags=["deliberation"])
class ProclaimView(_View):
    @extend_schema(**SESSION, request=None, responses={200: ClassDeliberationSerializer, **ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Proclame les résultats de la session et les fige avec le conseil. Fin d'année : date
        posée, une décision par élève, un motif par écart. Période ou semestre : date posée,
        bulletins dits prêts par le titulaire (`report_cards_not_ready`). Une proclamation après
        correction crée la version suivante. Seconde session : comme la fin d'année, pour ses
        élèves ; sa décision remplace « repêchage » (bulletin, situations, passage de classe)."""
        group = _group(pk)
        term, second = _session(request, group)
        deliberation.proclaim(group, actor=request.user, term=term, second=second)
        return _answer(request, group, term, second)


@extend_schema(tags=["deliberation"])
class ReopenView(_View):
    @extend_schema(
        **SESSION, request=ReasonSerializer, responses={200: ClassDeliberationSerializer, **ERRORS}
    )
    def post(self, request: Request, pk) -> Response:
        """Rouvre une session proclamée pour corriger (motif obligatoire). Les résultats figés
        restent ceux de la dernière proclamation jusqu'à la suivante."""
        group = _group(pk)
        term, second = _session(request, group)
        data = ReasonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        reason = data.validated_data["reason"]
        deliberation.reopen(group, reason, actor=request.user, term=term, second=second)
        return _answer(request, group, term, second)


class MinutesPrintSerializer(PrintOptionsSerializer, SessionQuerySerializer):
    output = serializers.ChoiceField(choices=["pdf", "html"], default="pdf")


def _quality(member: dict) -> str:
    parts = []
    if member["direction"]:
        parts.append(_("Studies management"))
    if member["homeroom"]:
        parts.append(_("Homeroom teacher"))
    if member["courses"]:
        parts.append(", ".join(member["courses"]))
    return " · ".join(parts)


def _figures(kind: str, rows: list[dict]) -> dict:
    """Chiffres du procès-verbal, lus dans les lignes figées."""
    if kind == "year":
        # Un `Counter` répond 0 à `.items` dans un gabarit : un vrai dictionnaire.
        return {"decisions": dict(Counter(row["decision"] for row in rows))}
    percents = [Decimal(row["percent"]) for row in rows if row["percent"] is not None]
    passed = sum(1 for row in rows if row["passed"])
    return {
        "students": len(rows),
        "ranked": len(percents),
        "passed": passed,
        "failed": len(percents) - passed,
        "average": (sum(percents) / len(percents)).quantize(Decimal("0.1")) if percents else None,
        "highest": max(percents, default=None),
        "lowest": min(percents, default=None),
    }


@extend_schema(tags=["deliberation"])
class MinutesView(_CouncilView):
    @extend_schema(parameters=[MinutesPrintSerializer], responses={**PRINT_RESPONSE, **ERRORS})
    def get(self, request: Request, pk) -> HttpResponse:
        """Procès-verbal de la session, en PDF ou en aperçu HTML, pour les membres du conseil :
        séance, président, présents et absents, chiffres de la classe, résultats des élèves
        (décisions et écarts motivés en fin d'année), observations, signatures. Lu dans la
        dernière version proclamée (`not_proclaimed` avant) ; chaque PDF est noté au journal."""
        group = self.member_group(request, pk)
        params = MinutesPrintSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        term, second = _session(request, group)
        current = deliberation.session_of(group, term, second=second)
        snapshot = current.snapshots.order_by("-version").first() if current else None
        if snapshot is None:
            raise BusinessError(deliberation.NOT_PROCLAIMED)
        kind = term.kind if term else "year"
        frozen = snapshot.council or {}
        members = [{**m, "quality": _quality(m)} for m in frozen.get("members", [])]
        labels = dict(DeliberationDecision.Decision.choices)
        rows = [
            {**row, "decision_label": labels.get(row.get("decision"), "")} for row in snapshot.rows
        ]
        if term:
            session = term_label(term)
        else:
            session = _("Second session") if second else _("End of the year")
        if data["output"] == "pdf":
            audit.record(
                Action.DELIBERATION_MINUTES_PRINTED,
                snapshot,
                actor=request.user,
                label=f"{group.name} · {session} · v{snapshot.version}",
            )
        context = {
            **school_header(require_current_school()),
            "class_group": group,
            "year": group.academic_year,
            "session": session,
            "kind": kind,
            "snapshot": snapshot,
            "rows": rows,
            "deviations": [row for row in rows if row.get("deviates")],
            "present": [m for m in members if m["present"]],
            "absent": [m for m in members if not m["present"]],
            "members_count": len(members),
            "chair": frozen.get("chair", ""),
            "secretary": frozen.get("secretary", ""),
            "remarks": frozen.get("remarks", ""),
            "figures": _figures(kind, snapshot.rows),
            "decision_labels": labels,
        }
        return render(
            "academics/deliberation_minutes.html",
            context,
            data["output"],
            f"proces-verbal-{slugify(group.name)}-{slugify(session)}.pdf",
            print_options(data, "portrait"),
        )


# Reprise des résultats (8.4.7)

PRIOR_RESULT_ISSUES = [
    "missing_matricule",
    "unknown_student",
    "duplicate",
    "missing_decision",
    "unknown_decision",
    "invalid_percent",
    "has_grades",
    "class_proclaimed",
]


class PriorResultUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="Excel (.xlsx) ou CSV, 5 Mo au plus.")
    expected = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Nombre de lignes prêtes de l'aperçu : présent, le fichier est enregistré.",
    )
    held_on = serializers.DateField(
        required=False, help_text="Date de délibération des classes qui n'en ont pas."
    )

    def validate(self, attrs):
        if "expected" in attrs and "held_on" not in attrs:
            raise serializers.ValidationError({"held_on": deliberation.DATE_REQUIRED.detail})
        return attrs


class PriorResultIssueSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=PRIOR_RESULT_ISSUES)


class PriorResultLineSerializer(serializers.Serializer):
    line = serializers.IntegerField(source="number", help_text="Numéro de la ligne du fichier.")
    matricule = serializers.CharField()
    student = serializers.CharField(source="enrollment.student", allow_null=True)
    class_group = serializers.CharField(source="enrollment.class_group.name", allow_null=True)
    decision_text = serializers.CharField(help_text="Décision telle qu'elle est écrite.")
    decision = serializers.CharField(
        help_text="Décision reconnue (valeurs de `decision`), ou vide."
    )
    percent_text = serializers.CharField(help_text="Pourcentage tel qu'il est écrit.")
    percent = serializers.DecimalField(max_digits=4, decimal_places=1, allow_null=True)
    issues = PriorResultIssueSerializer(many=True)


class PriorResultPreviewSerializer(serializers.Serializer):
    """Aperçu d'un fichier de résultats repris, ou son résultat une fois enregistré."""

    recorded = serializers.BooleanField()
    ready_count = serializers.IntegerField(help_text="Lignes prêtes (ou enregistrées).")
    error_count = serializers.IntegerField(help_text="Lignes en erreur : jamais enregistrées.")
    empty_count = serializers.IntegerField(help_text="Lignes sans décision : ignorées.")
    class_count = serializers.IntegerField(help_text="Classes des lignes prêtes.")
    changed_count = serializers.IntegerField(
        help_text="Décisions écrites (0 : le fichier était déjà enregistré tel quel)."
    )
    errors = PriorResultLineSerializer(many=True, help_text="Les 300 premières.")
    ready = PriorResultLineSerializer(many=True, help_text="Les 20 premières.")


@extend_schema(tags=["deliberation"])
class PriorResultsView(_View):
    """Reprise des résultats d'une année sans notes dans Mwangaza (8.4.7) : décision finale et
    pourcentage de chaque élève de l'année en cours, importés d'un fichier. Sans `expected` :
    aperçu (200), rien n'est écrit. Avec le nombre de lignes prêtes de l'aperçu et la date :
    décisions écrites dans la délibération de chaque classe, à proclamer ensuite (201) ; 409
    `preview_outdated` si le résultat n'est plus celui de l'aperçu."""

    parser_classes = [MultiPartParser]

    @extend_schema(
        request={"multipart/form-data": PriorResultUploadSerializer},
        responses={
            200: PriorResultPreviewSerializer,
            201: PriorResultPreviewSerializer,
            409: ErrorSerializer,
            **ERRORS,
        },
    )
    def post(self, request: Request) -> Response:
        params = PriorResultUploadSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        expected = data.get("expected")
        if expected is None:
            preview = prior_results.check(data["file"])
        else:
            preview = prior_results.record(
                data["file"], actor=request.user, held_on=data["held_on"], expected=expected
            )
        errors = preview.errors
        body = {
            "recorded": expected is not None,
            "ready_count": len(preview.ready),
            "error_count": len(errors),
            "empty_count": preview.empty,
            "class_count": preview.class_count,
            "changed_count": preview.changed,
            "errors": errors[: prior_results.MAX_ERRORS],
            "ready": preview.ready[: prior_results.MAX_READY],
        }
        return Response(
            PriorResultPreviewSerializer(body).data,
            status=status.HTTP_200_OK if expected is None else status.HTTP_201_CREATED,
        )


@extend_schema(tags=["deliberation"])
class PriorResultsTemplateView(_View):
    """Modèle Excel de la reprise des résultats, déjà garni : les élèves de l'année sans aucune
    note, dans une classe pas encore proclamée, avec ce qui est déjà repris."""

    @extend_schema(responses={**XLSX_RESPONSE, 409: ErrorSerializer, **ERRORS})
    def get(self, request: Request) -> HttpResponse:
        return file_response(prior_results.template_workbook(), XLSX, "reprise-resultats.xlsx")
