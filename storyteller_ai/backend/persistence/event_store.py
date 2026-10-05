from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import Connection, Engine, and_, false, func, or_, select

from ..models.campaign import Actor
from ..models.state import Event
from .db import create_campaign_engine
from .projectors import project_event
from .tables import branches, events


def branch_lineage_filter(connection: Connection, campaign_id: str, branch_id: str, table):
    clauses = []
    current_id: str | None = branch_id
    inherited_through: int | None = None
    while current_id is not None:
        branch = connection.execute(select(branches).where(
            branches.c.id == current_id,
            branches.c.campaign_id == campaign_id,
        )).mappings().one_or_none()
        if branch is None:
            break
        conditions = [table.c.branch_id == current_id]
        if inherited_through is not None:
            conditions.append(table.c.seq <= inherited_through)
        clauses.append(and_(*conditions))
        parent_id = branch["parent_branch_id"]
        if parent_id is None:
            break
        forked_at_seq = int(branch["forked_at_seq"] or 0)
        inherited_through = (
            forked_at_seq if inherited_through is None
            else min(inherited_through, forked_at_seq)
        )
        current_id = parent_id
    return or_(*clauses) if clauses else false()


class EventWriter:
    def __init__(self, connection: Connection, campaign_id: str, branch_id: str):
        self.connection = connection
        self.campaign_id = campaign_id
        self.branch_id = branch_id
        self.seq = connection.scalar(
            select(func.coalesce(func.max(events.c.seq), 0)).where(events.c.campaign_id == campaign_id)
        )

    def append(self, event_type: str, payload: dict, actor: Actor, turn_id: str | None = None) -> Event:
        self.seq += 1
        event = Event(
            seq=self.seq, campaign_id=self.campaign_id, branch_id=self.branch_id,
            type=event_type, payload=payload, actor=actor, turn_id=turn_id,
            created_at=datetime.now(timezone.utc),
        )
        self.connection.execute(events.insert().values(
            campaign_id=event.campaign_id, seq=event.seq, branch_id=event.branch_id,
            type=event.type, payload=event.payload, payload_version=event.payload_version,
            actor_kind=event.actor.kind, actor_id=event.actor.id,
            turn_id=event.turn_id, created_at=event.created_at.isoformat(),
        ))
        project_event(self.connection, event)
        return event


class EventStore:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or create_campaign_engine()

    @contextmanager
    def transaction(self, campaign_id: str, branch_id: str) -> Iterator[EventWriter]:
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                yield EventWriter(connection, campaign_id, branch_id)
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def read(self, campaign_id: str, branch_id: str | None = None, after_seq: int = 0) -> list[Event]:
        if branch_id is not None:
            with self.engine.connect() as connection:
                branch = connection.execute(select(branches).where(branches.c.id == branch_id)).mappings().one_or_none()
            if branch and branch["parent_branch_id"]:
                inherited = self.read(campaign_id, branch["parent_branch_id"], after_seq)
                inherited = [event for event in inherited if event.seq <= (branch["forked_at_seq"] or 0)]
                child = self._read_events(campaign_id, branch_id, after_seq)
                return inherited + child
        return self._read_events(campaign_id, branch_id, after_seq)

    def _read_events(self, campaign_id: str, branch_id: str | None, after_seq: int) -> list[Event]:
        query = select(events).where(events.c.campaign_id == campaign_id, events.c.seq > after_seq)
        if branch_id is not None:
            query = query.where(events.c.branch_id == branch_id)
        with self.engine.connect() as connection:
            rows = connection.execute(query.order_by(events.c.seq)).mappings().all()
        return [Event(
            seq=row["seq"], campaign_id=row["campaign_id"], branch_id=row["branch_id"],
            type=row["type"], payload=row["payload"], payload_version=row["payload_version"],
            actor=Actor(kind=row["actor_kind"], id=row["actor_id"]),
            turn_id=row["turn_id"], created_at=datetime.fromisoformat(row["created_at"]),
        ) for row in rows]