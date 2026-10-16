"""PDF gardés (PERF.2) : un bulletin n'est mis en page qu'une fois, refait quand ses données
changent (l'ancien fichier part), jamais visible d'une autre école, purgé s'il n'est plus lu."""

import io
from datetime import timedelta
from uuid import UUID

import pytest
import weasyprint
from django.utils import timezone
from pypdf import PdfReader

from apps.academics.models import Grade
from apps.academics.tests.test_grades import setup
from apps.academics.tests.test_report_card_documents import url, validate_all
from apps.academics.tests.test_report_cards import put
from apps.core import kept, printing
from apps.core.models import KeptDocument
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def chief(school):
    return MembershipFactory(school=school, roles=["study_director"]).user


@pytest.fixture
def klass(school, head):
    data = setup(school, head)
    amani, josue = data["amani"], data["josue"]
    put(school, data["physics"], data["p1"], "Interro", 20, {amani: "18", josue: "8"})
    put(school, data["workshop"], data["p1"], "TP", 100, {amani: "80", josue: "80"})
    validate_all(school, data)
    return data


@pytest.fixture
def layouts(monkeypatch):
    """Compte les mises en page WeasyPrint."""
    calls = []
    original = weasyprint.HTML.write_pdf

    def counting(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(weasyprint.HTML, "write_pdf", counting)
    return calls


def documents(school) -> list[KeptDocument]:
    with use_school(school):
        return list(KeptDocument.objects.order_by("created_at"))


def pages(response) -> int:
    return len(PdfReader(io.BytesIO(response.content)).pages)


def test_a_reprinted_class_is_read_from_files_and_a_changed_grade_remakes_only_its_report_card(
    api, school, chief, klass, layouts
):
    client = api(chief)
    assert pages(client.get(url(klass), output="pdf")) == 2
    assert len(layouts) == 2 and len(documents(school)) == 2

    layouts.clear()
    assert pages(client.get(url(klass), output="pdf")) == 2
    assert layouts == []  # aucune mise en page : deux fichiers lus

    with use_school(school):
        grade = Grade.objects.get(enrollment_id=klass["josue"], evaluation__name="Interro")
        grade.score = 9
        grade.save()
    before = {d.subject: d.key for d in documents(school)}
    assert pages(client.get(url(klass), output="pdf")) == 2
    after = {d.subject: d.key for d in documents(school)}
    assert len(after) == 2  # l'ancien fichier est effacé, pas gardé en double
    assert after[UUID(klass["josue"])] != before[UUID(klass["josue"])]
    assert 1 <= len(layouts) <= 2


def test_a_class_in_the_background_only_makes_the_missing_pages(
    api, school, chief, klass, layouts, monkeypatch
):
    client = api(chief)
    client.get(url(klass), output="pdf", enrollment=str(klass["amani"]))
    assert len(layouts) == 1
    layouts.clear()
    monkeypatch.setattr(printing, "INLINE_MAX_PAGES", 0)  # tout passe par la tâche de fond
    response = client.get(url(klass), output="pdf")
    assert (response.status_code, pages(response)) == (200, 2)
    assert len(layouts) == 1  # seul le bulletin de Josué manquait
    assert len(documents(school)) == 2


def test_a_kept_pdf_is_never_seen_by_another_school(school, other_school, klass, api, chief):
    api(chief).get(url(klass), output="pdf")
    [document] = documents(school)[:1]
    with use_school(other_school):
        assert kept.lookup([document.key]) == {}
        assert KeptDocument.objects.count() == 0
        assert kept.fingerprint("<html></html>") != _fingerprint_in(school)


def _fingerprint_in(school) -> str:
    with use_school(school):
        return kept.fingerprint("<html></html>")


def test_unused_files_are_purged_with_their_file(api, school, chief, klass):
    api(chief).get(url(klass), output="pdf")
    old, recent = documents(school)
    path = old.file.path
    with use_school(school):
        KeptDocument.objects.filter(pk=old.pk).update(
            last_used_at=timezone.now() - kept.UNUSED_AFTER - timedelta(days=1)
        )
    assert kept.purge() == 1
    assert [d.pk for d in documents(school)] == [recent.pk]
    assert not old.file.storage.exists(old.file.name) and path
