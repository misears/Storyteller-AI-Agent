"""Measure local replay and non-LLM persistence overhead targets."""

import os
import tempfile
from time import perf_counter


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="storyteller-performance-") as directory:
        os.environ["STORYTELLER_DATA_DIR"] = directory
        from backend.models.campaign import Actor
        from backend.persistence.db import create_campaign_engine
        from backend.persistence.event_store import EventStore
        from backend.services.campaign_service import campaign_service

        campaign = campaign_service.create("Performance")
        engine = create_campaign_engine()
        try:
            for index in range(1000):
                with EventStore(engine).transaction(campaign.id, campaign.active_branch_id) as writer:
                    writer.append("message.posted", {
                        "id": f"message-{index}", "speaker_kind": "system", "content": str(index),
                    }, Actor(kind="system"))
            start = perf_counter()
            campaign_service.state(campaign)
            replay_seconds = perf_counter() - start
            start = perf_counter()
            with EventStore(engine).transaction(campaign.id, campaign.active_branch_id) as writer:
                writer.append("message.posted", {
                    "id": "overhead", "speaker_kind": "system", "content": "turn",
                }, Actor(kind="system"))
            overhead_ms = (perf_counter() - start) * 1000
        finally:
            engine.dispose()
    print({"replay_seconds": replay_seconds, "non_llm_overhead_ms": overhead_ms})


if __name__ == "__main__":
    main()