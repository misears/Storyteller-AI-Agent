from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from ..domain.reducers import replay
from ..models.campaign import Actor, Campaign, GMMode
from ..persistence.db import create_campaign_engine, upgrade_database
from ..persistence.event_store import EventStore
from ..persistence.tables import branches, campaigns
from .app_paths import get_data_dir


class CampaignService:
    def _engine(self):
        if not (get_data_dir() / "campaigns.db").exists():
            upgrade_database()
        return create_campaign_engine()

    def create(
        self, title: str = "", mode: GMMode = GMMode.GROUP,
        setting: str = "", document_ids: list[str] | None = None,
        campaign_genres: list[str] | None = None,
    ) -> Campaign:
        now = datetime.now(timezone.utc)
        campaign = Campaign(
            id=str(uuid4()), title=title, mode=mode,
            ruleset_id="freeform", ruleset_version="1.0",
            setting_pack_id=setting or "default", setting_pack_version="1.0",
            source_document_ids=document_ids or [], rng_seed_ref=str(uuid4()),
            active_branch_id=str(uuid4()), created_at=now, updated_at=now,
            bible={"legacy_campaign_genres": campaign_genres or []},
        )
        engine = self._engine()
        try:
            store = EventStore(engine)
            with store.transaction(campaign.id, campaign.active_branch_id) as writer:
                writer.connection.execute(campaigns.insert().values(
                    id=campaign.id, data=campaign.model_dump(mode="json"),
                    status=campaign.status, active_branch_id=campaign.active_branch_id,
                ))
                writer.connection.execute(branches.insert().values(
                    id=campaign.active_branch_id, campaign_id=campaign.id, label="main",
                ))
                writer.append("campaign.created", {"campaign": campaign.model_dump(mode="json")}, Actor(kind="system"))
        finally:
            engine.dispose()
        return campaign

    def get(self, campaign_id: str) -> Campaign | None:
        engine = self._engine()
        try:
            with engine.connect() as connection:
                data = connection.scalar(select(campaigns.c.data).where(campaigns.c.id == campaign_id))
            return Campaign.model_validate(data) if data is not None else None
        finally:
            engine.dispose()

    def list(self) -> list[Campaign]:
        engine = self._engine()
        try:
            with engine.connect() as connection:
                data = connection.scalars(select(campaigns.c.data)).all()
            return [Campaign.model_validate(item) for item in data]
        finally:
            engine.dispose()

    def state(self, campaign: Campaign):
        engine = self._engine()
        try:
            history = EventStore(engine).read(campaign.id, campaign.active_branch_id)
            return replay(campaign.id, campaign.active_branch_id, history)
        finally:
            engine.dispose()


campaign_service = CampaignService()