import asyncio
from types import SimpleNamespace

from httpx2 import ASGITransport, AsyncClient

from backend.main import app
from backend.services import campaign_turn_service as turn_service_module
from backend.services.llm_client import LLMTimeoutError
from backend.services.session_manager import session_manager
from backend.services.dice_service import dice_service
from backend.engines.gm_loop import GMLoop
from backend.models.tools import ProviderResponse, ToolCall
from backend.persistence.db import create_campaign_engine
from backend.persistence.event_store import EventStore


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


def test_retry_with_same_client_message_id_returns_original_turn(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    async def request_twice():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            campaign = await client.post("/campaigns/", json={"title": "Idempotent turn"})
            campaign_id = campaign.json()["id"]
            body = {"content": "Look around", "client_msg_id": "retry-safe-action"}
            first = await client.post(f"/campaigns/{campaign_id}/turns", json=body)
            retry = await client.post(f"/campaigns/{campaign_id}/turns", json=body)
            conflicting = await client.post(
                f"/campaigns/{campaign_id}/turns",
                json={"content": "Different action", "client_msg_id": body["client_msg_id"]},
            )
            chat = await client.get(f"/campaigns/{campaign_id}/chat")
            return first, retry, conflicting, chat

    first, retry, conflicting, chat = asyncio.run(request_twice())

    assert first.status_code == retry.status_code == 200
    assert retry.json()["turn_id"] == first.json()["turn_id"]
    assert retry.json()["text"] == first.json()["text"]
    assert conflicting.status_code == 409
    assert len(chat.json()["messages"]) == 2


def test_generation_timeout_returns_504_without_persisting_turn(monkeypatch):
    class TimedOutLoop:
        mode = "group"
        orchestrator = SimpleNamespace(state={"scene": {"tension": "medium"}})

        async def step(self, content, **kwargs):
            raise LLMTimeoutError("Ollama generation exceeded the total time limit.")

    monkeypatch.setattr(session_manager, "get_loop", lambda campaign_id: TimedOutLoop())

    async def request_timeout():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            campaign = await client.post("/campaigns/", json={"title": "Timeout test"})
            campaign_id = campaign.json()["id"]
            turn = await client.post(
                f"/campaigns/{campaign_id}/turns",
                json={"content": "Wait", "client_msg_id": "timed-out-action"},
            )
            chat = await client.get(f"/campaigns/{campaign_id}/chat")
            return turn, chat

    turn, chat = asyncio.run(request_timeout())

    assert turn.status_code == 504
    assert "Ollama generation exceeded" in turn.json()["detail"]
    assert chat.json()["messages"] == []


def test_cancel_during_generation_does_not_persist_turn(monkeypatch):
    started = asyncio.Event()
    original_state = {"scene": {"tension": "medium"}}

    class WaitingLoop:
        mode = "group"

        def __init__(self):
            self.orchestrator = SimpleNamespace(state={"scene": {"tension": "medium"}})

        async def step(self, content, **kwargs):
            started.set()
            await asyncio.Event().wait()

    loop = WaitingLoop()
    monkeypatch.setattr(session_manager, "get_loop", lambda campaign_id: loop)
    monkeypatch.setattr(turn_service_module.campaign_turn_service, "_active", {})

    async def cancel_turn():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            campaign = await client.post("/campaigns/", json={"title": "Cancel test"})
            campaign_id = campaign.json()["id"]
            client_msg_id = "cancelled-action"
            task = asyncio.create_task(client.post(
                f"/campaigns/{campaign_id}/turns",
                json={"content": "Wait", "client_msg_id": client_msg_id},
            ))
            await asyncio.wait_for(started.wait(), timeout=1)
            cancelled = await client.post(
                f"/campaigns/{campaign_id}/turns/{client_msg_id}/cancel",
            )
            turn = await asyncio.wait_for(task, timeout=1)
            chat = await client.get(f"/campaigns/{campaign_id}/chat")
            return cancelled, turn, chat

    cancelled, turn, chat = asyncio.run(cancel_turn())

    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled"] is True
    assert turn.status_code == 200
    assert turn.json()["status"] == "cancelled"
    assert chat.json()["messages"] == []
    assert loop.orchestrator.state == original_state


def test_tool_effects_roll_narration_and_state_replay_commit_as_one_turn(monkeypatch):
    class ToolResultLoop:
        mode = "group"

        def __init__(self):
            self.orchestrator = SimpleNamespace(
                state={"scene": {"location": "Elysium", "tension": "medium"}},
                apply_state_update=lambda patch: self.orchestrator.state["scene"].update(patch["scene"]),
            )

        async def step(self, content, campaign, turn_id):
            roll = dice_service.prepare_roll(
                campaign, "1d10", "tool-loop test", turn_id=turn_id,
            )
            return {
                "text": "The die lands and the room falls silent.",
                "mode": self.mode,
                "tool_results": [{
                    "tool_call_id": "roll-1", "name": "roll_dice", "ok": True,
                    "result": roll.model_dump(mode="json"), "error": None,
                }],
                "state_updates": [{"scene": {"tension": "high"}}],
                "dice_rolls": [roll.model_dump(mode="json")],
            }

    loop = ToolResultLoop()
    monkeypatch.setattr(session_manager, "get_loop", lambda campaign_id: loop)

    async def request():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            campaign = await client.post("/campaigns/", json={"title": "Tool effects"})
            campaign_id = campaign.json()["id"]
            turn = await client.post(f"/campaigns/{campaign_id}/turns", json={
                "content": "Make the uncertain action", "client_msg_id": "tool-effects-once",
            })
            chat = await client.get(f"/campaigns/{campaign_id}/chat")
            dice = await client.get(f"/campaigns/{campaign_id}/dice")
            return campaign_id, turn, chat, dice

    campaign_id, turn, chat, dice = asyncio.run(request())

    assert turn.status_code == 200
    assert len(chat.json()["messages"]) == 3
    assert len(dice.json()["rolls"]) == 1
    engine = create_campaign_engine()
    try:
        events = EventStore(engine).read(campaign_id)
    finally:
        engine.dispose()
    relevant = [event for event in events if event.turn_id == turn.json()["turn_id"]]
    assert [event.type for event in relevant] == [
        "message.posted", "turn.started", "dice.rolled", "message.posted",
        "tool.executed", "game_state.updated", "message.posted", "turn.completed",
    ]
    session_manager.sessions.pop(campaign_id, None)
    resumed_loop = session_manager.get_session(campaign_id)["gm_loop"]
    assert resumed_loop.orchestrator.state["scene"]["tension"] == "high"


def test_timeout_after_staged_tool_call_leaves_no_partial_turn(monkeypatch):
    class TimesOutAfterRoll:
        supports_native_tools = True
        calls = 0

        async def generate_with_tools(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return ProviderResponse(tool_calls=[ToolCall(
                    id="staged-roll", name="roll_dice",
                    arguments={"expression": "1d10", "reason": "must not commit"},
                )], finish_reason="tool_calls")
            raise LLMTimeoutError("timed out after staged roll")

    loop = GMLoop(llm_client=TimesOutAfterRoll())
    initial_state = loop.orchestrator.state.copy()
    monkeypatch.setattr(session_manager, "get_loop", lambda campaign_id: loop)

    async def request_timeout_after_tool():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            campaign = await client.post("/campaigns/", json={"title": "Staged timeout"})
            campaign_id = campaign.json()["id"]
            turn = await client.post(
                f"/campaigns/{campaign_id}/turns",
                json={"content": "Roll, then timeout", "client_msg_id": "staged-timeout"},
            )
            chat = await client.get(f"/campaigns/{campaign_id}/chat")
            dice = await client.get(f"/campaigns/{campaign_id}/dice")
            return turn, chat, dice

    turn, chat, dice = asyncio.run(request_timeout_after_tool())

    assert turn.status_code == 504
    assert chat.json()["messages"] == []
    assert dice.json()["rolls"] == []
    assert loop.orchestrator.state == initial_state