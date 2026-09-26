"""Modèles de base : identifiant UUID v7, dates, auteur, et lien obligatoire à une école
(`TenantModel`)."""

from django.conf import settings
from django.db import models

from apps.core.ids import uuid7
from apps.core.tenancy import (
    AllSchoolsManager,
    CrossSchoolError,
    SchoolNotSetError,
    TenantManager,
    get_current_school,
)


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Rempli par les services ; vide pour ce que crée le système (migrations, `make demo`).
    # Un compte n'est jamais supprimé (on le désactive) : PROTECT garde l'auteur.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )

    class Meta:
        abstract = True


class TenantModel(BaseModel):
    """Donnée d'une école [T]. Lecture : `objects` ne voit que l'école courante et lève une erreur
    sans école. Écriture : l'école est remplie depuis l'école courante ; toute écriture ou
    suppression qui toucherait une autre école lève `CrossSchoolError`."""

    # Pas d'accès inverse depuis l'école (`school.note_set`) : on lit toujours depuis le modèle.
    school = models.ForeignKey(
        "schools.School", on_delete=models.PROTECT, related_name="+", editable=False
    )

    objects = TenantManager()
    all_schools = AllSchoolsManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.check_school()
        super().save(*args, **kwargs)
        self._school_id_in_db = self.school_id

    def delete(self, *args, **kwargs):
        self._check_current_school()
        return super().delete(*args, **kwargs)

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        # École en base au chargement : une ligne ne change jamais d'école.
        instance._school_id_in_db = instance.__dict__.get("school_id")
        return instance

    def check_school(self) -> None:
        """Contrôles faits avant chaque écriture (`save`, `bulk_create`)."""
        if self.school_id is None:
            current = get_current_school()
            if current is None:
                raise SchoolNotSetError("Ligne sans école et aucune école courante.")
            self.school = current
        self._check_current_school()
        school_id_in_db = getattr(self, "_school_id_in_db", None)
        if school_id_in_db is not None and school_id_in_db != self.school_id:
            raise CrossSchoolError(
                "Une ligne ne change jamais d'école : un transfert est une copie (décision Q10)."
            )
        self._check_links()

    def _check_current_school(self) -> None:
        current = get_current_school()
        if current is not None and self.school_id != current.pk:
            raise CrossSchoolError(
                f"{type(self).__name__} appartient à une autre école que l'école courante."
            )

    def _check_links(self) -> None:
        """Refuse un lien (clé étrangère) vers une ligne d'une autre école."""
        for field in self._meta.concrete_fields:
            if not isinstance(field, models.ForeignKey) or field.name == "school":
                continue
            if not issubclass(field.related_model, TenantModel):
                continue
            value = getattr(self, field.attname)
            if value is None:
                continue
            if field.is_cached(self):
                related = field.get_cached_value(self)
                related_school_id = getattr(related, "school_id", None)
            else:
                related_school_id = (
                    field.related_model.all_schools.filter(**{field.target_field.attname: value})
                    .values_list("school_id", flat=True)
                    .first()
                )
            if related_school_id is not None and related_school_id != self.school_id:
                raise CrossSchoolError(
                    f"{type(self).__name__}.{field.name} pointe vers une ligne d'une autre école."
                )
