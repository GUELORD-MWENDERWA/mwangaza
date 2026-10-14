"""Administration Django : le journal de toutes les écoles, en lecture seule (support)."""

import pytest

from apps.audit.actions import Action
from apps.audit.models import AuditLog
from apps.core.tenancy import use_all_schools, use_school

pytestmark = pytest.mark.django_db


def test_the_journal_is_read_only_in_the_admin(admin_client, school, other_school):
    with use_school(school):
        log = AuditLog.objects.create(action=Action.ROLES_CREATED, entity_label="Chef d'atelier")
    with use_school(other_school):
        AuditLog.objects.create(action=Action.ROLES_DELETED, entity_label="Magasinier")

    content = admin_client.get("/admin/audit/auditlog/").content.decode()
    assert "Chef d&#x27;atelier" in content
    assert "Magasinier" in content
    assert admin_client.get(f"/admin/audit/auditlog/{log.id}/change/").status_code == 200

    assert admin_client.get("/admin/audit/auditlog/add/").status_code == 403
    response = admin_client.post(f"/admin/audit/auditlog/{log.id}/delete/", {"post": "yes"})
    assert response.status_code == 403
    response = admin_client.post(
        f"/admin/audit/auditlog/{log.id}/change/", {"entity_label": "Autre chose"}
    )
    assert response.status_code == 403
    with use_all_schools():
        assert AuditLog.all_schools.get(pk=log.pk).entity_label == "Chef d'atelier"
