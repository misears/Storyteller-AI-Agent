import asyncio

from httpx2 import ASGITransport, AsyncClient

from backend.main import app


def _run_async(coroutine):
    return asyncio.new_event_loop().run_until_complete(coroutine)


async def _submit_request(method, path, json=None):
    async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
        if method.lower() == "get":
            return await client.get(path, params=json)

        request = getattr(client, method)
        return await request(path, json=json)


def test_session_create(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    response = _run_async(_submit_request("post", "/sessions/create", json={"mode": "group"}))

    assert response.status_code == 200
    body = response.json()
    assert "session_id" in body
    assert body["mode"] == "group"


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


def test_health_endpoint():
    response = _run_async(_submit_request("get", "/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
