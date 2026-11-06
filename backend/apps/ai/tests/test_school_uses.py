"""IA dans l'école (IA.3, IA.4, IA.5) : chaque usage repasse les verrous, ne lit que l'école
courante, n'écrit rien seul. L'API de l'IA est simulée ; la tâche de fond tourne tout de suite."""

import json

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.academics.tests.test_courses import classes
from apps.accounts.models import Role
from apps.ai import client, services
from apps.ai.models import AiCall
from apps.core.ids import uuid7
from apps.core.tenancy import use_school
from apps.students.tests.conftest import enrolled
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

sent: list = []  # les messages reçus par l'IA


@pytest.fixture
def reply(monkeypatch):
    """L'API simulée rend `answer["json"]` ; le comptage des jetons rend `answer["tokens"]`."""
    answer: dict = {"json": {}, "tokens": 5_000}
    sent.clear()

    def fake(**kwargs):
        sent.append(kwargs["messages"])
        return client.Reply(
            text=json.dumps(answer["json"]),
            stop_reason="end_turn",
            model=kwargs["model"],
            input_tokens=800,
            output_tokens=60,
        )

    monkeypatch.setattr(client, "complete", fake)
    monkeypatch.setattr(client, "count_tokens", lambda **kwargs: answer["tokens"])
    monkeypatch.setattr(
        services,
        "_enqueue",
        lambda call, payload: services.execute(str(call.pk), str(call.school_id), payload),
    )
    return answer


def person(school, *permissions):
    with use_school(school):
        role = Role.objects.create(name=f"IA {uuid7()}", permissions=list(permissions))
    return MembershipFactory(school=school, roles=[role]).user


def allow(school, platform_admin, *uses_):
    services.set_allowance(
        school, actor=platform_admin, uses_=list(uses_), monthly_credits=100, paused=False
    )


def test_questions_are_answered_by_the_code_with_the_persons_rights(
    api, school, head, other_school, platform_admin, reply
):
    allow(school, platform_admin, "assistant")
    data = classes(school, head)
    enrolled(school, head, data["a"], first_name="Zawadi")
    clerk = api(person(school, "ai.use", "students.view"))
    url = "/api/ai/questions/"

    def ask(question, intent, class_ref="", history=()):
        reply["json"] = {"intent": intent, "class_ref": class_ref, "teacher_ref": "", "period": ""}
        asked = clerk.post(
            url,
            {"request_id": str(uuid7()), "question": question, "history": list(history)},
        )
        assert asked.status_code == 202, asked.json()
        return clerk.get(f"{url}{asked.json()['id']}/").json()

    # Effectif d'une classe : calculé par l'application, avec le lien vers l'écran.
    done = ask("Combien d'élèves en 1re A ?", "headcount", "K1")
    assert done["answer"]["status"] == "answered" and done["state"] == "kept"
    figures = done["answer"]["figures"]
    assert (figures["class_group"], figures["count"]) == (data["a"].name, 1)
    assert figures["link"] == f"/students?class={data['a'].pk}"
    # L'IA n'a reçu que la question et les noms des classes : jamais un nom d'élève.
    text = sent[-1][0]["content"]
    assert data["a"].name in text and "Zawadi" not in text
    # Une question d'un écran interdit (impayés sans `finance.view_reports`) : aucun chiffre.
    refused = ask("Et les impayés ?", "unpaid", history=["Combien d'élèves en 1re A ?"])
    assert refused["answer"] == {"intent": "unpaid", "status": "forbidden"}
    assert "Combien d'élèves en 1re A ?" in sent[-1][0]["content"]  # la question d'avant
    unknown = ask("Quel temps fera-t-il ?", "unknown")
    assert (unknown["answer"]["status"], unknown["state"]) == ("not_understood", "abandoned")
    # La réponse ne se calcule qu'une fois.
    assert clerk.get(f"{url}{unknown['id']}/").json()["answer"] is None

    # Limite par personne et par jour, réglée dans la console : refus sans appel à l'API.
    services.update_settings(
        actor=platform_admin,
        use_overrides={"assistant": {"daily_limit": 3}},
    )
    calls = len(sent)
    over = clerk.post(url, {"request_id": str(uuid7()), "question": "Encore ?"})
    assert (over.status_code, over.json()["code"]) == (429, "ai_daily_limit") and len(sent) == calls

    # Une autre école ne lit pas l'appel ; sans `ai.use` : 403.
    beta_user = person(other_school, "ai.use", "students.view")
    beta = api(beta_user, host="beta.localhost")
    assert beta.get(f"{url}{done['id']}/").status_code == 404
    assert api(person(school, "students.view")).post(url, {}).status_code == 403


def test_a_draft_is_only_a_draft(api, school, platform_admin, reply):
    allow(school, platform_admin, "drafting")
    writer = api(person(school, "ai.use", "announcements.publish"))
    url = "/api/ai/drafts/"
    body = {"request_id": str(uuid7()), "kind": "summons", "brief": "Réunion samedi 9 h"}
    assert api(person(school, "ai.use")).post(url, body).status_code == 403
    reply["json"] = {"title": "T" * 300, "body": "Chers parents…"}
    asked = writer.post(url, body)
    assert asked.status_code == 202, asked.json()
    done = writer.get(f"{url}{asked.json()['id']}/").json()
    assert done["draft"] == {"title": "T" * 120, "body": "Chers parents…"}
    # Rien n'est publié : la personne garde le brouillon dans son texte, une fois.
    assert writer.post(f"{url}{done['id']}/", {"kept": True}).status_code == 204
    assert writer.post(f"{url}{done['id']}/", {"kept": True}).json()["code"] == "ai_not_ready"
    with use_school(school):
        assert AiCall.objects.get(pk=done["id"]).state == AiCall.State.KEPT


def test_course_grid_from_a_report_card(api, school, other_school, platform_admin, reply):
    allow(school, platform_admin, "course_grid_from_pdf")
    reader = api(person(school, "ai.use", "courses.configure"))
    url = "/api/ai/course-grid/"
    pdf = b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Pages /Count 1 >>"

    def send(content, name="bulletin.pdf"):
        upload = SimpleUploadedFile(name, content)
        body = {"request_id": str(uuid7()), "file": upload}
        return reader.client.post(url, body, HTTP_HOST=reader.host)

    # Refus avant tout appel : pas un PDF ni une photo, plus de 3 pages.
    assert send(b"MZ\x90\x00 pas un bulletin").json()["code"] == "bad_file"
    assert send(pdf + b" /Type /Page" * 3).json()["code"] == "too_many_pages"
    assert not sent

    reply["json"] = {
        "courses": [
            {
                "name": "Mathématiques",
                "domain": "Formation scientifique",
                "period_max": 60,
                "has_exam": True,
                "category": "main",
                "doubtful": False,
            },
            {
                "name": "Dessin",
                "domain": "",
                "period_max": 0,
                "has_exam": False,
                "category": "general",
                "doubtful": True,
            },
        ],
        "skipped": [{"name": "Conduite", "reason": "Cote, pas un cours."}],
    }
    asked = send(pdf)
    assert asked.status_code == 202, asked.json()
    # Le PDF est parti en document, avant la consigne ; puis effacé de nos fichiers.
    assert sent[-1][0]["content"][0]["type"] == "document"
    assert default_storage.listdir(f"{services.UPLOADS}/{school.pk}")[1] == []
    done = reader.get(f"{url}{asked.json()['id']}/").json()
    assert [row["name"] for row in done["proposal"]["courses"]] == ["Mathématiques"]
    assert {row["name"] for row in done["proposal"]["skipped"]} == {"Conduite", "Dessin"}
    # Une autre école ne lit pas la grille lue.
    beta = api(person(other_school, "ai.use", "courses.configure"), host="beta.localhost")
    assert beta.get(f"{url}{done['id']}/").status_code == 404

    # Un PDF dont le vrai poids dépasse l'usage : refusé avant l'appel, rien facturé.
    reply["tokens"] = 90_000
    calls = len(sent)
    heavy = reader.get(f"{url}{send(pdf).json()['id']}/").json()
    assert (heavy["state"], heavy["refusal"]) == ("error", "ai_too_large") and len(sent) == calls
    with use_school(school):
        assert AiCall.objects.get(pk=heavy["id"]).cost_micro == 0
