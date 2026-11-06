"""Bibliothèque et ateliers [T] (lot 11, `docs/04` § Bibliothèque et ateliers).

Un lieu (`Location`) est la bibliothèque ou un atelier. Un article (`Item`) est un titre, un outil
ou une matière d'œuvre. Un livre ou un outil a des exemplaires (`Copy`), chacun avec son étiquette
QR (son numéro) ; une matière a une quantité, somme de ses mouvements (`Movement`), qui ne sont
jamais modifiés ni supprimés : une erreur se corrige par un mouvement inverse. Prêts, constats,
commandes, bons de sortie et inventaires ne sont jamais effacés non plus."""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel
from apps.core.money import Currency

# Un prêt est celui d'un élève ou d'un membre du personnel, jamais des deux.
ONE_HOLDER = Q(student__isnull=False, member__isnull=True) | Q(
    student__isnull=True, member__isnull=False
)


class ImmutableError(RuntimeError):
    """Écriture refusée : la ligne ne change plus une fois créée."""


class Location(TenantModel):
    """Lieu de stock : la bibliothèque, ou un atelier (mécanique, électricité…). Jamais effacé :
    désactivé, il ne reçoit plus d'article."""

    class Kind(models.TextChoices):
        LIBRARY = "library", _("Library")
        WORKSHOP = "workshop", _("Workshop")

    name = models.CharField(_("name"), max_length=80)
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        ordering = ["kind", "name"]
        verbose_name = _("location")
        verbose_name_plural = _("locations")
        constraints = [
            models.UniqueConstraint("school", Lower("name"), name="inventory_location_name")
        ]

    def __str__(self) -> str:
        return self.name


class Item(TenantModel):
    """Article d'un lieu : un titre (livre), un outil (ses exemplaires) ou une matière d'œuvre (une
    quantité). `price_minor` : prix de remplacement d'un exemplaire, ou prix unitaire estimé d'une
    matière, en entiers dans `currency`. `alert_threshold` : stock bas d'une matière (0 = aucune
    alerte). `reference_only` : ouvrage consulté sur place, jamais prêté."""

    class Kind(models.TextChoices):
        BOOK = "book", _("Book")
        TOOL = "tool", _("Tool")
        MATERIAL = "material", _("Material")

    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="items", verbose_name=_("location")
    )
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices)
    name = models.CharField(_("name"), max_length=200)
    author = models.CharField(_("author"), max_length=120, blank=True)
    isbn = models.CharField(_("ISBN"), max_length=20, blank=True)
    category = models.CharField(_("category"), max_length=60, blank=True)
    level = models.ForeignKey(
        "schools.Level",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("level"),
    )
    unit = models.CharField(_("unit"), max_length=20, blank=True)
    alert_threshold = models.PositiveIntegerField(_("alert threshold"), default=0)
    price_minor = models.BigIntegerField(
        _("price"), null=True, blank=True, validators=[MinValueValidator(0)]
    )
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices, blank=True)
    reference_only = models.BooleanField(_("reference only"), default=False)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("item")
        verbose_name_plural = _("items")
        constraints = [
            models.CheckConstraint(
                condition=Q(price_minor__isnull=True, currency="")
                | Q(price_minor__gte=0, currency__in=Currency.values),
                name="inventory_item_price_currency",
            )
        ]
        indexes = [models.Index(fields=["school", "location", "kind"], name="item_location_kind")]

    def __str__(self) -> str:
        return self.name

    @property
    def has_copies(self) -> bool:
        return self.kind != self.Kind.MATERIAL


# Préfixe du code imprimé sur l'étiquette : LIV-000414, OUT-000052.
COPY_PREFIX = {Item.Kind.BOOK: "LIV", Item.Kind.TOOL: "OUT"}


class Copy(TenantModel):
    """Exemplaire d'un livre ou d'un outil. `number` : suite de l'école, imprimée et contenue dans
    le QR de l'étiquette. Jamais effacé : `state` ne change que par un prêt, un retour, un constat
    ou un inventaire validé (`lost`, `withdrawn` : hors du catalogue)."""

    class State(models.TextChoices):
        AVAILABLE = "available", _("Available")
        LENT = "lent", _("Lent")
        LOST = "lost", _("Lost")
        WITHDRAWN = "withdrawn", _("Withdrawn")

    item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="copies", verbose_name=_("item")
    )
    number = models.PositiveIntegerField(_("number"), editable=False)
    state = models.CharField(
        _("state"), max_length=10, choices=State.choices, default=State.AVAILABLE
    )

    class Meta:
        ordering = ["number"]
        verbose_name = _("copy")
        verbose_name_plural = _("copies")
        constraints = [
            models.UniqueConstraint(fields=["school", "number"], name="inventory_copy_number")
        ]
        indexes = [models.Index(fields=["school", "item", "state"], name="copy_item_state")]

    def __str__(self) -> str:
        return self.code

    @property
    def code(self) -> str:
        return f"{COPY_PREFIX.get(self.item.kind, 'EX')}-{self.number:06d}"


class PurchaseOrder(TenantModel):
    """Commande de matériel d'un atelier (ATL.2) : demandée, validée ou refusée par la direction,
    achetée (une dépense FIN.1 liée, si l'école a le module des finances), puis reçue (entrées en
    stock). Montant de chaque ligne en entiers dans `currency`."""

    class Status(models.TextChoices):
        REQUESTED = "requested", _("Waiting for approval")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        PURCHASED = "purchased", _("Purchased")
        RECEIVED = "received", _("Received")

    number = models.CharField(_("number"), max_length=20, editable=False)
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="orders", verbose_name=_("workshop")
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.REQUESTED
    )
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices)
    note = models.CharField(_("note"), max_length=200, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("decided by"),
    )
    decided_at = models.DateTimeField(_("decided at"), null=True, blank=True)
    decision_note = models.CharField(_("decision note"), max_length=200, blank=True)
    expense = models.OneToOneField(
        "finance.Expense",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_order",
        verbose_name=_("expense"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("purchase order")
        verbose_name_plural = _("purchase orders")
        constraints = [
            models.UniqueConstraint(fields=["school", "number"], name="inventory_order_number")
        ]

    def __str__(self) -> str:
        return self.number


class PurchaseOrderLine(TenantModel):
    order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="lines", verbose_name=_("order")
    )
    item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="order_lines", verbose_name=_("item")
    )
    quantity = models.PositiveIntegerField(_("quantity"), validators=[MinValueValidator(1)])
    unit_price_minor = models.BigIntegerField(
        _("unit price"), default=0, validators=[MinValueValidator(0)]
    )
    # Déjà reçu : somme des réceptions (entrées en stock ou exemplaires créés).
    received = models.PositiveIntegerField(_("received"), default=0)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = _("order line")
        verbose_name_plural = _("order lines")
        constraints = [
            models.CheckConstraint(
                condition=Q(received__lte=models.F("quantity")), name="order_line_not_over"
            )
        ]


class IssueSlip(TenantModel):
    """Bon de sortie (ATL.2) : matière retirée de l'atelier par un enseignant, pour une classe et
    un travail pratique ; chaque ligne est un mouvement de sortie."""

    number = models.CharField(_("number"), max_length=20, editable=False)
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="slips", verbose_name=_("workshop")
    )
    class_group = models.ForeignKey(
        "schools.ClassGroup",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("class"),
    )
    work = models.CharField(_("practical work"), max_length=120, blank=True)
    taken_by = models.ForeignKey(
        "accounts.Membership",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("taken by"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("issue slip")
        verbose_name_plural = _("issue slips")
        constraints = [
            models.UniqueConstraint(fields=["school", "number"], name="inventory_slip_number")
        ]

    def __str__(self) -> str:
        return self.number


class Stocktake(TenantModel):
    """Inventaire d'un lieu (INV.1) : comptage (étiquettes scannées, quantités) qui ne change rien
    tant que la direction ne l'a pas validé ; la validation crée les mouvements de régularisation
    et change l'état des exemplaires. Un seul comptage ouvert par lieu."""

    class Status(models.TextChoices):
        OPEN = "open", _("Counting")
        VALIDATED = "validated", _("Validated")

    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="stocktakes", verbose_name=_("location")
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.OPEN
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("validated by"),
    )
    validated_at = models.DateTimeField(_("validated at"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("stocktake")
        verbose_name_plural = _("stocktakes")
        constraints = [
            models.UniqueConstraint(
                fields=["location"], condition=Q(status="open"), name="one_open_stocktake"
            )
        ]


class StocktakeCount(TenantModel):
    """Une ligne du comptage : un exemplaire scanné (`copy`, quantité 1), ou la quantité comptée
    d'une matière. À la validation, chaque exemplaire attendu et non scanné reçoit une ligne à 0 :
    non retrouvé une seconde fois, il passe « perdu »."""

    stocktake = models.ForeignKey(
        Stocktake, on_delete=models.PROTECT, related_name="counts", verbose_name=_("stocktake")
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")
    copy = models.ForeignKey(
        Copy, on_delete=models.PROTECT, null=True, blank=True, related_name="counts"
    )
    quantity = models.PositiveIntegerField(_("counted"), default=0)

    class Meta:
        verbose_name = _("stocktake count")
        verbose_name_plural = _("stocktake counts")
        constraints = [
            models.UniqueConstraint(
                fields=["stocktake", "copy"],
                condition=Q(copy__isnull=False),
                name="stocktake_one_count_per_copy",
            ),
            models.UniqueConstraint(
                fields=["stocktake", "item"],
                condition=Q(copy__isnull=True),
                name="stocktake_one_count_per_material",
            ),
        ]


class Movement(TenantModel):
    """Mouvement de stock d'une matière d'œuvre [immuable] : le stock est leur somme, jamais un
    compteur modifié. Une erreur se corrige par le mouvement inverse (`reverses`), une fois."""

    class Kind(models.TextChoices):
        OPENING = "opening", _("Opening stock")
        RECEIPT = "receipt", _("Reception")
        ISSUE = "issue", _("Issue")
        CORRECTION = "correction", _("Correction")
        STOCKTAKE = "stocktake", _("Stocktake")

    item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="movements", verbose_name=_("item")
    )
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices)
    quantity = models.IntegerField(_("quantity"))
    reason = models.CharField(_("reason"), max_length=200, blank=True)
    order_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    issue_slip = models.ForeignKey(
        IssueSlip, on_delete=models.PROTECT, null=True, blank=True, related_name="movements"
    )
    stocktake = models.ForeignKey(
        Stocktake, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reverses = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversed_by"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("stock movement")
        verbose_name_plural = _("stock movements")
        constraints = [models.CheckConstraint(condition=~Q(quantity=0), name="movement_not_zero")]
        indexes = [models.Index(fields=["school", "item"], name="movement_item")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableError("Un mouvement de stock ne se modifie pas : mouvement inverse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError("Un mouvement de stock ne s'efface pas : mouvement inverse.")


class Loan(TenantModel):
    """Prêt d'un exemplaire (BIB.2, ATL.3) à un élève ou à un membre du personnel, fait au guichet
    même sans réseau (opération `inventory.loan`). `number` : N° du bon de prêt, suite de l'école.
    Un exemplaire n'a qu'un prêt ouvert : un second, rejoué d'un autre appareil, est refusé
    (« déjà prêté »). Le retour ou le constat le ferme (`returned_at`, `return_condition`)."""

    class Condition(models.TextChoices):
        GOOD = "good", _("Good")
        WORN = "worn", _("Worn")
        DAMAGED = "damaged", _("Damaged")
        LOST = "lost", _("Lost")

    number = models.PositiveIntegerField(_("number"), editable=False)
    copy = models.ForeignKey(
        Copy, on_delete=models.PROTECT, related_name="loans", verbose_name=_("copy")
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="loans",
        verbose_name=_("student"),
    )
    member = models.ForeignKey(
        "accounts.Membership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="loans",
        verbose_name=_("staff member"),
    )
    lent_at = models.DateTimeField(_("lent at"))
    due_on = models.DateField(_("due on"))
    extensions = models.PositiveSmallIntegerField(_("extensions"), default=0)
    returned_at = models.DateTimeField(_("returned at"), null=True, blank=True)
    return_condition = models.CharField(
        _("condition on return"), max_length=10, choices=Condition.choices, blank=True
    )
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("taken back by"),
    )
    device = models.ForeignKey(
        "sync.Device", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # Rappels (BIB.3) : nombre envoyés et jour du dernier, une fois par jour au plus.
    reminders = models.PositiveSmallIntegerField(_("reminders"), default=0)
    reminded_on = models.DateField(_("last reminder"), null=True, blank=True)

    class Meta:
        ordering = ["-lent_at"]
        verbose_name = _("loan")
        verbose_name_plural = _("loans")
        constraints = [
            models.CheckConstraint(condition=ONE_HOLDER, name="loan_one_holder"),
            models.UniqueConstraint(fields=["school", "number"], name="inventory_loan_number"),
            models.UniqueConstraint(
                fields=["copy"], condition=Q(returned_at__isnull=True), name="one_open_loan"
            ),
        ]
        indexes = [
            models.Index(fields=["school", "returned_at", "due_on"], name="loan_open_due"),
            models.Index(fields=["school", "student"], name="loan_student"),
        ]

    def __str__(self) -> str:
        return f"{self.number}"


class LossReport(TenantModel):
    """Constat de perte ou d'abîmé (BIB.3, ATL.3). Pour un élève, des frais de remplacement
    (`amount_minor` > 0) deviennent une dette (`charge`, un `StudentCharge` payé à la caisse avec
    un reçu normal). Jamais effacé : une erreur se corrige par un constat de rectification
    (`corrects`), qui remet l'exemplaire en service et retire la dette encore impayée."""

    class Kind(models.TextChoices):
        LOST = "lost", _("Lost")
        DAMAGED = "damaged", _("Damaged")
        CORRECTION = "correction", _("Correction")

    copy = models.ForeignKey(
        Copy, on_delete=models.PROTECT, related_name="reports", verbose_name=_("copy")
    )
    loan = models.ForeignKey(
        Loan, on_delete=models.PROTECT, null=True, blank=True, related_name="reports"
    )
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices)
    note = models.CharField(_("note"), max_length=200)
    amount_minor = models.BigIntegerField(_("amount"), default=0, validators=[MinValueValidator(0)])
    currency = models.CharField(_("currency"), max_length=3, choices=Currency.choices, blank=True)
    charge = models.OneToOneField(
        "finance.StudentCharge",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="loss_report",
        verbose_name=_("charge"),
    )
    corrects = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="corrected_by"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("loss report")
        verbose_name_plural = _("loss reports")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_minor=0) | Q(currency__in=Currency.values),
                name="loss_report_currency",
            )
        ]
