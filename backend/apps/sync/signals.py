"""Chaque enregistrement ou suppression d'un modèle descendu sur les appareils note son entité
dans le `ChangeLog` (`changes.py`), dans la transaction du changement."""

from django.db.models.signals import post_delete, post_save

from apps.core.tenancy import use_school
from apps.finance.models import (
    CashRegister,
    Discount,
    ExchangeRate,
    FeeType,
    Payment,
    PaymentCancellation,
    StudentCharge,
)
from apps.schools.models import AcademicYear, ClassGroup, Level, School, Track
from apps.students.models import Enrollment, Student
from apps.sync import changes

# Inscriptions dont le contenu change avec la ligne.
ENROLLMENTS_OF = {
    Enrollment: lambda enrollment: [enrollment.pk],
    StudentCharge: lambda charge: [charge.enrollment_id],
    Discount: lambda discount: [discount.enrollment_id],
    Payment: lambda payment: [payment.enrollment_id],
    PaymentCancellation: lambda cancellation: [cancellation.payment.enrollment_id],
    Student: lambda student: Enrollment.all_schools.filter(
        school_id=student.school_id, student_id=student.pk
    ).values_list("pk", flat=True),
}
CONFIG_MODELS = (
    School,
    AcademicYear,
    Level,
    Track,
    ClassGroup,
    FeeType,
    CashRegister,
    ExchangeRate,
)


def _enrollment_saved(sender, instance, raw=False, **kwargs):
    if not raw:
        changes.touch_enrollments(ENROLLMENTS_OF[sender](instance), school_id=instance.school_id)


def _enrollment_deleted(sender, instance, **kwargs):
    if sender is Enrollment:
        changes.touch_enrollments(
            [instance.pk], school_id=instance.school_id, operation=changes.Operation.DELETE
        )
    else:
        _enrollment_saved(sender, instance)


def _config_changed(sender, instance, raw=False, **kwargs):
    if raw:
        return
    if sender is not School:
        changes.touch_config(instance.school_id)
        return
    # Une école se crée ou se modifie aussi depuis l'administration ou une autre école.
    with use_school(instance):
        changes.touch_config(instance.pk)


def connect() -> None:
    for model in ENROLLMENTS_OF:
        post_save.connect(_enrollment_saved, sender=model, dispatch_uid=f"sync_{model.__name__}")
        post_delete.connect(
            _enrollment_deleted, sender=model, dispatch_uid=f"sync_del_{model.__name__}"
        )
    for model in CONFIG_MODELS:
        post_save.connect(_config_changed, sender=model, dispatch_uid=f"sync_{model.__name__}")
        if model is School:
            continue  # Une école n'est jamais effacée.
        post_delete.connect(
            _config_changed, sender=model, dispatch_uid=f"sync_del_{model.__name__}"
        )
