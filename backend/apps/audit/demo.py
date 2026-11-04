"""Alertes de sécurité fictives (S.8) pour la console en mode démonstration : une de chaque sorte
sur le premier espace de démonstration, seulement s'il n'y en a aucune depuis 7 jours (le journal
ne s'efface pas : pas de double à chaque `make demo`). Jamais d'envoi sur l'écran de l'équipe."""

from datetime import timedelta

from django.utils import timezone

from apps.audit import security
from apps.audit import services as audit
from apps.audit.actions import PlatformAction
from apps.audit.models import PlatformAuditLog
from apps.schools.models import School
from apps.sync.models import Device

# Numéro du bloc fictif, sans compte : quelqu'un essaie des mots de passe au hasard.
TARGETED_PHONE = "+243000000777"


def create_demo_security() -> None:
    recent = PlatformAuditLog.objects.filter(
        is_demo=True,
        action__startswith=f"{security.DOMAIN}.",
        created_at__gte=timezone.now() - timedelta(days=security.SHOWN_DAYS),
    )
    school = School.objects.filter(environment=School.Environment.DEMO).order_by("created_at")
    school = school.first()
    if school is None or recent.exists():
        return
    audit.record_platform(
        PlatformAction.SECURITY_LOGIN_BURST,
        actor=None,
        label=TARGETED_PHONE,
        after={"scope": "phone", "failures": security.LOGIN_PHONE_FAILURES, "hours": 24},
        demo=True,
    )
    audit.record_platform(
        PlatformAction.SECURITY_CANCELLATIONS,
        school,
        actor=None,
        label=school.name,
        after={"today": 7, "previous_30_days": 12},
    )
    device = Device.all_schools.filter(school=school).select_related("user").first()
    if device is not None:
        audit.record_platform(
            PlatformAction.SECURITY_REVOKED_DEVICE,
            device,
            actor=None,
            label=f"{device} · {school.name}",
            after={"attempts": security.REVOKED_CONTACTS, "user": device.user.get_full_name()},
        )
