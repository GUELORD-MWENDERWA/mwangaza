"""API des paramètres de l'emploi du temps : grilles horaires, grille et salle des classes, salles,
règles générales (EDT.1a) ; disponibilités, contrôles (EDT.1b) ; règles (EDT.1c) ; brouillons de
l'horaire (EDT.2a : un geste par requête, qui renvoie l'état du brouillon) ; calcul automatique
(EDT.3a : demandé ici, fait par la file `heavy`, suivi par son état). Module
`timetable`, droit `timetable.manage` ; en ligne seulement. Listes courtes (quelques grilles, au
plus 300 salles, 500 règles, classes de l'année) : pas de pagination."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import support
from apps.accounts.permissions import HasSchoolAccess, HasSchoolPermission, school_access
from apps.accounts.roles import TIMETABLE_MANAGE, TIMETABLE_PUBLISH
from apps.ai.models import AiCall
from apps.core.documents import PRINT_RESPONSE, print_options, render, school_header
from apps.core.errors import ErrorSerializer
from apps.core.kept import Keep
from apps.core.tenancy import require_current_school
from apps.schools import organisation
from apps.schools.models import ClassGroup
from apps.timetable import (
    assistant,
    checks,
    constraints,
    drafts,
    prints,
    runs,
    schedule,
    services,
    versions,
)
from apps.timetable.models import (
    Room,
    TimeGrid,
    Timetable,
    TimetableEntry,
    TimetableRule,
    TimetableRun,
)
from apps.timetable.serializers import (
    AssistAskSerializer,
    AssistCallSerializer,
    AssistKeepSerializer,
    ChecksSerializer,
    DraftCreateSerializer,
    DraftSerializer,
    DraftStateSerializer,
    EntryChangeSerializer,
    MyTimetableSerializer,
    PlaceSerializer,
    PrintQuerySerializer,
    PublishSerializer,
    RoomCreateSerializer,
    RoomSerializer,
    RoomUpdateSerializer,
    RuleChoicesSerializer,
    RunCreateSerializer,
    RunListSerializer,
    RunSerializer,
    SwapSerializer,
    TeacherProfileSerializer,
    TimeGridCreateSerializer,
    TimeGridSerializer,
    TimeGridWriteSerializer,
    TimetableClassSerializer,
    TimetableClassUpdateSerializer,
    TimetableCourseSerializer,
    TimetableRuleSerializer,
    TimetableRulesSerializer,
    TimetableRuleWriteSerializer,
    VersionSerializer,
)

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
WRITE_ERRORS = {400: ErrorSerializer, 409: ErrorSerializer, **ERRORS}


class _TimetableView(APIView):
    permission_classes = [HasSchoolPermission]
    required_module = "timetable"
    required_permission = TIMETABLE_MANAGE


def _grid(grid_id) -> dict:
    grid = next(grid for grid in services.grids() if grid.pk == grid_id)
    return TimeGridSerializer(grid).data


@extend_schema(tags=["timetable"])
class GridsView(_TimetableView):
    @extend_schema(responses={200: TimeGridSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Grilles horaires de l'école (par défaut en premier) avec leurs cases."""
        return Response(TimeGridSerializer(services.grids(), many=True).data)

    @extend_schema(
        request=TimeGridCreateSerializer, responses={201: TimeGridSerializer, **WRITE_ERRORS}
    )
    def post(self, request: Request) -> Response:
        """Nouvelle grille ; sans cases, la semaine proposée (5 jours de 7 heures, samedi de 4,
        récréations après la 3e et la 5e heure) calculée avec la durée et le début donnés."""
        data = TimeGridCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        preset = {
            "lesson_minutes": services.PRESET_LESSON_MINUTES,
            "start_time": services.PRESET_START,
        }
        grid = services.create_grid(actor=request.user, **{**preset, **data.validated_data})
        return Response(_grid(grid.pk), status=status.HTTP_201_CREATED)


@extend_schema(tags=["timetable"])
class GridView(_TimetableView):
    @extend_schema(
        request=TimeGridWriteSerializer, responses={200: TimeGridSerializer, **WRITE_ERRORS}
    )
    def put(self, request: Request, pk) -> Response:
        """Enregistre les réglages et toute la semaine d'une grille, d'un bloc."""
        grid = get_object_or_404(TimeGrid.objects, pk=pk)
        data = TimeGridWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.update_grid(grid, actor=request.user, **data.validated_data)
        return Response(_grid(grid.pk))

    @extend_schema(request=None, responses={204: None, **WRITE_ERRORS})
    def delete(self, request: Request, pk) -> Response:
        """Supprime une grille (jamais celle par défaut) ; ses classes suivent la grille par
        défaut."""
        services.delete_grid(get_object_or_404(TimeGrid.objects, pk=pk), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["timetable"])
class ClassesView(_TimetableView):
    @extend_schema(responses={200: TimetableClassSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Classes de l'année en cours : grille, salle habituelle, heures de cours et places."""
        rows = services.class_rows(organisation.current_year())
        return Response(TimetableClassSerializer(rows, many=True).data)


@extend_schema(tags=["timetable"])
class ClassView(_TimetableView):
    @extend_schema(
        request=TimetableClassUpdateSerializer,
        responses={200: TimetableClassSerializer, **WRITE_ERRORS},
    )
    def patch(self, request: Request, pk) -> Response:
        """Change la grille ou la salle habituelle d'une classe (vide : les retire)."""
        group = get_object_or_404(ClassGroup.objects, pk=pk)
        data = TimetableClassUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.set_class(group, actor=request.user, **data.validated_data)
        row = next(row for row in services.class_rows(group.academic_year) if row["id"] == group.pk)
        return Response(TimetableClassSerializer(row).data)


@extend_schema(tags=["timetable"])
class RoomsView(_TimetableView):
    @extend_schema(responses={200: RoomSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Salles, ateliers et laboratoires, retirés compris."""
        return Response(RoomSerializer(services.rooms(), many=True).data)

    @extend_schema(request=RoomCreateSerializer, responses={201: RoomSerializer, **WRITE_ERRORS})
    def post(self, request: Request) -> Response:
        """Ajoute une salle."""
        data = RoomCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = {"capacity": None, **data.validated_data}
        room = services.create_room(actor=request.user, **fields)
        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["timetable"])
class RoomView(_TimetableView):
    @extend_schema(request=RoomUpdateSerializer, responses={200: RoomSerializer, **WRITE_ERRORS})
    def patch(self, request: Request, pk) -> Response:
        """Change le nom, le type ou les places d'une salle, ou la retire (`is_active`)."""
        room = get_object_or_404(Room.objects, pk=pk)
        data = RoomUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        room = services.update_room(room, actor=request.user, **data.validated_data)
        return Response(RoomSerializer(room).data)


@extend_schema(tags=["timetable"])
class RulesView(_TimetableView):
    @extend_schema(responses={200: TimetableRulesSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Règles générales de l'emploi du temps de l'école."""
        return Response(services.rules_of(require_current_school()))

    @extend_schema(
        request=TimetableRulesSerializer, responses={200: TimetableRulesSerializer, **WRITE_ERRORS}
    )
    def put(self, request: Request) -> Response:
        """Enregistre les règles générales."""
        data = TimetableRulesSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(services.set_rules(data.validated_data, actor=request.user))


@extend_schema(tags=["timetable"])
class TeachersView(_TimetableView):
    @extend_schema(responses={200: TeacherProfileSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Disponibilités réglées des enseignants (charge au plus, heures par jour, absences) ;
        un enseignant absent de la liste n'a rien de réglé."""
        return Response(TeacherProfileSerializer(services.teacher_profiles(), many=True).data)


@extend_schema(tags=["timetable"])
class TeacherView(_TimetableView):
    @extend_schema(
        request=TeacherProfileSerializer, responses={200: TeacherProfileSerializer, **WRITE_ERRORS}
    )
    def put(self, request: Request, pk) -> Response:
        """Règle la disponibilité d'un membre du personnel actif de l'école (`pk` : son compte) ;
        une absence en jour entier couvre les plages du même jour."""
        data = TeacherProfileSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        profile = services.set_teacher_profile(pk, actor=request.user, **data.validated_data)
        return Response(TeacherProfileSerializer(profile).data)


@extend_schema(tags=["timetable"])
class ChecksView(_TimetableView):
    @extend_schema(responses={200: ChecksSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Contrôles avant le calcul de l'horaire (année en cours) : classes, enseignants et
        salles surchargés, cours impossibles à étaler, cours incomplets ; rouge d'abord."""
        return Response(ChecksSerializer(checks.run(organisation.current_year())).data)


@extend_schema(tags=["timetable"])
class ConstraintsView(_TimetableView):
    @extend_schema(responses={200: TimetableRuleSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Règles de l'horaire de l'école (liste fermée de kinds), actives d'abord."""
        return Response(TimetableRuleSerializer(constraints.rules(), many=True).data)

    @extend_schema(
        request=TimetableRuleWriteSerializer,
        responses={201: TimetableRuleSerializer, **WRITE_ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Ajoute une règle : paramètres vérifiés par le schéma de son kind ; cours, salles et
        enseignants de l'école seulement ; un cours dans un seul groupe ; au plus 500 règles."""
        data = TimetableRuleWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rule = constraints.create_rule(actor=request.user, **data.validated_data)
        return Response(TimetableRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["timetable"])
class ConstraintView(_TimetableView):
    @extend_schema(
        request=TimetableRuleWriteSerializer,
        responses={200: TimetableRuleSerializer, **WRITE_ERRORS},
    )
    def put(self, request: Request, pk) -> Response:
        """Remplace une règle (kind compris) ; ce qui change va dans le journal."""
        rule = get_object_or_404(TimetableRule, pk=pk)
        data = TimetableRuleWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rule = constraints.update_rule(rule, actor=request.user, **data.validated_data)
        return Response(TimetableRuleSerializer(rule).data)

    @extend_schema(responses={204: None, **ERRORS})
    def delete(self, request: Request, pk) -> Response:
        """Supprime une règle (journal) ; la désactiver la garde sans la compter."""
        constraints.delete_rule(get_object_or_404(TimetableRule, pk=pk), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["timetable"])
class ConstraintChoicesView(_TimetableView):
    @extend_schema(responses={200: RuleChoicesSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Ce que l'éditeur des règles propose : kinds (forces permises, poids par défaut), cours
        enseignés cette année et leurs enseignants."""
        return Response(RuleChoicesSerializer(constraints.choices()).data)


def _assist_call(request: Request, pk) -> AiCall:
    """L'appel de cette personne, dans cette école (un autre : 404)."""
    return get_object_or_404(AiCall, pk=pk, user=request.user, use=assistant.USE)


def _assist_state(call: AiCall, code: int = status.HTTP_200_OK) -> Response:
    ready = call.state == AiCall.State.DONE
    data = {
        "id": call.pk,
        "state": call.state,
        "refusal": call.refusal,
        "proposals": assistant.proposals(call) if ready else None,
    }
    return Response(AssistCallSerializer(data).data, status=code)


@extend_schema(tags=["timetable"])
class AssistView(_TimetableView):
    @extend_schema(
        request=AssistAskSerializer,
        responses={202: AssistCallSerializer, 400: ErrorSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Envoie les consignes du directeur des études à l'assistant (IA.2a) : l'appel est rendu
        tout de suite, la réponse se lit sur l'appel. Droits `timetable.manage` et `ai.use`,
        crédits de l'école ; refus expliqués (assistant coupé, crédits épuisés, trop long…)."""
        data = AssistAskSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        call = assistant.ask(
            school=require_current_school(),
            user=request.user,
            permissions=school_access(request).permissions,
            request_id=data.validated_data["request_id"],
            text=data.validated_data["text"],
            support=support.current(request) is not None,
        )
        return _assist_state(call, status.HTTP_202_ACCEPTED)


@extend_schema(tags=["timetable"])
class AssistCallView(_TimetableView):
    @extend_schema(responses={200: AssistCallSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """État de la demande ; prête, les règles proposées (vérifiées) ou les consignes pas
        comprises avec la raison."""
        return _assist_state(_assist_call(request, pk))


@extend_schema(tags=["timetable"])
class AssistKeepView(_TimetableView):
    @extend_schema(
        request=AssistKeepSerializer,
        responses={200: TimetableRuleSerializer(many=True), **WRITE_ERRORS},
    )
    def post(self, request: Request, pk) -> Response:
        """Enregistre les règles cochées (revérifiées, source « assistant », journal), une seule
        fois par demande."""
        data = AssistKeepSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rules = assistant.keep(
            _assist_call(request, pk),
            [
                {"sentence": item["sentence"], "rule": item["rule"]}
                for item in data.validated_data["items"]
            ],
            actor=request.user,
        )
        return Response(TimetableRuleSerializer(rules, many=True).data)


@extend_schema(tags=["timetable"])
class AssistAbandonView(_TimetableView):
    @extend_schema(request=None, responses={204: None, **WRITE_ERRORS})
    def post(self, request: Request, pk) -> Response:
        """La personne abandonne la réponse : rien n'est enregistré."""
        assistant.abandon(_assist_call(request, pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


def _state(timetable: Timetable, code: int = status.HTTP_200_OK) -> Response:
    return Response(DraftStateSerializer(drafts.state(timetable)).data, status=code)


@extend_schema(tags=["timetable"])
class TimetableCoursesView(_TimetableView):
    @extend_schema(responses={200: TimetableCourseSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Cours enseignés cette année, tels que l'éditeur de l'horaire les place : séances, salle
        ou type exigé, récréation traversable, au plus par jour."""
        return Response(
            TimetableCourseSerializer(
                drafts.year_courses(organisation.current_year()), many=True
            ).data
        )


@extend_schema(tags=["timetable"])
class DraftsView(_TimetableView):
    @extend_schema(responses={200: DraftSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Brouillons de l'horaire de l'année en cours, le plus récent d'abord."""
        return Response(DraftSerializer(drafts.drafts(organisation.current_year()), many=True).data)

    @extend_schema(
        request=DraftCreateSerializer, responses={201: DraftStateSerializer, **WRITE_ERRORS}
    )
    def post(self, request: Request) -> Response:
        """Nouveau brouillon : copie d'une version de l'année (brouillon, publiée ou archivée),
        ou vide avec les heures verrouillées des règles déjà placées (journal)."""
        data = DraftCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        year = organisation.current_year()
        based_on = None
        if data.validated_data["based_on"]:
            based_on = Timetable.objects.filter(
                academic_year=year, pk=data.validated_data["based_on"]
            ).first()
            if based_on is None:
                return Response(
                    {"based_on": [_("This timetable does not exist.")]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        timetable = drafts.create_draft(
            year=year, name=data.validated_data["name"], based_on=based_on, actor=request.user
        )
        return _state(timetable, status.HTTP_201_CREATED)


@extend_schema(tags=["timetable"])
class DraftView(_TimetableView):
    @extend_schema(responses={200: DraftStateSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Un brouillon, ou une version publiée ou archivée (lecture seule) : séances, conflits
        (recalculés), reste à placer, heures placées / dues."""
        return _state(get_object_or_404(Timetable, pk=pk))

    @extend_schema(responses={204: None, **WRITE_ERRORS})
    def delete(self, request: Request, pk) -> Response:
        """Supprime un brouillon et ses séances (journal)."""
        drafts.delete_draft(get_object_or_404(Timetable, pk=pk), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["timetable"])
class DraftEntriesView(_TimetableView):
    @extend_schema(request=PlaceSerializer, responses={201: DraftStateSerializer, **WRITE_ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Place une séance restant à placer ; refusée hors de la grille de la classe, sur une
        récréation que le cours ne passe pas, ou si le cours n'a plus de séance de cette longueur.
        Un conflit ne la refuse pas : il est montré."""
        timetable = get_object_or_404(Timetable, pk=pk)
        data = PlaceSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return _state(
            drafts.place(timetable, actor=request.user, **data.validated_data),
            status.HTTP_201_CREATED,
        )


@extend_schema(tags=["timetable"])
class DraftEntryView(_TimetableView):
    @extend_schema(
        request=EntryChangeSerializer, responses={200: DraftStateSerializer, **WRITE_ERRORS}
    )
    def patch(self, request: Request, pk, entry) -> Response:
        """Un geste sur une séance : la déplacer, changer sa salle, la verrouiller ou la
        déverrouiller (journal). Une séance verrouillée ne bouge ni ne change de salle."""
        timetable = get_object_or_404(Timetable, pk=pk)
        lesson = get_object_or_404(TimetableEntry, pk=entry, timetable=timetable)
        data = EntryChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        change = data.validated_data
        if "locked" in change:
            timetable = drafts.set_locked(
                timetable, lesson, locked=change["locked"], actor=request.user
            )
        elif "room" in change:
            timetable = drafts.set_room(timetable, lesson, room=change["room"])
        else:
            timetable = drafts.move(
                timetable, lesson, weekday=change["weekday"], first=change["first"]
            )
        return _state(timetable)

    @extend_schema(request=None, responses={200: DraftStateSerializer, **WRITE_ERRORS})
    def delete(self, request: Request, pk, entry) -> Response:
        """Retire une séance du brouillon : elle revient dans « À placer »."""
        timetable = get_object_or_404(Timetable, pk=pk)
        lesson = get_object_or_404(TimetableEntry, pk=entry, timetable=timetable)
        return _state(drafts.remove(timetable, lesson))


@extend_schema(tags=["timetable"])
class DraftSwapView(_TimetableView):
    @extend_schema(request=SwapSerializer, responses={200: DraftStateSerializer, **WRITE_ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Échange les places de deux séances du brouillon (aucune verrouillée)."""
        timetable = get_object_or_404(Timetable, pk=pk)
        data = SwapSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        lessons = timetable.entries
        entry = get_object_or_404(lessons, pk=data.validated_data["entry"])
        other = get_object_or_404(lessons, pk=data.validated_data["other"])
        return _state(drafts.swap(timetable, entry, other))


@extend_schema(tags=["timetable"])
class DraftUndoView(_TimetableView):
    @extend_schema(request=None, responses={200: DraftStateSerializer, **WRITE_ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Annule le dernier geste (50 derniers gardés)."""
        timetable = get_object_or_404(Timetable, pk=pk)
        return _state(drafts.undo(timetable, actor=request.user))


@extend_schema(tags=["timetable"])
class DraftPublishView(_TimetableView):
    required_permission = TIMETABLE_PUBLISH

    @extend_schema(request=PublishSerializer, responses={200: DraftStateSerializer, **WRITE_ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Publie le brouillon : il devient l'horaire de l'école dès `valid_from`, ne se modifie
        plus, et la version en vigueur est archivée (journal). Refusé (409) tant que le brouillon
        a des conflits ; le reste à placer ne bloque pas."""
        timetable = get_object_or_404(Timetable, pk=pk)
        data = PublishSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        published = versions.publish(
            timetable, valid_from=data.validated_data["valid_from"], actor=request.user
        )
        return _state(published)


@extend_schema(tags=["timetable"])
class VersionsView(_TimetableView):
    @extend_schema(responses={200: VersionSerializer(many=True), **ERRORS})
    def get(self, request: Request) -> Response:
        """Version publiée puis anciennes versions (archivées) de l'année en cours."""
        listed = versions.versions(organisation.current_year())
        return Response(VersionSerializer(listed, many=True).data)


@extend_schema(tags=["timetable"])
class PrintView(_TimetableView):
    @extend_schema(
        parameters=[PrintQuerySerializer],
        responses={**PRINT_RESPONSE, 400: ErrorSerializer, 409: ErrorSerializer, **ERRORS},
    )
    def get(self, request: Request) -> HttpResponse:
        """Horaire imprimé (EDT.4c) : d'une classe, d'un enseignant (avec sa charge), d'une salle
        ou général, d'une version au choix (la publiée par défaut). Sans `subject`, un seul PDF,
        une page par classe, enseignant ou salle qui a des séances. Aperçu HTML ou PDF gardé."""
        params = PrintQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        year = organisation.current_year()
        timetable = prints.timetable_of(data.get("timetable"), year.pk if year else None)
        kind = data["kind"]
        pages = prints.document(
            kind, timetable, data.get("subject"), one_sheet=data["paper"] == "a3"
        )
        options = print_options(data, "landscape")
        template = "timetable/general.html" if kind == prints.GENERAL else "timetable/sheet.html"
        keep = Keep(
            kind=f"timetable_{kind}",
            subjects=[subject for subject, _context in pages],
            variant=f"{options['paper']}-{options['orientation']}",
            volatile={"printed_at": None},
        )
        contexts = [
            {**school_header(require_current_school()), **context} for _subject, context in pages
        ]
        return render(
            template,
            contexts[0],
            data["output"],
            f"horaire-{kind}.pdf",
            options,
            more=contexts[1:],
            keep=keep,
        )


@extend_schema(tags=["timetable"])
class MyTimetableView(APIView):
    """« Mon horaire » (EDT.4b) : tout le personnel de l'école le lit, chacun seulement ses
    séances et celles de la classe dont il est titulaire."""

    permission_classes = [HasSchoolAccess]
    required_module = "timetable"

    @extend_schema(responses={200: MyTimetableSerializer, 403: ErrorSerializer})
    def get(self, request: Request) -> Response:
        """Séances du compte dans l'horaire publié de l'année en cours (début et fin d'après la
        grille de chaque classe) et, s'il est titulaire, celles de sa classe."""
        return Response(MyTimetableSerializer(schedule.mine(request.user)).data)


@extend_schema(tags=["timetable"])
class RunsView(_TimetableView):
    @extend_schema(operation_id="timetable_runs_list", responses={200: RunListSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Les 10 derniers calculs de l'année en cours, le plus récent d'abord, et le temps de
        calcul le plus long permis à l'école (une demande plus longue y est ramenée)."""
        listed = {
            "time_limit_max": require_current_school().timetable_max_seconds,
            "runs": runs.runs(organisation.current_year()),
        }
        return Response(RunListSerializer(listed).data)

    @extend_schema(
        request=RunCreateSerializer,
        responses={200: RunSerializer, 202: RunSerializer, 429: ErrorSerializer, **WRITE_ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Demande le calcul d'un brouillon (tout l'horaire, une classe ou un enseignant ; le
        reste ne bouge pas) ; le résultat sera un nouveau brouillon. 202 : demandé ; 200 : cette
        demande existait déjà. Refusé (409) si les contrôles ont du rouge ou si l'école calcule
        déjà ; 429 si la plateforme a trop de calculs en cours."""
        data = RunCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data
        timetable = (
            drafts.drafts(organisation.current_year()).filter(pk=fields.pop("timetable")).first()
        )
        if timetable is None:
            return Response(
                {"timetable": [_("This draft does not exist.")]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        run, created = runs.request(timetable=timetable, actor=request.user, **fields)
        code = status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK
        return Response(RunSerializer(run).data, status=code)


@extend_schema(tags=["timetable"])
class RunView(_TimetableView):
    @extend_schema(responses={200: RunSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Un calcul : état, durée, souhaits non tenus, règles qui bloquent, brouillon calculé."""
        return Response(RunSerializer(get_object_or_404(TimetableRun, pk=pk)).data)


@extend_schema(tags=["timetable"])
class RunCancelView(_TimetableView):
    @extend_schema(request=None, responses={200: RunSerializer, **WRITE_ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Annule un calcul en attente ou en cours : son résultat ne sera pas écrit."""
        return Response(RunSerializer(runs.cancel(get_object_or_404(TimetableRun, pk=pk))).data)
