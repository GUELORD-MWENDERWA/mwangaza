"""Documents à imprimer ou à télécharger (D5, M6) : gabarit HTML rendu tel quel (aperçu) ou en PDF
(WeasyPrint), classeurs Excel (openpyxl). Les images (logo, photo) sont intégrées au HTML en
`data:` : WeasyPrint ne charge rien d'autre, ni fichier ni adresse (un SVG piégé ne peut pas faire
appeler une adresse par le serveur)."""

import base64
import io
import re

import openpyxl
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from apps.schools.logos import CONTENT_TYPES as LOGO_TYPES
from apps.schools.logos import logo_kind
from apps.schools.models import School

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF = "application/pdf"
HTML = "text/html"
XLSX_RESPONSE = {(200, XLSX): OpenApiResponse(OpenApiTypes.BINARY, description="Classeur Excel.")}
PRINT_RESPONSE = {
    (200, PDF): OpenApiResponse(OpenApiTypes.BINARY, description="Document PDF (`output=pdf`)."),
    (200, HTML): OpenApiResponse(OpenApiTypes.STR, description="Aperçu HTML (`output=html`)."),
}


def data_uri(field, kind: str | None, content_types: dict[str, str]) -> str:
    """Fichier (logo, photo) intégré au document ; vide s'il manque ou n'est plus lisible."""
    if not field or kind is None:
        return ""
    try:
        with field.open("rb") as file:
            content = file.read()
    except OSError:
        return ""
    return f"data:{content_types[kind]};base64,{base64.b64encode(content).decode()}"


def school_header(school: School) -> dict:
    """En-tête commun : nom officiel (sinon nom) et logo de l'école, date d'impression."""
    kind = None
    if school.logo:
        try:
            with school.logo.open("rb") as file:
                kind = logo_kind(file)
        except OSError:
            kind = None
    return {
        "school_name": school.official_name or school.name,
        "logo": data_uri(school.logo, kind, LOGO_TYPES),
        "printed_at": timezone.localtime(),
    }


def render(template: str, context: dict, output: str, name: str) -> HttpResponse:
    """`html` : aperçu dans la page (même origine seulement) ; `pdf` : fichier ouvert dans le
    navigateur, qui l'imprime ou l'enregistre."""
    html = render_to_string(template, context)
    if output == "html":
        response = HttpResponse(html, content_type=f"{HTML}; charset=utf-8")
        response["X-Frame-Options"] = "SAMEORIGIN"
        return response
    from weasyprint import HTML as Document
    from weasyprint.urls import URLFetcher

    content = Document(string=html, url_fetcher=URLFetcher(allowed_protocols=["data"])).write_pdf()
    return file_response(content, PDF, name, inline=True)


def workbook(headers: list[str], rows, *, title: str = "", widths: list[int] | None = None):
    """Classeur d'une feuille, titres en gras, écrit ligne à ligne (milliers de lignes)."""
    book = openpyxl.Workbook(write_only=True)
    # Excel refuse []:*?/\ dans le nom d'une feuille, et plus de 31 caractères.
    sheet = book.create_sheet(re.sub(r"[\[\]:*?/\\]", " ", title)[:31] or None)
    for index, width in enumerate(widths or [22] * len(headers), start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    header_cells = []
    for header in headers:
        cell = WriteOnlyCell(sheet, value=header)
        cell.font = Font(bold=True)
        header_cells.append(cell)
    sheet.append(header_cells)
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def file_response(content: bytes, content_type: str, name: str, *, inline=False) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{name}"'
    return response
