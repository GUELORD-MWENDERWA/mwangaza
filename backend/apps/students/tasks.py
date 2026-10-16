"""Tâches de fond des élèves : import d'une liste (D1)."""

import logging

from celery import shared_task

from apps.accounts.models import User
from apps.audit.context import RequestInfo, use_request_info
from apps.core.tenancy import use_all_schools, use_school
from apps.students import imports
from apps.students.models import StudentImport

logger = logging.getLogger(__name__)


@shared_task(soft_time_limit=840, time_limit=900)
def run_student_import(import_id: str, actor_id: str, request: dict) -> None:
    """Import confirmé par `actor_id`. Le journal garde l'adresse, le navigateur et la session
    support de la requête qui l'a lancé (`imports.confirm`)."""
    with use_all_schools():
        imp = StudentImport.all_schools.select_related("school").get(pk=import_id)
    actor = User.objects.get(pk=actor_id)
    impersonated_by = request.get("impersonated_by")
    info = RequestInfo(
        ip=request.get("ip"),
        user_agent=request.get("user_agent", ""),
        impersonated_by=User.objects.get(pk=impersonated_by) if impersonated_by else None,
        support_school_id=imp.school_id if impersonated_by else None,
    )
    with use_school(imp.school), use_request_info(info):
        try:
            imports.run(imp, actor=actor)
        except Exception:
            logger.exception("Import d'élèves %s échoué", import_id)
            imports.fail(imp)
