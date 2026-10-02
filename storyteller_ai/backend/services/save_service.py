from datetime import datetime, timezone
import io
import json
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select

from ..domain.reducers import replay
from ..models.campaign import Actor, Campaign
from ..persistence.db import create_campaign_engine, upgrade_database
from ..persistence.event_store import EventStore
from ..persistence.projectors import project_event
from ..persistence.tables import branches, campaigns, events, saves
from ..models.state import Event


class SaveService:
    def _engine(self):
        upgrade_database()
        return create_campaign_engine()

    def create(self, campaign: Campaign, name: str) -> dict:
        engine = self._engine()
        try:
            history = EventStore(engine).read(campaign.id, campaign.active_branch_id)
            state = replay(campaign.id, campaign.active_branch_id, history).model_dump(mode="json")
            event_seq = history[-1].seq if history else 0
            save_id = str(uuid4())
            data = {"state": state, "ruleset_version": campaign.ruleset_version,
                    "setting_pack_version": campaign.setting_pack_version}
            with engine.begin() as connection:
                connection.execute(saves.insert().values(
                    id=save_id, campaign_id=campaign.id, branch_id=campaign.active_branch_id,
                    name=name, event_seq=event_seq, data=data,
                    created_at=datetime.now(timezone.utc).isoformat(),
                ))
            return {"id": save_id, "name": name, "event_seq": event_seq, **data}
        finally:
            engine.dispose()

    def list(self, campaign: Campaign) -> list[dict]:
        engine = self._engine()
        try:
            with engine.connect() as connection:
                rows = connection.execute(select(saves).where(saves.c.campaign_id == campaign.id)).mappings().all()
            return [dict(row) for row in rows]
        finally:
            engine.dispose()

    def load(self, campaign: Campaign, save_id: str) -> str:
        engine = self._engine()
        try:
            with engine.begin() as connection:
                save = connection.execute(select(saves).where(saves.c.id == save_id)).mappings().one_or_none()
                if save is None:
                    raise KeyError(f"save {save_id} not found")
                branch_id = str(uuid4())
                connection.execute(branches.insert().values(
                    id=branch_id, campaign_id=campaign.id,
                    parent_branch_id=save["branch_id"], forked_at_seq=save["event_seq"], label=save["name"],
                ))
                updated = campaign.model_copy(update={"active_branch_id": branch_id, "updated_at": datetime.now(timezone.utc)})
                connection.execute(campaigns.update().where(campaigns.c.id == campaign.id).values(
                    active_branch_id=branch_id, data=updated.model_dump(mode="json"),
                ))
            return branch_id
        finally:
            engine.dispose()

    def export(self, campaign: Campaign) -> bytes:
        engine = self._engine()
        try:
            with engine.connect() as connection:
                history = [dict(row) for row in connection.execute(select(events).where(events.c.campaign_id == campaign.id)).mappings()]
                saved = [dict(row) for row in connection.execute(select(saves).where(saves.c.campaign_id == campaign.id)).mappings()]
            memory = io.BytesIO()
            with ZipFile(memory, "w", ZIP_DEFLATED) as archive:
                archive.writestr("campaign.json", campaign.model_dump_json())
                archive.writestr("events.json", json.dumps(history, default=str))
                archive.writestr("saves.json", json.dumps(saved, default=str))
            return memory.getvalue()
        finally:
            engine.dispose()

    @staticmethod
    def inspect_export(archive_bytes: bytes) -> dict:
        if len(archive_bytes) > 50 * 1024 * 1024:
            raise ValueError("export is too large")
        with ZipFile(io.BytesIO(archive_bytes)) as archive:
            if len(archive.infolist()) > 100:
                raise ValueError("export contains too many files")
            names = [item.filename for item in archive.infolist()]
            if any(name.startswith("/") or ".." in name.split("/") for name in names):
                raise ValueError("export contains an unsafe path")
            if any(name.lower().endswith(".pdf") for name in names):
                raise ValueError("exports cannot contain source PDFs")
            required = {"campaign.json", "events.json", "saves.json"}
            if not required.issubset(names):
                raise ValueError("export is missing required files")
            campaign = json.loads(archive.read("campaign.json"))
            events_data = json.loads(archive.read("events.json"))
            saves_data = json.loads(archive.read("saves.json"))
            if not isinstance(campaign, dict) or not isinstance(events_data, list) or not isinstance(saves_data, list):
                raise ValueError("export has invalid JSON structure")
            return {"campaign": campaign, "event_count": len(events_data), "save_count": len(saves_data)}

    def import_archive(self, archive_bytes: bytes) -> Campaign:
        self.inspect_export(archive_bytes)
        with ZipFile(io.BytesIO(archive_bytes)) as archive:
            source_campaign = Campaign.model_validate(json.loads(archive.read("campaign.json")))
            source_events = json.loads(archive.read("events.json"))
            source_saves = json.loads(archive.read("saves.json"))
        new_campaign_id = str(uuid4())
        new_branch_id = str(uuid4())
        campaign = source_campaign.model_copy(update={
            "id": new_campaign_id, "active_branch_id": new_branch_id,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        })
        engine = self._engine()
        try:
            with engine.begin() as connection:
                connection.execute(campaigns.insert().values(
                    id=new_campaign_id, data=campaign.model_dump(mode="json"),
                    status=campaign.status, active_branch_id=new_branch_id,
                ))
                connection.execute(branches.insert().values(
                    id=new_branch_id, campaign_id=new_campaign_id, label="imported",
                ))
                for raw in source_events:
                    payload = raw["payload"]
                    if raw["type"] == "campaign.created" and "campaign" in payload:
                        payload = {"campaign": campaign.model_dump(mode="json")}
                    event = Event(
                        seq=raw["seq"], campaign_id=new_campaign_id, branch_id=new_branch_id,
                        type=raw["type"], payload=payload, payload_version=raw.get("payload_version", 1),
                        actor=Actor(kind=raw["actor_kind"], id=raw.get("actor_id")),
                        turn_id=raw.get("turn_id"), created_at=datetime.fromisoformat(raw["created_at"]),
                    )
                    connection.execute(events.insert().values(
                        campaign_id=new_campaign_id, seq=event.seq, branch_id=new_branch_id,
                        type=event.type, payload=event.payload, payload_version=event.payload_version,
                        actor_kind=event.actor.kind, actor_id=event.actor.id, turn_id=event.turn_id,
                        created_at=event.created_at.isoformat(),
                    ))
                    project_event(connection, event)
                for raw in source_saves:
                    connection.execute(saves.insert().values(
                        id=str(uuid4()), campaign_id=new_campaign_id, branch_id=new_branch_id,
                        name=raw["name"], event_seq=raw["event_seq"], data=raw["data"],
                        created_at=raw["created_at"],
                    ))
            return campaign
        finally:
            engine.dispose()


save_service = SaveService()