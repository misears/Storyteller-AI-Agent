import asyncio
import io
import zipfile

from httpx2 import ASGITransport, AsyncClient

import fitz
from backend.main import app
from backend.services.session_manager import session_manager


def _run_async(coroutine):
    return asyncio.new_event_loop().run_until_complete(coroutine)


async def _submit_request(method, path, json=None):
    async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
        if method.lower() == "get":
            return await client.get(path, params=json)

        request = getattr(client, method)
        return await request(path, json=json)


def test_cors_allows_only_configured_origins():
    async def preflight(origin):
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            return await client.options(
                "/health",
                headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
            )

    allowed = _run_async(preflight("http://127.0.0.1:8000"))
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:8000"
    assert allowed.headers["access-control-allow-credentials"] == "true"

    denied = _run_async(preflight("https://untrusted.example"))
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_session_create(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    response = _run_async(_submit_request("post", "/sessions/create", json={"mode": "group"}))

    assert response.status_code == 200
    body = response.json()
    assert "session_id" in body
    assert body["mode"] == "group"


def test_campaign_persists_after_session_cache_reset(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    response = _run_async(_submit_request("post", "/campaigns/", json={"title": "Midnight"}))
    assert response.status_code == 200
    campaign_id = response.json()["id"]

    monkeypatch.setattr(session_manager, "sessions", {})
    campaign = _run_async(_submit_request("get", f"/campaigns/{campaign_id}"))
    session = _run_async(_submit_request("get", f"/sessions/{campaign_id}"))
    assert campaign.status_code == 200
    assert session.status_code == 200
    assert session.json()["state"]["campaign"]["title"] == "Midnight"
    assert session_manager.get_loop(campaign_id) is session_manager.get_session(campaign_id)["gm_loop"]


def test_legacy_character_survives_session_cache_reset(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    campaign_id = _run_async(_submit_request("post", "/sessions/create", json={"mode": "group"})).json()["session_id"]
    added = _run_async(_submit_request("post", f"/sessions/{campaign_id}/characters", json={"name": "Mina"}))
    assert added.status_code == 200

    monkeypatch.setattr(session_manager, "sessions", {})
    status = _run_async(_submit_request("get", f"/sessions/{campaign_id}"))
    assert status.status_code == 200
    assert status.json()["state"]["characters"] == [{"name": "Mina", "clan": None, "notes": None}]


def test_chat_paging_and_client_idempotency():
    created = _run_async(_submit_request("post", "/campaigns/", json={"title": "Chat test"}))
    campaign_id = created.json()["id"]
    first = _run_async(_submit_request("post", f"/campaigns/{campaign_id}/chat", json={
        "content": "First", "client_msg_id": "client-1",
    }))
    duplicate = _run_async(_submit_request("post", f"/campaigns/{campaign_id}/chat", json={
        "content": "First", "client_msg_id": "client-1",
    }))
    second = _run_async(_submit_request("post", f"/campaigns/{campaign_id}/chat", json={
        "content": "Second", "client_msg_id": "client-2", "speaker_kind": "gm",
        "session_id": "session-2", "scene_id": "scene-2",
    }))
    assert first.status_code == duplicate.status_code == second.status_code == 200
    assert first.json()["id"] == duplicate.json()["id"]

    page = _run_async(_submit_request("get", f"/campaigns/{campaign_id}/chat", json={"limit": 1}))
    assert [item["content"] for item in page.json()["messages"]] == ["First"]
    cursor = page.json()["next_after_seq"]
    later = _run_async(_submit_request("get", f"/campaigns/{campaign_id}/chat", json={
        "after_seq": cursor, "limit": 1,
    }))
    assert [item["content"] for item in later.json()["messages"]] == ["Second"]
    assert later.json()["next_after_seq"] is None
    filtered = _run_async(_submit_request("get", f"/campaigns/{campaign_id}/chat", json={
        "speaker_kind": "gm", "session_id": "session-2", "scene_id": "scene-2",
    }))
    assert [item["id"] for item in filtered.json()["messages"]] == [second.json()["id"]]


def test_gm_step_with_mock_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    create_response = _run_async(_submit_request("post", "/sessions/create", json={"mode": "group"}))
    assert create_response.status_code == 200

    session_id = create_response.json()["session_id"]
    gm_response = _run_async(
        _submit_request(
            "post",
            "/gm/step",
            json={"session_id": session_id, "message": "Try to update state_update"},
        )
    )

    assert gm_response.status_code == 200
    body = gm_response.json()
    assert body["mode"] == "group"
    assert "Mock LLM" in body["text"] or "storyteller" in body["text"]


def test_session_status_endpoint(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    create_response = _run_async(_submit_request("post", "/sessions/create", json={"mode": "group"}))
    assert create_response.status_code == 200

    session_id = create_response.json()["session_id"]
    status_response = _run_async(_submit_request("get", f"/sessions/{session_id}"))

    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["session_id"] == session_id
    assert status_body["mode"] == "group"
    assert "state" in status_body


def test_upload_document():
    buf = io.BytesIO()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test PDF upload content.")
    doc.save(buf)
    doc.close()
    buf.seek(0)

    async def request_upload():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            files = {"files": ("test_upload.pdf", buf.read(), "application/pdf")}
            return await client.post("/documents/upload", files=files)

    response = _run_async(request_upload())
    assert response.status_code == 200
    body = response.json()
    assert "documents" in body
    assert body["documents"][0]["title"] == "test_upload.pdf"


def test_delete_document():
    buf = io.BytesIO()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test PDF delete content.")
    doc.save(buf)
    doc.close()
    buf.seek(0)

    async def request_upload_then_delete():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            files = {"files": ("test_delete.pdf", buf.read(), "application/pdf")}
            upload_response = await client.post("/documents/upload", files=files)
            uploaded_id = upload_response.json()["documents"][0]["document_id"]

            delete_response = await client.delete(f"/documents/{uploaded_id}")
            list_response = await client.get("/documents/list")
            return upload_response, delete_response, list_response, uploaded_id

    upload_response, delete_response, list_response, uploaded_id = _run_async(request_upload_then_delete())
    assert upload_response.status_code == 200
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True
    remaining_ids = [doc["document_id"] for doc in list_response.json()["documents"]]
    assert uploaded_id not in remaining_ids


def test_health_endpoint():
    response = _run_async(_submit_request("get", "/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_character_sheet_create_and_export_pdf():
    templates_response = _run_async(
        _submit_request("get", "/character-sheets/templates", json={"genre": "fantasy", "audience": "player"})
    )
    assert templates_response.status_code == 200
    templates = templates_response.json()["templates"]
    assert templates

    template_key = templates[0]["key"]
    create_response = _run_async(
        _submit_request(
            "post",
            "/character-sheets/",
            json={
                "template_key": template_key,
                "name": "Sir Rowan",
                "fields": {"archetype": "Knight"},
            },
        )
    )
    assert create_response.status_code == 200
    sheet = create_response.json()["sheet"]
    assert sheet["name"] == "Sir Rowan"

    export_response = _run_async(
        _submit_request("get", f"/character-sheets/{sheet['sheet_id']}/export", json={"format": "pdf"})
    )
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "application/pdf"
    assert export_response.content.startswith(b"%PDF")


def test_character_sheet_export_docx():
    create_response = _run_async(
        _submit_request(
            "post",
            "/character-sheets/",
            json={
                "template_key": "horror-investigator-player",
                "name": "Mina Hale",
                "fields": {"occupation": "Archivist"},
            },
        )
    )
    assert create_response.status_code == 200
    sheet_id = create_response.json()["sheet"]["sheet_id"]

    export_response = _run_async(
        _submit_request("get", f"/character-sheets/{sheet_id}/export", json={"format": "docx"})
    )
    assert export_response.status_code == 200
    assert (
        export_response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    archive = zipfile.ZipFile(io.BytesIO(export_response.content))
    names = set(archive.namelist())
    assert "word/document.xml" in names


def test_ocr_status_endpoint():
    response = _run_async(_submit_request("get", "/settings/ocr"))

    assert response.status_code == 200
    body = response.json()
    assert "active" in body
    assert "detail" in body
    assert isinstance(body["active"], bool)
    assert isinstance(body["detail"], str)


def test_update_document_genres():
    buf = io.BytesIO()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test PDF genre tagging.")
    doc.save(buf)
    doc.close()
    buf.seek(0)

    async def request_upload_then_tag_then_list():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            files = {"files": ("test_genre.pdf", buf.read(), "application/pdf")}
            upload_response = await client.post("/documents/upload", files=files)
            uploaded_id = upload_response.json()["documents"][0]["document_id"]

            tag_response = await client.put(
                f"/documents/{uploaded_id}/genres",
                json={"genres": ["vampire", "werewolf"]},
            )
            list_response = await client.get("/documents/list")
            return upload_response, tag_response, list_response, uploaded_id

    upload_response, tag_response, list_response, uploaded_id = _run_async(request_upload_then_tag_then_list())
    assert upload_response.status_code == 200
    assert tag_response.status_code == 200
    tagged_doc = next(doc for doc in list_response.json()["documents"] if doc["document_id"] == uploaded_id)
    assert tagged_doc["genres"] == ["vampire", "werewolf"]


def test_session_create_with_campaign_genres(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    response = _run_async(
        _submit_request(
            "post",
            "/sessions/create",
            json={
                "mode": "group",
                "setting": "Old World of Darkness",
                "campaign_genres": ["vampire", "mage"],
                "document_ids": ["book-one", "book-two"],
            },
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["campaign_genres"] == ["vampire", "mage"]
    assert body["document_ids"] == ["book-one", "book-two"]
