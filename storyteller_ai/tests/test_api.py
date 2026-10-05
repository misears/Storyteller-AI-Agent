import asyncio
import io
import zipfile

from httpx2 import ASGITransport, AsyncClient
import pytest

import fitz
from backend.main import app
from backend.services.session_manager import session_manager
from backend.services import pdf_ingest
from backend.services.ai_setup import AIConfigStore, WindowsCredentialStore, ai_setup_service
from backend.services.runtime_settings import runtime_settings


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


def test_ollama_timeout_settings_api_validates_and_returns_values(monkeypatch):
    monkeypatch.setattr(runtime_settings, "_overrides", {})

    async def update_settings():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            current = await client.get("/settings/llm")
            updated = await client.put("/settings/llm", json={
                "ollama_connect_timeout": 15,
                "ollama_read_timeout": 420,
                "ollama_total_timeout": 720,
                "ollama_connect_retries": 2,
                "ollama_context_window": 4096,
                "ollama_max_output_tokens": 1200,
                "ollama_think": "false",
            })
            invalid_timeout = await client.put("/settings/llm", json={"ollama_total_timeout": 0})
            invalid_context = await client.put("/settings/llm", json={"ollama_context_window": 128})
            invalid_think = await client.put("/settings/llm", json={"ollama_think": "unbounded"})
            return current, updated, invalid_timeout, invalid_context, invalid_think

    current, updated, invalid_timeout, invalid_context, invalid_think = _run_async(update_settings())

    assert current.status_code == 200
    assert current.json()["ollama_total_timeout"] == 900
    assert updated.status_code == 200
    assert updated.json()["ollama_connect_timeout"] == 15
    assert updated.json()["ollama_read_timeout"] == 420
    assert updated.json()["ollama_total_timeout"] == 720
    assert updated.json()["ollama_connect_retries"] == 2
    assert updated.json()["ollama_context_window"] == 4096
    assert updated.json()["ollama_max_output_tokens"] == 1200
    assert updated.json()["ollama_think"] == "false"
    assert invalid_timeout.status_code == 422
    assert invalid_context.status_code == 422
    assert invalid_think.status_code == 422


def test_ai_setup_api_never_returns_saved_cloud_key(tmp_path, monkeypatch):
    secret = "sk-test-secret-that-must-not-return"
    credentials = WindowsCredentialStore(tmp_path / "credentials")
    monkeypatch.setattr(WindowsCredentialStore, "_protect", staticmethod(lambda value: b"cipher:" + value[::-1]))
    monkeypatch.setattr(WindowsCredentialStore, "_unprotect", staticmethod(lambda value: value.removeprefix(b"cipher:")[::-1]))
    monkeypatch.setattr(ai_setup_service, "config", AIConfigStore(tmp_path / "ai-settings.json"))
    monkeypatch.setattr(ai_setup_service, "credentials", credentials)

    async def runtime_status(mode):
        return {"running": False, "url": None, "managed": False, "mode": mode, "models": []}

    monkeypatch.setattr(ai_setup_service.ollama, "status", runtime_status)
    saved = _run_async(_submit_request("put", "/settings/ai/credentials/openai", json={"api_key": secret}))
    status = _run_async(_submit_request("get", "/settings/ai"))

    assert saved.status_code == 200
    assert saved.json() == {"provider": "openai", "configured": True}
    assert secret not in saved.text
    assert status.status_code == 200
    assert status.json()["credentials"] == {"openai": True, "anthropic": False}
    assert secret not in status.text
    assert secret.encode() not in (tmp_path / "credentials" / "openai.dpapi").read_bytes()
    assert not (tmp_path / "ai-settings.json").exists()


def test_request_size_limit_rejects_chunked_body_without_content_length(monkeypatch):
    monkeypatch.setenv("STORYTELLER_MAX_REQUEST_BYTES", "16")

    async def request():
        class BodyChunks:
            def __init__(self):
                self.chunks = [b'{"title":"too ', b'large for limit"}']

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.chunks:
                    raise StopAsyncIteration
                return self.chunks.pop(0)

        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            return await client.post(
                "/campaigns/", content=BodyChunks(),
                headers={"Content-Type": "application/json"},
            )

    response = _run_async(request())

    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}


def test_ai_provider_test_redacts_provider_exception(tmp_path, monkeypatch):
    secret = "sk-test-secret-that-must-not-return"
    credentials = WindowsCredentialStore(tmp_path / "credentials")
    monkeypatch.setattr(WindowsCredentialStore, "_protect", staticmethod(lambda value: b"cipher:" + value[::-1]))
    monkeypatch.setattr(WindowsCredentialStore, "_unprotect", staticmethod(lambda value: value.removeprefix(b"cipher:")[::-1]))
    credentials.set("openai", secret)
    config = AIConfigStore(tmp_path / "ai-settings.json")
    config.save({"provider": "openai", "model": "gpt-test", "ollama_mode": "auto"})
    monkeypatch.setattr(ai_setup_service, "config", config)
    monkeypatch.setattr(ai_setup_service, "credentials", credentials)

    class FailingProvider:
        async def generate(self, *_args, **_kwargs):
            raise RuntimeError(f"provider rejected key {secret}")

    monkeypatch.setattr("backend.routers.settings.LLMClient", FailingProvider)
    response = _run_async(_submit_request("post", "/settings/ai/test"))

    assert response.status_code == 502
    assert "RuntimeError" in response.text
    assert secret not in response.text


def test_ai_provider_test_succeeds_with_configured_cloud_provider(tmp_path, monkeypatch):
    credentials = WindowsCredentialStore(tmp_path / "credentials")
    monkeypatch.setattr(WindowsCredentialStore, "_protect", staticmethod(lambda value: b"cipher:" + value[::-1]))
    monkeypatch.setattr(WindowsCredentialStore, "_unprotect", staticmethod(lambda value: value.removeprefix(b"cipher:")[::-1]))
    credentials.set("anthropic", "test-only-cloud-key")
    config = AIConfigStore(tmp_path / "ai-settings.json")
    config.save({"provider": "anthropic", "model": "claude-test", "ollama_mode": "auto"})
    monkeypatch.setattr(ai_setup_service, "config", config)
    monkeypatch.setattr(ai_setup_service, "credentials", credentials)

    class ReadyProvider:
        async def generate(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr("backend.routers.settings.LLMClient", ReadyProvider)
    response = _run_async(_submit_request("post", "/settings/ai/test"))

    assert response.status_code == 200
    assert response.json() == {"ok": True, "provider": "anthropic", "model": "claude-test"}


def test_player_chat_dice_and_stream_filter_private_visibility(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path / "data"))
    campaign = _run_async(_submit_request("post", "/campaigns/", json={"title": "Visibility"})).json()
    campaign_id = campaign["id"]
    for content, visibility in [
        ("Public scene", {"scope": "public", "player_ids": []}),
        ("GM secret", {"scope": "gm_only", "player_ids": []}),
        ("Private whisper", {"scope": "players", "player_ids": ["player-a"]}),
    ]:
        response = _run_async(_submit_request("post", f"/campaigns/{campaign_id}/chat", json={
            "content": content, "visibility": visibility,
        }))
        assert response.status_code == 200
    roll_ids = []
    for visibility in [
        {"scope": "public", "player_ids": []},
        {"scope": "gm_only", "player_ids": []},
        {"scope": "players", "player_ids": ["player-a"]},
    ]:
        response = _run_async(_submit_request("post", f"/campaigns/{campaign_id}/dice", json={
            "expression": "1d20", "reason": "visibility test", "visibility": visibility,
        }))
        assert response.status_code == 200
        roll_ids.append(response.json()["id"])

    player_chat = _run_async(_submit_request("get", f"/campaigns/{campaign_id}/chat", json={"speaker_kind": "player"}))
    targeted_chat = _run_async(_submit_request("get", f"/campaigns/{campaign_id}/chat", json={
        "viewer": "player", "player_id": "player-a", "speaker_kind": "player",
    }))
    gm_chat = _run_async(_submit_request("get", f"/campaigns/{campaign_id}/chat", json={
        "viewer": "gm", "speaker_kind": "player",
    }))
    player_dice = _run_async(_submit_request("get", f"/campaigns/{campaign_id}/dice"))
    targeted_dice = _run_async(_submit_request("get", f"/campaigns/{campaign_id}/dice", json={
        "viewer": "player", "player_id": "player-a",
    }))
    gm_dice = _run_async(_submit_request("get", f"/campaigns/{campaign_id}/dice", json={"viewer": "gm"}))
    hidden_roll_verify = _run_async(_submit_request(
        "get", f"/campaigns/{campaign_id}/dice/{roll_ids[1]}/verify",
    ))
    gm_roll_verify = _run_async(_submit_request(
        "get", f"/campaigns/{campaign_id}/dice/{roll_ids[1]}/verify", json={"viewer": "gm"},
    ))
    assert [message["content"] for message in player_chat.json()["messages"]] == ["Public scene"]
    assert [message["content"] for message in targeted_chat.json()["messages"]] == ["Public scene", "Private whisper"]
    assert [message["content"] for message in gm_chat.json()["messages"]] == ["Public scene", "GM secret", "Private whisper"]
    assert len(player_dice.json()["rolls"]) == 1
    assert len(targeted_dice.json()["rolls"]) == 2
    assert len(gm_dice.json()["rolls"]) == 3
    assert hidden_roll_verify.status_code == 404
    assert gm_roll_verify.status_code == 200


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


def test_scanned_pdf_upload_reports_missing_ocr(monkeypatch):
    monkeypatch.setattr(
        pdf_ingest,
        "get_ocr_runtime_status",
        lambda: (
            False,
            "Install Tesseract OCR with English language data. "
            "Text-based PDFs can still be imported.",
        ),
    )
    pdf = fitz.open()
    page = pdf.new_page()
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10))
    page.insert_image(page.rect, pixmap=pixmap)
    contents = pdf.tobytes()
    pdf.close()

    async def upload():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            return await client.post(
                "/documents/upload",
                files={"files": ("scanned.pdf", contents, "application/pdf")},
            )

    response = _run_async(upload())

    assert response.status_code == 422
    assert "Page 1 appears to be scanned" in response.json()["detail"]
    assert "Text-based PDFs can still be imported" in response.json()["detail"]


def test_scanned_pdf_upload_and_retrieval_preserve_page_citation():
    active, detail = pdf_ingest.get_ocr_runtime_status()
    if not active:
        pytest.skip(detail)

    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1600, 300), "white")
    ImageDraw.Draw(image).text(
        (40, 80),
        "MERCURY ARCHIVE CITATION",
        fill="black",
        font=ImageFont.load_default(size=100),
    )
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")

    pdf = fitz.open()
    first_page = pdf.new_page(width=800, height=150)
    first_page.insert_text((40, 80), "First page has ordinary embedded text.")
    scanned_page = pdf.new_page(width=800, height=150)
    scanned_page.insert_image(scanned_page.rect, stream=image_bytes.getvalue())
    pdf_bytes = pdf.tobytes()
    pdf.close()

    async def upload_and_retrieve():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            upload = await client.post(
                "/documents/upload",
                files={"files": ("scanned-citation.pdf", pdf_bytes, "application/pdf")},
            )
            if upload.status_code != 200:
                return upload, None
            document_id = upload.json()["documents"][0]["document_id"]
            retrieve = await client.post(
                "/documents/retrieve-scoped",
                    params={"query": "MERCURY ARCHIVE CITATION"},
                    json=[document_id],
            )
            return upload, retrieve

    upload_response, retrieve_response = _run_async(upload_and_retrieve())

    assert upload_response.status_code == 200, upload_response.text
    assert retrieve_response is not None
    assert retrieve_response.status_code == 200, retrieve_response.text
    result = retrieve_response.json()["results"][0]
    assert result["page"] == 2
    assert "MERCURY ARCHIVE CITATION" in result["snippet"].upper()


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
