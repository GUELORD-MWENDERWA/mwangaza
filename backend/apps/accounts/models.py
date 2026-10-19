"""Comptes, rôles et appartenances (`docs/04-modele-de-donnees.md` § 1 et § 8).

- `User` [G] : une personne, un numéro de téléphone, un seul compte dans toutes les écoles (B3).
- `Role` [T] : rôle d'une école ; les 9 rôles système y sont copiés à sa création (B1), l'école
  crée les siens (B2).
- `Membership` [G] : la personne dans une école, avec ses rôles de cette école.
- `RecoveryCode` [G] et `LoginFailure` [G] : codes de secours et essais ratés (B4).
"""

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.accounts.phone import InvalidPhoneError, PhoneNumberField, normalize_phone
from apps.accounts.platform_roles import OWNER, ROLE_CHOICES, permissions_of
from apps.accounts.roles import PERMISSION_CHOICES
from apps.core.models import BaseModel, TenantModel
from apps.schools.signatures import member_signature_path


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
        """Propriétaire de la plateforme (`createsuperuser`) : le reste de l'équipe est invité
        depuis la console (EQ.1)."""
        fields["is_platform_admin"] = True
        fields.setdefault("platform_roles", [OWNER])
        return self.create_user(phone, password, **fields)


class User(BaseModel, AbstractBaseUser):
    """Compte d'une personne [G], identifié par son numéro de téléphone.

    Une école gère l'appartenance de la personne à l'école. Elle ne modifie le compte lui-même
    (noms, téléphone, mot de passe, double authentification) que s'il ne sert dans aucune autre
    école (`services.account_managed_by`) : sinon, le support de la plateforme s'en charge."""

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
        _("platform account"),
        default=False,
        help_text=_(
            "Account of the platform team: console with the rights of its roles, two-factor "
            "authentication always required, no school rights."
        ),
    )
    # Rôles fixes de l'équipe (`platform_roles.py`) ; vide hors de l'équipe ou une fois retiré.
    platform_roles = ArrayField(
        models.CharField(max_length=32, choices=ROLE_CHOICES),
        verbose_name=_("platform roles"),
        default=list,
        blank=True,
    )
    # Mot de passe provisoire donné par l'école : à changer à la connexion.
    must_change_password = models.BooleanField(_("must change password"), default=False)
    # Double authentification (B4) : clé TOTP chiffrée (`apps/core/crypto.py`), date
    # d'activation, dernière période de 30 s utilisée (un code ne sert qu'une fois).
    totp_secret = models.CharField(_("TOTP key"), max_length=255, blank=True, editable=False)
    totp_enabled_at = models.DateTimeField(
        _("two-factor authentication enabled on"), null=True, blank=True, editable=False
    )
    totp_last_step = models.BigIntegerField(default=0, editable=False)

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

    @property
    def totp_enabled(self) -> bool:
        return self.totp_enabled_at is not None

    @property
    def platform_permissions(self) -> frozenset[str]:
        """Droits dans la console, d'après les rôles de l'équipe (lus avec le compte : aucune
        requête de plus)."""
        if not (self.is_active and self.is_platform_admin):
            return frozenset()
        return permissions_of(self.platform_roles)

    @property
    def is_platform_owner(self) -> bool:
        return self.is_active and self.is_platform_admin and OWNER in self.platform_roles

    # Administration Django (dépannage, elle peut tout changer) : réservée au propriétaire de la
    # plateforme. Les droits dans une école viennent de ses rôles (`HasSchoolPermission`), jamais
    # d'ici.
    @property
    def is_staff(self) -> bool:
        return self.is_platform_owner

    def has_perm(self, perm, obj=None) -> bool:
        return self.is_platform_owner

    def has_perms(self, perm_list, obj=None) -> bool:
        return all(self.has_perm(perm, obj) for perm in perm_list)

    def has_module_perms(self, app_label) -> bool:
        return self.is_platform_owner


class Role(TenantModel):
    """Rôle d'une école [T] : un nom et un ensemble de codes de permissions.

    Tous les rôles sont ceux de l'école : elle les renomme, change leurs permissions et les
    supprime (s'ils ne sont donnés à personne). Une école neuve reçoit le modèle de départ
    (`roles.STARTER_ROLES`), rien de plus : aucun rôle n'a de code ni de statut à part."""

    name = models.CharField(_("name"), max_length=80)
    permissions = ArrayField(
        models.CharField(max_length=50, choices=PERMISSION_CHOICES),
        verbose_name=_("permissions"),
        default=list,
        blank=True,
    )

    class Meta:
        # UUID v7 croissants : rôles du modèle de départ dans l'ordre de `docs/04` § 8, puis ceux
        # que l'école a créés.
        ordering = ["id"]
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        constraints = [
            models.UniqueConstraint(
                models.F("school"), Lower("name"), name="role_name_unique_per_school"
            ),
            models.CheckConstraint(condition=~models.Q(name=""), name="role_has_a_name"),
        ]

    def __str__(self) -> str:
        return self.name


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
    # Dernière connexion à l'adresse de cette école : l'école ne voit pas celles des autres.
    last_login_at = models.DateTimeField(_("last login"), null=True, blank=True, editable=False)
    # Posée sur les documents que la personne donne (reçu, convocation…), DOC.1 : propre à
    # l'école, comme tout ce qu'elle y fait ; déposée dans « Mon compte ».
    signature = models.FileField(
        _("signature"), upload_to=member_signature_path, blank=True, editable=False
    )

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


class RecoveryCode(BaseModel):
    """Code de secours de la double authentification [G] : 8 par compte, à usage unique (M1).

    Seule son empreinte est gardée (HMAC avec la clé du serveur) : une fuite de la base ne les
    livre pas."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recovery_codes",
        verbose_name=_("account"),
    )
    digest = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(_("used on"), null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("recovery code")
        verbose_name_plural = _("recovery codes")


class LoginFailure(BaseModel):
    """Essai de connexion raté [G] : mot de passe, code de double authentification ou mot de
    passe actuel. Sert à bloquer un numéro ou une adresse IP (`attempts.py`) ; effacé à la
    connexion réussie, purgé au bout d'un jour."""

    # Numéro tapé, au format E.164 s'il est valable : un numéro sans compte est bloqué pareil.
    phone = models.CharField(_("phone"), max_length=64)
    ip = models.GenericIPAddressField(_("IP address"), null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("failed login")
        verbose_name_plural = _("failed logins")
        indexes = [
            models.Index(fields=["phone", "created_at"], name="loginfailure_phone"),
            models.Index(fields=["ip", "created_at"], name="loginfailure_ip"),
            models.Index(fields=["created_at"], name="loginfailure_created"),
        ]

    def __str__(self) -> str:
        return f"{self.phone} — {self.created_at:%Y-%m-%d %H:%M}"
