"""Lieux, articles et exemplaires (INV.1, BIB.1, ATL.1), et import du catalogue depuis Excel.

Un livre est rangé à la bibliothèque ; un outil ou une matière dans un atelier. Chaque exemplaire
reçoit le numéro suivant de l'école (son étiquette QR), sous verrou de l'école : deux saisies en
même temps ne prennent jamais le même numéro.

Import (comme celui du personnel, R.1) : ni table ni tâche de fond. `check` lit le fichier et rend
l'aperçu ; à la validation, le même fichier est renvoyé et `record` le vérifie de nouveau, puis
crée titres et exemplaires d'un bloc. Un titre déjà au catalogue (même titre, même auteur) est
ignoré : un fichier envoyé deux fois ne crée rien deux fois."""

from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, Q, QuerySet
from django.utils import translation
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.actions import Action
from apps.core.documents import workbook
from apps.core.errors import ApiError, BusinessError
from apps.core.tenancy import require_current_school
from apps.finance.prior_payments import _amount
from apps.inventory.models import Copy, Item, Location
from apps.schools.models import Level, School
from apps.students import imports

# Exemplaires ajoutés d'un coup ; titres d'un fichier.
MAX_COPIES = 200
MAX_ROWS = 3000

WRONG_LOCATION = ApiError(
    "item_wrong_location",
    _("A book belongs to the library; a tool or a material to a workshop."),
    400,
)
LOCATION_INACTIVE = ApiError("location_inactive", _("This place is no longer in use."), 409)
NO_COPIES = ApiError("item_without_copies", _("A material has a quantity, not copies."), 400)
PRICE_CURRENCY = ApiError("price_currency", _("Give the price and its currency together."), 400)
MISSING_COLUMN = ApiError("missing_column", _("The file must have at least a title column."), 400)
TOO_MANY_ROWS = ApiError(
    "too_many_rows", _("Too many titles in one file: split it into several files."), 400
)
NOTHING_TO_RECORD = ApiError("nothing_to_record", _("No row can be recorded."), 409)
PREVIEW_OUTDATED = ApiError(
    "preview_outdated", _("The catalogue has changed since the preview: check again."), 409
)

TITLES = {
    "name": {"titre", "title", "ouvrage", "livre"},
    "author": {"auteur", "auteurs", "author"},
    "isbn": {"isbn"},
    "category": {"categorie", "category", "rubrique"},
    "level": {"niveau", "level"},
    "copies": {"exemplaires", "nombredexemplaires", "copies", "nombre", "quantite"},
    "price": {"prix", "price", "prixderemplacement"},
}
READY, SKIPPED, ERROR = "ready", "skipped", "error"


def lock_school() -> School:
    """Verrou de l'école : numéros des exemplaires, des prêts, des commandes et des bons."""
    return School.objects.select_for_update().get(pk=require_current_school().pk)


def next_copy_numbers(count: int) -> list[int]:
    """Numéros suivants de l'école, sous `lock_school`."""
    last = Copy.objects.aggregate(last=Max("number"))["last"] or 0
    return list(range(last + 1, last + 1 + count))


def library() -> Location:
    """La bibliothèque de l'école, créée au premier besoin (nommée dans la langue de la
    plateforme, renommable) ; une seule par école."""
    found = Location.objects.filter(kind=Location.Kind.LIBRARY).order_by("created_at").first()
    if found is not None:
        return found
    with transaction.atomic():
        lock_school()
        found = Location.objects.filter(kind=Location.Kind.LIBRARY).first()
        if found is None:
            with translation.override(settings.LANGUAGE_CODE):
                name = gettext("Library")
            found = Location.objects.create(name=name, kind=Location.Kind.LIBRARY)
    return found


def create_location(*, actor: User, name: str, kind: str) -> Location:
    return Location.objects.create(name=name, kind=kind, created_by=actor)


def _check_place(location: Location, kind: str) -> None:
    if not location.is_active:
        raise BusinessError(LOCATION_INACTIVE)
    in_library = location.kind == Location.Kind.LIBRARY
    if in_library != (kind == Item.Kind.BOOK):
        raise BusinessError(WRONG_LOCATION)


def _item_data(item: Item) -> dict:
    return {
        "location": item.location.name,
        "kind": item.kind,
        "name": item.name,
        "author": item.author,
        "price_minor": item.price_minor,
        "currency": item.currency,
        "alert_threshold": item.alert_threshold,
        "is_active": item.is_active,
    }


def save_item(item: Item | None, *, actor: User, copies: int = 0, **fields) -> Item:
    """Crée (`item` vide) ou modifie un article ; `copies` : exemplaires à créer avec un nouveau
    livre ou outil. Le lieu et la sorte d'un article ne changent plus après sa création."""
    creating = item is None
    item = item or Item(created_by=actor)
    before = {} if creating else _item_data(item)
    if not creating:
        fields.pop("location", None)
        fields.pop("kind", None)
    for name, value in fields.items():
        setattr(item, name, value)
    if (item.price_minor is None) != (not item.currency):
        raise BusinessError(PRICE_CURRENCY)
    if creating:
        _check_place(item.location, item.kind)
    with transaction.atomic():
        item.save()
        if creating and copies:
            add_copies(item, actor=actor, count=copies, journal=False)
        after = _item_data(item)
        audit.record(
            Action.INVENTORY_ITEM_CHANGED,
            item,
            actor=actor,
            before={key: value for key, value in before.items() if after[key] != value},
            after={key: value for key, value in after.items() if before.get(key) != value}
            | ({"copies": copies} if creating and copies else {}),
        )
    return item


def add_copies(item: Item, *, actor: User, count: int, journal: bool = True) -> list[Copy]:
    if not item.has_copies:
        raise BusinessError(NO_COPIES)
    with transaction.atomic():
        lock_school()
        copies = Copy.objects.bulk_create(
            [
                Copy(item=item, number=number, created_by=actor)
                for number in next_copy_numbers(count)
            ]
        )
        if journal:
            audit.record(
                Action.INVENTORY_COPIES_ADDED,
                item,
                actor=actor,
                after={"copies": [copy.code for copy in copies]},
            )
    return copies


def items(location: Location | None = None) -> QuerySet[Item]:
    """Articles avec le compte de leurs exemplaires par état (une requête)."""
    queryset = Item.objects.select_related("location", "level")
    if location is not None:
        queryset = queryset.filter(location=location)
    state = Copy.State
    return queryset.annotate(
        copies_total=Count("copies", filter=~Q(copies__state__in=[state.LOST, state.WITHDRAWN])),
        copies_available=Count("copies", filter=Q(copies__state=state.AVAILABLE)),
        copies_lent=Count("copies", filter=Q(copies__state=state.LENT)),
    )


# Import du catalogue (BIB.1)


@dataclass
class Line:
    number: int
    name: str
    author: str
    isbn: str
    category: str
    level_text: str
    copies_text: str
    price_text: str
    level: Level | None = None
    copies: int = 1
    price_minor: int | None = None
    status: str = READY
    issues: list[dict] = field(default_factory=list)

    def refuse(self, code: str, **params) -> None:
        self.status = ERROR
        self.issues.append({"code": code, **params})


@dataclass
class Preview:
    lines: list[Line]
    created: int = 0

    def count(self, status: str) -> int:
        return sum(line.status == status for line in self.lines)


def _read(file) -> list[Line]:
    _sheet, headers, rows = imports.read_file(file, set().union(*TITLES.values()))
    keys = [imports._key(header) for header in headers]
    columns = {
        name: next((i for i, key in enumerate(keys) if key in titles), None)
        for name, titles in TITLES.items()
    }
    if columns["name"] is None:
        raise BusinessError(MISSING_COLUMN)
    if len(rows) > MAX_ROWS:
        raise BusinessError(TOO_MANY_ROWS)

    def cell(cells: list[str], name: str) -> str:
        index = columns[name]
        return cells[index].strip() if index is not None and index < len(cells) else ""

    return [Line(number, *(cell(cells, name) for name in TITLES)) for number, cells in rows]


def _check(lines: list[Line], location: Location, currency: str) -> None:
    """Statut de chaque ligne ; deux requêtes quel que soit le nombre de lignes."""
    levels = {imports._key(level.name): level for level in Level.objects.all()}
    known = {
        (imports._key(name), imports._key(author))
        for name, author in Item.objects.filter(location=location).values_list("name", "author")
    }
    seen: dict[tuple[str, str], int] = {}
    for line in lines:
        key = (imports._key(line.name), imports._key(line.author))
        if not line.name:
            line.refuse("missing_title")
        elif len(line.name) > 200 or len(line.author) > 120:
            line.refuse("too_long")
        if line.level_text:
            line.level = levels.get(imports._key(line.level_text))
            if line.level is None:
                line.refuse("unknown_level", level=line.level_text)
        if line.copies_text:
            text = line.copies_text.removesuffix(".0")
            if not text.isdigit() or not 1 <= int(text) <= MAX_COPIES:
                line.refuse("invalid_copies")
            else:
                line.copies = int(text)
        if line.price_text:
            line.price_minor = _amount(line.price_text, currency)
            if line.price_minor is None:
                line.refuse("invalid_price")
        if line.name and key in seen:
            line.refuse("duplicate_title", line=seen[key])
        elif line.name:
            seen[key] = line.number
        if line.name and key in known:
            line.status, line.issues = SKIPPED, [{"code": "already_in_catalogue"}]


def check(file, *, location: Location, currency: str) -> Preview:
    """Aperçu d'un fichier : rien n'est écrit."""
    _check_place(location, Item.Kind.BOOK)
    lines = _read(file)
    _check(lines, location, currency)
    return Preview(lines)


def record(file, *, location: Location, currency: str, actor: User, expected: int) -> Preview:
    """Crée les titres prêts et leurs exemplaires d'un bloc. `expected` : lignes prêtes de
    l'aperçu validé ; 409 `preview_outdated` si ce nombre a changé."""
    _check_place(location, Item.Kind.BOOK)
    lines = _read(file)
    with transaction.atomic():
        lock_school()
        _check(lines, location, currency)
        ready = [line for line in lines if line.status == READY]
        if len(ready) != expected:
            raise BusinessError(PREVIEW_OUTDATED)
        if not ready:
            raise BusinessError(NOTHING_TO_RECORD)
        created = Item.objects.bulk_create(
            [
                Item(
                    location=location,
                    kind=Item.Kind.BOOK,
                    name=line.name,
                    author=line.author,
                    isbn=line.isbn[:20],
                    category=line.category[:60],
                    level=line.level,
                    price_minor=line.price_minor,
                    currency=currency if line.price_minor is not None else "",
                    created_by=actor,
                )
                for line in ready
            ]
        )
        numbers = iter(next_copy_numbers(sum(line.copies for line in ready)))
        Copy.objects.bulk_create(
            [
                Copy(item=item, number=next(numbers), created_by=actor)
                for item, line in zip(created, ready, strict=True)
                for _copy in range(line.copies)
            ]
        )
        audit.record(
            Action.INVENTORY_IMPORTED,
            location,
            actor=actor,
            after={"titles": len(ready), "copies": sum(line.copies for line in ready)},
        )
    return Preview(lines, created=len(ready))


def template_workbook() -> bytes:
    """Modèle à remplir : titres reconnus à l'import."""
    titles = [
        gettext("TITLE"),
        gettext("AUTHOR"),
        gettext("ISBN"),
        gettext("CATEGORY"),
        gettext("LEVEL"),
        gettext("COPIES"),
        gettext("PRICE"),
    ]
    return workbook(titles, [])
