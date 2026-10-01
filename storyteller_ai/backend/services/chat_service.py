from uuid import uuid4

from sqlalchemy import select

from ..models.campaign import Actor
from ..models.chat import ChatMessage, Visibility
from ..persistence.db import create_campaign_engine
from ..persistence.event_store import EventStore
from ..persistence.tables import chat_messages


class ChatService:
    def post(
        self, campaign_id: str, branch_id: str, content: str,
        speaker_kind: str, player_id: str | None = None,
        client_msg_id: str | None = None, visibility: Visibility | None = None,
        session_id: str | None = None, scene_id: str | None = None,
    ) -> ChatMessage:
        engine = create_campaign_engine()
        try:
            with EventStore(engine).transaction(campaign_id, branch_id) as writer:
                if client_msg_id is not None:
                    existing = writer.connection.scalar(select(chat_messages.c.data).where(
                        chat_messages.c.campaign_id == campaign_id,
                        chat_messages.c.client_msg_id == client_msg_id,
                    ))
                    if existing is not None:
                        return ChatMessage.model_validate(existing)
                actor = Actor(kind="player" if speaker_kind == "player" else "system", id=player_id)
                event = writer.append("message.posted", {
                    "id": str(uuid4()), "speaker_kind": speaker_kind,
                    "player_id": player_id, "content": content,
                    "client_msg_id": client_msg_id,
                    "session_id": session_id, "scene_id": scene_id,
                    "visibility": (visibility or Visibility()).model_dump(),
                }, actor)
                message_data = writer.connection.scalar(select(chat_messages.c.data).where(
                    chat_messages.c.campaign_id == campaign_id,
                    chat_messages.c.seq == event.seq,
                ))
                return ChatMessage.model_validate(message_data)
        finally:
            engine.dispose()

    def list(
        self, campaign_id: str, branch_id: str, after_seq: int = 0,
        limit: int = 50, session_id: str | None = None,
        scene_id: str | None = None, speaker_kind: str | None = None,
    ) -> tuple[list[ChatMessage], int | None]:
        engine = create_campaign_engine()
        try:
            query = select(chat_messages.c.data).where(
                chat_messages.c.campaign_id == campaign_id,
                chat_messages.c.branch_id == branch_id,
                chat_messages.c.seq > after_seq,
            )
            if session_id is not None:
                query = query.where(chat_messages.c.session_id == session_id)
            if scene_id is not None:
                query = query.where(chat_messages.c.scene_id == scene_id)
            if speaker_kind is not None:
                query = query.where(chat_messages.c.speaker_kind == speaker_kind)
            with engine.connect() as connection:
                data = connection.scalars(query.order_by(chat_messages.c.seq).limit(limit + 1)).all()
            messages = [ChatMessage.model_validate(item) for item in data[:limit]]
            next_after_seq = messages[-1].seq if len(data) > limit else None
            return messages, next_after_seq
        finally:
            engine.dispose()


chat_service = ChatService()