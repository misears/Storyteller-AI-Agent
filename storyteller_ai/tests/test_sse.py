import asyncio

from httpx2 import ASGITransport, AsyncClient

from backend.main import app


def test_sse_replays_events_after_last_id():
    async def request():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            campaign = await client.post("/campaigns/", json={"title": "Stream"})
            campaign_id = campaign.json()["id"]
            await client.post(f"/campaigns/{campaign_id}/chat", json={"content": "Hello"})
            stream = await client.get(f"/campaigns/{campaign_id}/stream", params={"last_event_id": 1})
            return stream

    response = asyncio.new_event_loop().run_until_complete(request())

    assert response.status_code == 200
    assert "event: message.posted" in response.text
    assert "event: campaign.created" not in response.text