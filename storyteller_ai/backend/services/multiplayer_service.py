from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from ..models.campaign import Actor, Membership, Player
from ..persistence.db import create_campaign_engine
from ..persistence.event_store import EventStore
from ..persistence.tables import memberships


class MultiplayerService:
    def join(self, campaign_id: str, branch_id: str, display_name: str, role: str = "player") -> Player:
        engine = create_campaign_engine()
        try:
            with EventStore(engine).transaction(campaign_id, branch_id) as writer:
                active = writer.connection.execute(select(memberships.c.player_id).where(
                    memberships.c.campaign_id == campaign_id,
                    memberships.c.data["status"].as_string() == "active",
                )).all()
                if len(active) >= 10:
                    raise ValueError("campaign has reached the ten-player limit")
                player = Player(id=str(uuid4()), display_name=display_name, created_at=datetime.now(timezone.utc))
                membership = Membership(
                    campaign_id=campaign_id, player_id=player.id, role=role,
                    joined_at=datetime.now(timezone.utc),
                )
                writer.append("player.joined", {
                    "player": player.model_dump(mode="json"),
                    "membership": membership.model_dump(mode="json"),
                }, Actor(kind="system"))
                return player
        finally:
            engine.dispose()

    def set_status(self, campaign_id: str, branch_id: str, player_id: str, status: str) -> None:
        if status not in {"active", "away", "left"}:
            raise ValueError("invalid player status")
        engine = create_campaign_engine()
        try:
            with EventStore(engine).transaction(campaign_id, branch_id) as writer:
                writer.append("player.left" if status == "left" else "player.status_changed", {
                    "player_id": player_id, "status": status,
                }, Actor(kind="system"))
        finally:
            engine.dispose()

    def select_character(self, campaign_id: str, branch_id: str, player_id: str, character_id: str) -> Membership:
        engine = create_campaign_engine()
        try:
            with EventStore(engine).transaction(campaign_id, branch_id) as writer:
                data = writer.connection.scalar(select(memberships.c.data).where(
                    memberships.c.campaign_id == campaign_id, memberships.c.player_id == player_id,
                ))
                if data is None:
                    raise KeyError("player is not a campaign member")
                character_ids = list(data.get("character_ids", []))
                if character_id not in character_ids:
                    character_ids.append(character_id)
                membership = Membership.model_validate({**data, "character_ids": character_ids, "active_character_id": character_id})
                writer.append("player.character_selected", {"player_id": player_id, "membership": membership.model_dump(mode="json")}, Actor(kind="system"))
                return membership
        finally:
            engine.dispose()


multiplayer_service = MultiplayerService()