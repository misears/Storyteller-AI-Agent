import asyncio
import pytest
from sqlalchemy import select
from sqlalchemy.exc import StatementError

from backend.domain.reducers import replay
from backend.models.campaign import Actor
from backend.persistence.db import create_campaign_engine, upgrade_database
from backend.persistence.event_store import EventStore
from backend.persistence.projectors import rebuild_projections
from backend.persistence.tables import branches, campaigns, chat_messages, memberships, play_sessions, players, scenes, turns
from backend.services.turn_service import TurnService


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYTELLER_DATA_DIR", str(tmp_path))
    upgrade_database()
    engine = create_campaign_engine()
    with engine.begin() as connection:
        connection.execute(campaigns.insert().values(
            id="campaign-1", data={}, status="active", active_branch_id="branch-1",
        ))
        connection.execute(branches.insert().values(
            id="branch-1", campaign_id="campaign-1", label="main",
        ))
    yield EventStore(engine)
    engine.dispose()


def test_intake_and_dice_survive_failed_resolution(store):
    actor = Actor(kind="player", id="player-1")
    with store.transaction("campaign-1", "branch-1") as writer:
        writer.append("message.posted", {"id": "message-1", "speaker_kind": "player", "content": "Attack"}, actor, "turn-1")
        writer.append("turn.started", {"id": "turn-1"}, actor, "turn-1")

    with store.transaction("campaign-1", "branch-1") as writer:
        writer.append("dice.rolled", {"total": 17}, Actor(kind="system"), "turn-1")

    with pytest.raises(StatementError):
        with store.transaction("campaign-1", "branch-1") as writer:
            writer.append("scene.started", {"scene": {"id": "scene-1", "title": "Alley"}}, Actor(kind="system"), "turn-1")
            writer.append("turn.completed", {"bad": object()}, Actor(kind="system"), "turn-1")

    assert [(event.seq, event.type) for event in store.read("campaign-1")] == [
        (1, "message.posted"), (2, "turn.started"), (3, "dice.rolled"),
    ]
    with store.engine.connect() as connection:
        assert connection.scalar(select(turns.c.status)) == "in_progress"
        assert connection.scalar(select(scenes.c.id)) is None


def test_rebuild_matches_live_projections(store):
    actor = Actor(kind="system")
    with store.transaction("campaign-1", "branch-1") as writer:
        writer.append("scene.started", {"scene": {"id": "scene-1", "title": "Alley"}}, actor)
        writer.append("message.posted", {
            "id": "message-1", "speaker_kind": "gm", "content": "The rain falls.",
        }, actor)

    with store.engine.connect() as connection:
        live_scene = connection.execute(select(scenes.c.data)).scalar_one()
        live_message = connection.execute(select(chat_messages.c.data)).scalar_one()
    history = store.read("campaign-1")
    state = replay("campaign-1", "branch-1", history)
    assert state.scene.title == "Alley"
    assert state.head_seq == 2

    with store.engine.begin() as connection:
        rebuild_projections(connection, "campaign-1", history)
    with store.engine.connect() as connection:
        assert connection.execute(select(scenes.c.data)).scalar_one() == live_scene
        assert connection.execute(select(chat_messages.c.data)).scalar_one() == live_message


def test_turn_service_rolls_back_interrupted_resolution_atomically(store):
    service = TurnService(store)

    def crash_resolution(writer, turn_id):
        writer.append("scene.started", {"scene": {"id": "scene-2", "title": "Bridge"}}, Actor(kind="system"), turn_id)
        raise RuntimeError("resolution interrupted")

    with pytest.raises(RuntimeError, match="resolution interrupted"):
        asyncio.run(service.run(
            "campaign-1", "branch-1", Actor(kind="player", id="player-1"),
            "Cross the bridge", [], crash_resolution,
        ))

    history = store.read("campaign-1")
    assert history == []
    assert service.recover_incomplete("campaign-1", "branch-1") == []
    with store.engine.connect() as connection:
        assert connection.scalar(select(turns.c.status)) is None
        assert connection.scalar(select(scenes.c.id)) is None


def test_lifecycle_projections_rebuild_from_events(store):
    actor = Actor(kind="system")
    with store.transaction("campaign-1", "branch-1") as writer:
        writer.append("player.joined", {
            "player": {"id": "player-1", "display_name": "Mina"},
            "membership": {"player_id": "player-1", "campaign_id": "campaign-1", "status": "active"},
        }, actor)
        writer.append("session.started", {"id": "session-1"}, actor)
        writer.append("scene.started", {"scene": {"id": "scene-1", "title": "Bridge"}}, actor)
        writer.append("message.posted", {
            "id": "message-1", "speaker_kind": "player", "content": "secret",
        }, actor)
        writer.append("player.left", {"player_id": "player-1"}, actor)
        writer.append("session.ended", {"id": "session-1", "recap": "Rain."}, actor)
        writer.append("scene.ended", {"id": "scene-1"}, actor)
        writer.append("message.redacted", {"id": "message-1"}, actor)

    with store.engine.connect() as connection:
        live = tuple(connection.scalar(select(table.c.data)) for table in (
            players, memberships, play_sessions, scenes, chat_messages,
        ))
    assert live[1]["status"] == "left"
    assert live[4]["content"] == "[redacted]"
    assert replay("campaign-1", "branch-1", store.read("campaign-1")).scene is None

    with store.engine.begin() as connection:
        rebuild_projections(connection, "campaign-1", store.read("campaign-1"))
    with store.engine.connect() as connection:
        assert tuple(connection.scalar(select(table.c.data)) for table in (
            players, memberships, play_sessions, scenes, chat_messages,
        )) == live