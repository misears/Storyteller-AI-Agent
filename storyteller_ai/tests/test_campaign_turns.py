import asyncio

from httpx2 import ASGITransport, AsyncClient

from backend.main import app


def test_campaign_turn_endpoint_persists_gm_response(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    async def request():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            campaign = await client.post("/campaigns/", json={"title": "Turn test"})
            campaign_id = campaign.json()["id"]
            turn = await client.post(f"/campaigns/{campaign_id}/turns", json={"content": "Look around"})
            chat = await client.get(f"/campaigns/{campaign_id}/chat")
            return turn, chat

    turn, chat = asyncio.new_event_loop().run_until_complete(request())

    assert turn.status_code == 200
    assert turn.json()["status"] == "resolved"
    assert len(chat.json()["messages"]) == 2
    assert chat.json()["messages"][-1]["speaker_kind"] == "gm"