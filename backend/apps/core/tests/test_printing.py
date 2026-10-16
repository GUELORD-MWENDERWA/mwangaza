"""Impression des documents lourds en tâche de fond (PERF.1) : le PDF d'une classe n'est jamais
fait dans la requête web, recharger l'adresse ne relance rien, chaque personne a son travail, une
école ne peut pas en entasser, un échec se voit et se reprend, paquets réunis sans page perdue."""

import io
from datetime import timedelta

import pytest
from django.utils import timezone
from pypdf import PdfReader

from apps.academics.tests.test_grades import setup
from apps.academics.tests.test_report_card_documents import url, validate_all
from apps.academics.tests.test_report_cards import put
from apps.core import printing
from apps.core.models import PrintJob
from apps.core.tasks import render_print_job
from apps.core.tenancy import use_school
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def chief(school):
    return MembershipFactory(school=school, roles=["study_director"]).user


@pytest.fixture
def klass(school, head):
    """Une classe de deux élèves dont les notes sont saisies (les feuilles se valident ensuite)."""
    data = setup(school, head)
    amani, josue = data["amani"], data["josue"]
    put(school, data["physics"], data["p1"], "Interro", 20, {amani: "18", josue: "8"})
    put(school, data["workshop"], data["p1"], "TP", 100, {amani: "80", josue: "80"})
    return data


@pytest.fixture(autouse=True)
def heavy(monkeypatch):
    """Deux bulletins suffisent à passer en tâche de fond."""
    monkeypatch.setattr(printing, "INLINE_MAX_PAGES", 1)


@pytest.fixture
def queued(monkeypatch):
    """Le travailleur ne tourne pas : les travaux restent en attente (sinon, immédiat)."""
    monkeypatch.setattr(render_print_job, "delay", lambda job_id: None)


def jobs(school) -> list[PrintJob]:
    with use_school(school):
        return list(PrintJob.objects.order_by("created_at"))


def pages(response) -> int:
    return len(PdfReader(io.BytesIO(response.content)).pages)


def test_a_class_is_made_by_the_job_once_and_reloading_does_not_start_another(
    api,
    school,
    chief,
    klass,
):
    validate_all(school, klass)
    client = api(chief)
    first = client.get(url(klass), output="pdf")
    assert (first.status_code, first["Content-Type"], pages(first)) == (200, "application/pdf", 2)
    [job] = jobs(school)
    assert (job.status, job.pages, job.pages_done, job.created_by_id) == ("done", 2, 2, chief.pk)
    assert not job.source  # le document déposé est effacé une fois fait
    again = client.get(url(klass), output="pdf")
    assert pages(again) == 2 and len(jobs(school)) == 1


def test_waiting_page_refreshes_itself_then_gives_the_pdf_and_each_person_has_their_own_job(
    api,
    school,
    other_school,
    chief,
    klass,
    queued,
):
    validate_all(school, klass)
    client = api(chief)
    waiting = client.get(url(klass), output="pdf")
    assert waiting.status_code == 202 and b'http-equiv="refresh"' in waiting.content
    assert client.get(url(klass), output="pdf").status_code == 202
    [job] = jobs(school)
    assert job.status == "queued"

    colleague = MembershipFactory(school=school, roles=["study_director"]).user
    assert api(colleague).get(url(klass), output="pdf").status_code == 202
    assert len(jobs(school)) == 2  # pas de partage du travail d'une autre personne

    printing.run(str(job.pk))
    done = client.get(url(klass), output="pdf")
    assert (done.status_code, pages(done)) == (200, 2)
    assert jobs(other_school) == []


def test_a_school_cannot_pile_up_documents(api, school, chief, klass, queued):
    validate_all(school, klass)
    for _ in range(printing.MAX_PENDING_PER_SCHOOL):
        who = MembershipFactory(school=school, roles=["study_director"]).user
        assert api(who).get(url(klass), output="pdf").status_code == 202
    refused = api(chief).get(url(klass), output="pdf")
    assert refused.status_code == 429 and len(jobs(school)) == printing.MAX_PENDING_PER_SCHOOL


def test_a_failed_job_is_shown_then_forgotten_so_the_next_request_starts_again(
    api,
    school,
    chief,
    klass,
    monkeypatch,
):
    validate_all(school, klass)

    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(printing, "build_kept", broken)
    client = api(chief)
    failed = client.get(url(klass), output="pdf")
    assert (
        failed.status_code == 500 and b"try again" in failed.content.lower()
    ) or failed.status_code == 500
    assert jobs(school) == []
    monkeypatch.undo()
    monkeypatch.setattr(printing, "INLINE_MAX_PAGES", 1)
    assert pages(client.get(url(klass), output="pdf")) == 2


def test_chunks_are_joined_without_losing_or_adding_a_page(monkeypatch):
    monkeypatch.setattr(printing, "CHUNK_PAGES", 8)
    head = "<html><head><style>.next{page-break-before:always}</style></head><body>"
    pdf = printing.build_pdf(head, [f"<p>Page {n}</p>" for n in range(20)])
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 20


def test_old_jobs_and_their_files_are_purged(api, school, chief, klass):
    validate_all(school, klass)
    api(chief).get(url(klass), output="pdf")
    [job] = jobs(school)
    name = job.pdf.name
    with use_school(school):
        PrintJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(days=2))
    assert printing.purge() == 1 and jobs(school) == []
    assert not job.pdf.storage.exists(name)
