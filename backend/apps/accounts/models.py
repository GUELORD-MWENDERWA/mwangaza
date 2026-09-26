"""Comptes, rôles et appartenances (`docs/04-modele-de-donnees.md` § 1 et § 8).

- `User` [G] : une personne, un numéro de téléphone, un seul compte dans toutes les écoles (B3).
- `Role` [T] : rôle d'une école ; les 9 rôles système y sont copiés à sa création (B1), l'école
  crée les siens (B2).
- `Membership` [G] : la personne dans une école, avec ses rôles de cette école.
"""

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.accounts.phone import InvalidPhoneError, PhoneNumberField, normalize_phone
from apps.accounts.roles import PERMISSION_CHOICES, SYSTEM_ROLE_CODES, SYSTEM_ROLES
from apps.core.models import BaseModel, TenantModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, phone):
        # Connexion avec le numéro tel qu'on le tape (0971234567) : même forme qu'en base.
        try:
            phone = normalize_phone(phone)
        except InvalidPhoneError:
            raise self.model.DoesNotExist from None
        return self.get(phone=phone)

    def create_user(self, phone, password=None, **fields):
        user = self.model(phone=normalize_phone(phone), **fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **fields):
        fields["is_platform_admin"] = True
        return self.create_user(phone, password, **fields)


class User(BaseModel, AbstractBaseUser):
    """Compte d'une personne [G], identifié par son numéro de téléphone.

    Une école ne modifie jamais le compte lui-même (nom, téléphone, mot de passe) : il peut servir
    dans une autre école. Elle gère seulement l'appartenance de la personne à l'école."""

    class Language(models.TextChoices):
        FRENCH = "fr", "Français"
        ENGLISH = "en", "English"

    phone = PhoneNumberField(
        _("phone"),
        unique=True,
        help_text=_("Identifies the person on the whole platform, e.g. +243971234567."),
    )
    last_name = models.CharField(_("last name"), max_length=100)
    # Post-nom : nom, post-nom, prénom (usage en RDC).
    middle_name = models.CharField(_("middle name"), max_length=100, blank=True)
    first_name = models.CharField(_("first name"), max_length=100, blank=True)
    language = models.CharField(
        _("language"), max_length=5, choices=Language.choices, default=Language.FRENCH
    )
    is_active = models.BooleanField(_("active"), default=True)
    is_platform_admin = models.BooleanField(
        _("platform administrator"),
        default=False,
        help_text=_("Mwangaza super-administrator: Django administration only, no school rights."),
    )
    # Mot de passe provisoire donné par l'école : à changer à la connexion (tâche 1.3).
    must_change_password = models.BooleanField(_("must change password"), default=False)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["last_name", "first_name"]

    class Meta:
        ordering = ["last_name", "middle_name", "first_name"]
        verbose_name = _("account")
        verbose_name_plural = _("accounts")

    def __str__(self) -> str:
        return self.get_full_name() or self.phone

    def get_full_name(self) -> str:
        return " ".join(
            part for part in (self.last_name, self.middle_name, self.first_name) if part
        )

    def get_short_name(self) -> str:
        return self.first_name or self.last_name

    # Administration Django : réservée au super-admin. Les droits dans une école viennent de ses
    # rôles (`HasSchoolPermission`), jamais d'ici.
    @property
    def is_staff(self) -> bool:
        return self.is_platform_admin

    def has_perm(self, perm, obj=None) -> bool:
        return self.is_active and self.is_platform_admin

    def has_perms(self, perm_list, obj=None) -> bool:
        return all(self.has_perm(perm, obj) for perm in perm_list)

    def has_module_perms(self, app_label) -> bool:
        return self.is_active and self.is_platform_admin


class Role(TenantModel):
    """Rôle d'une école [T] : un ensemble de codes de permissions.

    Rôle système : `code` (`head`, `cashier`…), nom vide = l'interface affiche le nom traduit ;
    l'école peut le renommer et changer ses permissions, pas le supprimer. Rôle de l'école
    (ex. « Chef d'atelier ») : sans code, avec un nom."""

    code = models.CharField(
        _("code"),
        max_length=30,
        blank=True,
        editable=False,
        choices=[(code, role.label) for code, role in SYSTEM_ROLES.items()],
    )
    name = models.CharField(_("name"), max_length=80, blank=True)
    permissions = ArrayField(
        models.CharField(max_length=50, choices=PERMISSION_CHOICES),
        verbose_name=_("permissions"),
        default=list,
        blank=True,
    )

    class Meta:
        # UUID v7 croissants : rôles système dans l'ordre de `docs/04` § 8, puis ceux de l'école.
        ordering = ["id"]
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=~models.Q(code=""),
                name="role_code_unique_per_school",
            ),
            models.UniqueConstraint(
                models.F("school"),
                Lower("name"),
                condition=~models.Q(name=""),
                name="role_name_unique_per_school",
            ),
            models.CheckConstraint(
                condition=models.Q(code="") | models.Q(code__in=SYSTEM_ROLE_CODES),
                name="role_code_is_a_system_role",
            ),
            models.CheckConstraint(
                condition=~models.Q(code="") | ~models.Q(name=""),
                name="role_has_code_or_name",
            ),
        ]

    def __str__(self) -> str:
        return str(self.display_name)

    @property
    def is_system(self) -> bool:
        return bool(self.code)

    @property
    def display_name(self):
        return self.name or SYSTEM_ROLES[self.code].label


class Membership(BaseModel):
    """Une personne dans une école [G], avec ses rôles de cette école (plusieurs possibles).

    Global pour lister les écoles d'un compte (choix de l'école, M2) ; toujours lu avec l'école
    explicite côté école. Un rôle d'une autre école est refusé (`signals.py`)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="memberships",
        verbose_name=_("account"),
    )
    school = models.ForeignKey(
        "schools.School", on_delete=models.PROTECT, related_name="+", verbose_name=_("school")
    )
    roles = models.ManyToManyField(
        Role, related_name="memberships", blank=True, verbose_name=_("roles")
    )
    # Désactivé : plus aucun accès à cette école ; le compte reste valable ailleurs.
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")
        constraints = [
            models.UniqueConstraint(fields=["user", "school"], name="membership_unique_per_school")
        ]
        indexes = [models.Index(fields=["school", "is_active"], name="membership_school_active")]

    def __str__(self) -> str:
        return f"{self.user} — {self.school}"
