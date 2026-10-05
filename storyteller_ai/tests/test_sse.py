import asyncio

from starlette.requests import Request

from backend.models.chat import Visibility
from backend.routers.campaigns import stream_campaign_events
from backend.services.campaign_service import campaign_service
from backend.services.chat_service import chat_service


def _request():
    async def receive():
        await asyncio.Event().wait()

    return Request({"type": "http", "headers": [], "query_string": b""}, receive)


def test_sse_replays_events_after_last_id():
    campaign = campaign_service.create("Stream")
    chat_service.post(campaign.id, campaign.active_branch_id, "Hello", "player")
    response = stream_campaign_events(
        _request(), campaign.id, last_event_id=1, viewer="player", player_id=None,
        last_event_header=None,
    )

    body = asyncio.run(response.body_iterator.__anext__())

    assert "event: message.posted" in body
    assert "Hello" in body
    assert "campaign.created" not in body


def test_sse_uses_last_event_id_header_on_reconnect():
    campaign = campaign_service.create("Resume stream")
    first = chat_service.post(campaign.id, campaign.active_branch_id, "Already received", "player")
    chat_service.post(campaign.id, campaign.active_branch_id, "New event", "player")
    response = stream_campaign_events(
        _request(), campaign.id, last_event_id=0, viewer="player", player_id=None,
        last_event_header=str(first.seq),
    )

    body = asyncio.run(response.body_iterator.__anext__())

    assert "New event" in body
    assert "Already received" not in body


def test_sse_redacts_campaign_rng_seed_reference():
    campaign = campaign_service.create("Secret seed")
    response = stream_campaign_events(
        _request(), campaign.id, last_event_id=0, viewer="player", player_id=None,
        last_event_header=None,
    )
    event_data = asyncio.run(response.body_iterator.__anext__())

    assert "rng_seed_ref" not in event_data


def test_sse_delivers_events_committed_after_connection_starts():
    campaign = campaign_service.create("Live stream")
    response = stream_campaign_events(
        _request(), campaign.id, last_event_id=1, viewer="player", player_id=None,
        last_event_header=None,
    )
    iterator = response.body_iterator

    async def receive_new_event():
        pending = asyncio.create_task(iterator.__anext__())
        await asyncio.sleep(0.05)
        chat_service.post(campaign.id, campaign.active_branch_id, "Arrived live", "player")
        return await pending

    body = asyncio.run(receive_new_event())

    assert "Arrived live" in body


def test_player_sse_omits_gm_only_and_untargeted_whispers():
    campaign = campaign_service.create("Private stream")
    chat_service.post(
        campaign.id, campaign.active_branch_id, "GM only", "gm",
        visibility=Visibility(scope="gm_only"),
    )
    chat_service.post(
        campaign.id, campaign.active_branch_id, "Whisper", "gm",
        visibility=Visibility(scope="players", player_ids=["target-player"]),
    )
    chat_service.post(campaign.id, campaign.active_branch_id, "Public", "player")
    response = stream_campaign_events(
        _request(), campaign.id, last_event_id=1, viewer="player", player_id=None,
        last_event_header=None,
    )

    body = asyncio.run(response.body_iterator.__anext__())

    assert "Public" in body
    assert "GM only" not in body
    assert "Whisper" not in body