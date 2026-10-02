from backend.models.chat import Visibility
from backend.models.state import GameState
from backend.services.context_service import ContextService, MemoryFact


def test_context_is_bounded_and_layered():
    service = ContextService()
    result = service.build("campaign-1", GameState(campaign_id="campaign-1", branch_id="branch-1"), [], "protocol", "rules", "setting", "input", budget=40)

    assert result["characters"] <= 40
    assert result["layers"]
    assert service.usage_report("campaign-1")["characters"] == result["characters"]


def test_memory_search_filters_gm_secrets():
    service = ContextService()
    service.add_memory("campaign-1", MemoryFact("The prince owes Kira a favor."))
    service.add_memory("campaign-1", MemoryFact("The hidden vampire identity.", visibility=Visibility(scope="gm_only")))

    assert len(service.search_memory("campaign-1", "prince favor")) == 1
    assert service.search_memory("campaign-1", "hidden vampire") == []
    assert len(service.search_memory("campaign-1", "hidden vampire", actor_scope="gm")) == 1


def test_summary_records_coverage_sequences():
    summary = ContextService.summarize([], "scene")

    assert summary["level"] == "scene"
    assert summary["covers_from_seq"] == 0