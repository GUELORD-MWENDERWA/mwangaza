"""Bibliothèque (lot 11, module `library`) : catalogue, exemplaires, import, règles, prêts,
constats et liste de l'appareil du guichet. Lecture : `library.manage` ou `library.lend` ;
écriture du catalogue, des règles et des constats : `library.manage` ; prolongation :
`library.lend` ; rectification d'un constat : `inventory.validate`. Prêts et retours arrivent par
la synchronisation (`inventory.loan`, `inventory.return`, `POST /api/sync/push/`)."""

from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.permissions import HasSchoolPermission, school_access
from apps.accounts.roles import INVENTORY_VALIDATE, LIBRARY_LEND, LIBRARY_MANAGE
from apps.core.documents import XLSX, XLSX_RESPONSE, file_response
from apps.core.errors import ErrorSerializer
from apps.inventory import catalogue, loans, losses, rules
from apps.inventory.models import Copy, Item, Loan, LossReport
from apps.inventory.serializers import (
    BookDetailSerializer,
    BookSerializer,
    BookWriteSerializer,
    CatalogueImportSerializer,
    CatalogueImportUploadSerializer,
    CatalogueQuerySerializer,
    CopiesAddSerializer,
    CopySerializer,
    DeskQuerySerializer,
    DeskSerializer,
    LendingRulesSerializer,
    LoanQuerySerializer,
    LoanSerializer,
    ReportCorrectionSerializer,
    ReportSerializer,
    ReportWriteSerializer,
)

ERRORS = {403: ErrorSerializer, 404: ErrorSerializer}
WRITE_ERRORS = {400: ErrorSerializer, 409: ErrorSerializer, **ERRORS}
READ = (LIBRARY_MANAGE, LIBRARY_LEND)


class _LibraryView(GenericAPIView):
    """Lecture : `library.manage` ou `library.lend` ; écriture : `write_permission`."""

    permission_classes = [HasSchoolPermission]
    required_module = "library"
    write_permission: str | tuple[str, ...] = LIBRARY_MANAGE

    @property
    def required_permission(self):
        return READ if self.request.method in ("GET", "HEAD") else self.write_permission

    def query(self, serializer_class) -> dict:
        params = serializer_class(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return params.validated_data

    def permissions(self) -> frozenset[str]:
        return frozenset(school_access(self.request).permissions)


def _books():
    return catalogue.items(catalogue.library()).order_by("name", "author")


@extend_schema(tags=["library"])
class BooksView(_LibraryView, ListAPIView):
    serializer_class = BookSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Item.objects.none()
        data = self.query(CatalogueQuerySerializer)
        books = _books()
        for word in data.get("search", "").split():
            books = books.filter(Q(name__icontains=word) | Q(author__icontains=word))
        if data.get("category"):
            books = books.filter(category__iexact=data["category"])
        if data.get("level"):
            books = books.filter(level_id=data["level"])
        return books

    @extend_schema(parameters=[CatalogueQuerySerializer])
    def get(self, request: Request, *args, **kwargs) -> Response:
        """Catalogue : titres de la bibliothèque (recherche dans le titre et l'auteur, catégorie,
        niveau), avec leurs exemplaires en service, disponibles et prêtés."""
        return super().get(request, *args, **kwargs)

    @extend_schema(request=BookWriteSerializer, responses={201: BookSerializer, **WRITE_ERRORS})
    def post(self, request: Request) -> Response:
        """Nouveau titre, avec `copies` exemplaires numérotés (étiquettes)."""
        data = BookWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        book = catalogue.save_item(
            None,
            actor=request.user,
            location=catalogue.library(),
            kind=Item.Kind.BOOK,
            **data.validated_data,
        )
        return Response(
            BookSerializer(_books().get(pk=book.pk)).data, status=status.HTTP_201_CREATED
        )


def _book_detail(pk) -> Item:
    copies = Copy.objects.order_by("number")
    book = get_object_or_404(_books().prefetch_related(Prefetch("copies", queryset=copies)), pk=pk)
    open_by_copy = {
        loan.copy_id: loan
        for loan in loans.open_loans().filter(copy__item=book).select_related("student")
    }
    book.copy_list = list(book.copies.all())
    for copy in book.copy_list:
        copy.item = book
        copy.open_loan = open_by_copy.get(copy.pk)
    return book


@extend_schema(tags=["library"])
class BookView(_LibraryView):
    @extend_schema(responses={200: BookDetailSerializer, **ERRORS})
    def get(self, request: Request, pk) -> Response:
        """Un titre et chacun de ses exemplaires : code, état, emprunteur et date de retour."""
        return Response(BookDetailSerializer(_book_detail(pk)).data)

    @extend_schema(
        request=BookWriteSerializer, responses={200: BookDetailSerializer, **WRITE_ERRORS}
    )
    def patch(self, request: Request, pk) -> Response:
        """Modifier un titre (au journal : ce qui change)."""
        book = get_object_or_404(_books(), pk=pk)
        data = BookWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = {key: value for key, value in data.validated_data.items() if key != "copies"}
        catalogue.save_item(book, actor=request.user, **values)
        return Response(BookDetailSerializer(_book_detail(pk)).data)


@extend_schema(tags=["library"])
class BookCopiesView(_LibraryView):
    @extend_schema(
        request=CopiesAddSerializer, responses={201: CopySerializer(many=True), **WRITE_ERRORS}
    )
    def post(self, request: Request, pk) -> Response:
        """Ajouter des exemplaires à un titre : chacun reçoit le numéro suivant de l'école."""
        book = get_object_or_404(_books(), pk=pk)
        data = CopiesAddSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        copies = catalogue.add_copies(book, actor=request.user, count=data.validated_data["count"])
        return Response(CopySerializer(copies, many=True).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["library"])
class ImportView(_LibraryView):
    parser_classes = [MultiPartParser]

    @extend_schema(
        request={"multipart/form-data": CatalogueImportUploadSerializer},
        responses={200: CatalogueImportSerializer, 201: CatalogueImportSerializer, **WRITE_ERRORS},
    )
    def post(self, request: Request) -> Response:
        """Import du catalogue depuis Excel (BIB.1). Sans `expected` : aperçu ligne par ligne
        (200), rien n'est écrit. Avec le nombre de lignes prêtes de l'aperçu : titres et
        exemplaires créés d'un bloc (201) ; 409 `preview_outdated` si le résultat a changé."""
        params = CatalogueImportUploadSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        expected = data.get("expected")
        where = {"location": catalogue.library(), "currency": data["currency"]}
        if expected is None:
            preview = catalogue.check(data["file"], **where)
        else:
            preview = catalogue.record(data["file"], **where, actor=request.user, expected=expected)
        body = {
            "recorded": expected is not None,
            "ready_count": preview.count(catalogue.READY),
            "skipped_count": preview.count(catalogue.SKIPPED),
            "error_count": preview.count(catalogue.ERROR),
            "lines": preview.lines,
        }
        return Response(
            CatalogueImportSerializer(body).data,
            status=status.HTTP_200_OK if expected is None else status.HTTP_201_CREATED,
        )


@extend_schema(tags=["library"])
class ImportTemplateView(_LibraryView):
    @extend_schema(responses={**XLSX_RESPONSE, **ERRORS})
    def get(self, request: Request) -> HttpResponse:
        """Modèle Excel de l'import du catalogue : titre, auteur, ISBN, catégorie, niveau,
        exemplaires, prix."""
        return file_response(catalogue.template_workbook(), XLSX, "modele-catalogue.xlsx")


@extend_schema(tags=["library"])
class RulesView(_LibraryView):
    @extend_schema(responses={200: LendingRulesSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Règles de prêt de l'école (valeurs par défaut tant qu'elle n'a rien changé)."""
        return Response(LendingRulesSerializer(rules.rules()).data)

    @extend_schema(
        request=LendingRulesSerializer, responses={200: LendingRulesSerializer, **WRITE_ERRORS}
    )
    def put(self, request: Request) -> Response:
        """Enregistrer les règles de prêt (au journal : ce qui change)."""
        data = LendingRulesSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        saved = rules.update_rules(actor=request.user, values=data.validated_data)
        return Response(LendingRulesSerializer(saved).data)


@extend_schema(tags=["library"])
class LoansView(_LibraryView, ListAPIView):
    serializer_class = LoanSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Loan.objects.none()
        data = self.query(LoanQuerySerializer)
        return loans.loans(
            location=catalogue.library(), state=data["state"], search=data.get("search", "")
        )

    @extend_schema(parameters=[LoanQuerySerializer])
    def get(self, request: Request, *args, **kwargs) -> Response:
        """Prêts de la bibliothèque : en cours (par date de retour), en retard, ou rendus (plus
        récents d'abord) ; recherche dans le titre, le nom ou le matricule."""
        return super().get(request, *args, **kwargs)


@extend_schema(tags=["library"])
class LoanExtendView(_LibraryView):
    write_permission = LIBRARY_LEND

    @extend_schema(request=None, responses={200: LoanSerializer, **WRITE_ERRORS})
    def post(self, request: Request, pk) -> Response:
        """Prolonger un prêt en cours de la durée de l'emprunteur, dans la limite des règles."""
        loan = get_object_or_404(loans.open_loans().filter(copy__item__kind=Item.Kind.BOOK), pk=pk)
        loan = loans.extend(loan, actor=request.user, permissions=self.permissions())
        return Response(LoanSerializer(loans.loans(state="open").get(pk=loan.pk)).data)


def _reports():
    return LossReport.objects.select_related(
        "copy__item", "loan__student", "loan__member__user", "corrected_by"
    ).filter(copy__item__location__kind="library")


@extend_schema(tags=["library"])
class ReportsView(_LibraryView, ListAPIView):
    serializer_class = ReportSerializer

    def get_queryset(self):
        return _reports()

    @extend_schema(responses={200: ReportSerializer(many=True), **ERRORS})
    def get(self, request: Request, *args, **kwargs) -> Response:
        """Constats de perte et d'abîmé, plus récents d'abord, rectifications comprises."""
        return super().get(request, *args, **kwargs)

    @extend_schema(request=ReportWriteSerializer, responses={201: ReportSerializer, **WRITE_ERRORS})
    def post(self, request: Request) -> Response:
        """Constat : l'exemplaire sort du catalogue, son prêt est fermé ; pour un élève, les frais
        de remplacement (prix du titre par défaut) s'ajoutent à ce qu'il doit, payables à la
        caisse ; le parent est prévenu. Au journal."""
        data = ReportWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        copy = values.pop("copy")
        if copy.item.kind != Item.Kind.BOOK:
            raise NotFound()
        report = losses.report(copy, actor=request.user, **values)
        return Response(
            ReportSerializer(_reports().get(pk=report.pk)).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["library"])
class ReportCorrectView(_LibraryView):
    write_permission = INVENTORY_VALIDATE

    @extend_schema(
        request=ReportCorrectionSerializer, responses={201: ReportSerializer, **WRITE_ERRORS}
    )
    def post(self, request: Request, pk) -> Response:
        """Rectifier un constat fait par erreur : l'exemplaire revient, la dette encore impayée
        est retirée (409 `charge_paid` sinon : annuler d'abord le paiement). Au journal."""
        report = get_object_or_404(_reports(), pk=pk)
        data = ReportCorrectionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        correction = losses.correct(report, actor=request.user, note=data.validated_data["note"])
        return Response(
            ReportSerializer(_reports().get(pk=correction.pk)).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["library"])
class DeskView(_LibraryView):
    @property
    def required_permission(self):
        return LIBRARY_LEND

    @extend_schema(parameters=[DeskQuerySerializer], responses={200: DeskSerializer, **ERRORS})
    def get(self, request: Request) -> Response:
        """Liste de l'appareil du guichet : exemplaires en service (par pages de 2 000) avec leur
        prêt ouvert, et les règles de prêt. Rien n'est envoyé si `version` est celle de
        l'appareil ; une version changée en cours de pages : reprendre depuis la première."""
        data = self.query(DeskQuerySerializer)
        place = catalogue.library()
        version = loans.desk_version(place)
        settings = rules.rules()
        after = data.get("after")
        if after is None and data.get("version") == version:
            body = {"version": version, "unchanged": True, "copies": [], "next": None}
            return Response(DeskSerializer({**body, "rules": settings}).data)
        copies = loans.desk_copies(place, after)
        has_more = len(copies) > loans.DESK_PAGE
        copies = copies[: loans.DESK_PAGE]
        body = {
            "version": version,
            "unchanged": False,
            "copies": copies,
            "next": copies[-1].number if has_more else None,
            "rules": settings,
        }
        return Response(DeskSerializer(body).data)
