from sqlalchemy import Connection, delete, select
from sqlalchemy.dialects.sqlite import insert

from ..models.chat import ChatMessage
from ..models.state import Event
from .tables import campaigns, chat_messages, memberships, play_sessions, players, scenes, turns


def _upsert(connection: Connection, table, values: dict) -> None:
    statement = insert(table).values(**values)
    connection.execute(statement.on_conflict_do_update(
        index_elements=list(table.primary_key.columns),
        set_={key: value for key, value in values.items() if key not in table.primary_key.columns.keys()},
    ))


def _patch_data(connection: Connection, table, key, changes: dict) -> None:
    data = connection.scalar(select(table.c.data).where(key))
    if data is not None:
        connection.execute(table.update().where(key).values(data={**data, **changes}))


def project_event(connection: Connection, event: Event) -> None:
    payload = event.payload
    if event.type == "campaign.created" or event.type == "campaign.configured":
        campaign = payload["campaign"]
        _upsert(connection, campaigns, {
            "id": event.campaign_id, "data": campaign,
            "status": campaign["status"], "active_branch_id": campaign["active_branch_id"],
        })
    elif event.type == "player.joined":
        player = payload["player"]
        membership = payload["membership"]
        _upsert(connection, players, {"id": player["id"], "data": player})
        _upsert(connection, memberships, {
            "campaign_id": event.campaign_id, "player_id": player["id"], "data": membership,
        })
    elif event.type in ("player.left", "player.status_changed"):
        status = "left" if event.type == "player.left" else payload["status"]
        changes = {"status": status}
        if status == "left":
            changes["left_at"] = event.created_at.isoformat()
        _patch_data(connection, memberships, (
            memberships.c.campaign_id == event.campaign_id
        ) & (memberships.c.player_id == payload["player_id"]), changes)
    elif event.type == "session.started":
        _upsert(connection, play_sessions, {
            "id": payload["id"], "campaign_id": event.campaign_id, "data": payload,
        })
    elif event.type == "session.ended":
        _patch_data(connection, play_sessions, play_sessions.c.id == payload["id"], {
            "ended_at": event.created_at.isoformat(), "recap": payload.get("recap"),
        })
    elif event.type == "scene.started" or event.type == "scene.updated":
        scene = payload["scene"]
        _upsert(connection, scenes, {
            "id": scene["id"], "campaign_id": event.campaign_id,
            "branch_id": event.branch_id, "data": scene,
        })
    elif event.type == "scene.ended":
        _patch_data(connection, scenes, scenes.c.id == payload["id"], {
            "ended_at": event.created_at.isoformat(),
        })
    elif event.type == "turn.started":
        _upsert(connection, turns, {
            "id": event.turn_id, "campaign_id": event.campaign_id,
            "branch_id": event.branch_id, "status": "in_progress", "started_seq": event.seq,
            "ended_seq": None,
        })
    elif event.type in ("turn.completed", "turn.interrupted", "turn.failed"):
        connection.execute(turns.update().where(turns.c.id == event.turn_id).values(
            status=event.type.split(".")[1], ended_seq=event.seq,
        ))
    elif event.type == "message.posted":
        message = ChatMessage.model_validate({
            **payload, "campaign_id": event.campaign_id, "branch_id": event.branch_id,
            "seq": event.seq, "turn_id": event.turn_id, "created_at": event.created_at,
        })
        connection.execute(chat_messages.insert().values(
            id=message.id, campaign_id=message.campaign_id, branch_id=message.branch_id,
            seq=message.seq, session_id=message.session_id, scene_id=message.scene_id,
            turn_id=message.turn_id, speaker_kind=message.speaker_kind,
            player_id=message.player_id, character_id=message.character_id,
            client_msg_id=message.client_msg_id, data=message.model_dump(mode="json"),
        ))
    elif event.type == "message.redacted":
        _patch_data(connection, chat_messages, chat_messages.c.id == payload["id"], {
            "content": "[redacted]",
        })


def rebuild_projections(connection: Connection, campaign_id: str, events: list[Event]) -> None:
    for table in (chat_messages, turns, scenes, play_sessions, memberships):
        connection.execute(delete(table).where(table.c.campaign_id == campaign_id))
    for event in events:
        project_event(connection, event)