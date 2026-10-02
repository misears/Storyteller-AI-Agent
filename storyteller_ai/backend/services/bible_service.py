from datetime import datetime, timezone
from typing import Any

from ..models.bible import CampaignBible
from ..models.campaign import Actor, Campaign
from ..persistence.db import create_campaign_engine
from ..persistence.event_store import EventStore
from ..persistence.tables import campaigns


class BibleService:
    def generate(self, campaign: Campaign, section: str | None = None) -> CampaignBible:
        current = self._current(campaign)
        if current is None:
            current = CampaignBible(
                premise=f"A chronicle unfolds in {campaign.title or 'an unsettled world'}.",
                pitch_for_players=f"Shape the fate of {campaign.title or 'this chronicle'}.",
                themes=["choice", "consequence"],
                acts=[{"title": "First Signs", "goal": "Reveal the central pressure.", "key_beats": [], "climax": ""}],
                factions=[], key_npcs=[], locations=[], hooks=[], secrets=[],
                opening_situation="The first sign of trouble arrives at the table.",
            )
        if section is not None:
            if section not in CampaignBible.model_fields:
                raise ValueError(f"unknown bible section: {section}")
            return current
        self._persist(campaign, current, "bible.generated")
        return current

    def get(self, campaign: Campaign) -> CampaignBible | None:
        return self._current(campaign)

    def edit(self, campaign: Campaign, section: str, value: Any) -> CampaignBible:
        current = self._current(campaign)
        if current is None:
            current = self.generate(campaign)
        if section not in CampaignBible.model_fields:
            raise ValueError(f"unknown bible section: {section}")
        data = current.model_dump()
        data[section] = value
        updated = CampaignBible.model_validate(data)
        self._persist(campaign, updated, "bible.edited")
        return updated

    def _current(self, campaign: Campaign) -> CampaignBible | None:
        value = (campaign.bible or {}).get("campaign_bible")
        return CampaignBible.model_validate(value) if value else None

    def _persist(self, campaign: Campaign, bible: CampaignBible, event_type: str) -> None:
        updated = campaign.model_copy(update={"bible": {**(campaign.bible or {}), "campaign_bible": bible.model_dump(mode="json")}, "updated_at": datetime.now(timezone.utc)})
        engine = create_campaign_engine()
        try:
            with EventStore(engine).transaction(campaign.id, campaign.active_branch_id) as writer:
                writer.append(event_type, {"bible": bible.model_dump(mode="json")}, Actor(kind="system"))
                writer.connection.execute(campaigns.update().where(campaigns.c.id == campaign.id).values(data=updated.model_dump(mode="json")))
        finally:
            engine.dispose()


bible_service = BibleService()