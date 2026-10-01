import asyncio

from httpx2 import ASGITransport, AsyncClient

from backend.engines.dice_pool import roll_dice_pool
from backend.main import app
from backend.rules.dice.engine import evaluate
from backend.rules.dice.rng import CounterRNG


def _run(coroutine):
    return asyncio.new_event_loop().run_until_complete(coroutine)


def test_counter_rng_is_reproducible_per_branch():
    first = CounterRNG(b"fixed-seed", "branch-a")
    second = CounterRNG(b"fixed-seed", "branch-a")
    other_branch = CounterRNG(b"fixed-seed", "branch-b")

    assert [first.draw(10) for _ in range(20)] == [second.draw(10) for _ in range(20)]
    assert [CounterRNG(b"fixed-seed", "branch-a").draw(100) for _ in range(2)] != [
        other_branch.draw(100) for _ in range(2)
    ]


def test_engine_interprets_sum_and_pool_mechanics():
    sum_result = evaluate("2d6+3", b"fixed-seed", "branch-a", target=8)
    pool_result = evaluate(
        "4d10>=6", b"fixed-seed", "branch-a", mechanic="pool_successes",
        target=6, params={"ones_cancel": True},
    )

    assert sum_result.total is not None
    assert sum_result.outcome in {"success", "failure"}
    assert pool_result.successes is not None
    assert pool_result.outcome in {"success", "failure", "botch"}
    assert pool_result.counter_end > pool_result.counter_start


def test_legacy_dice_pool_shim_remains_available():
    result = roll_dice_pool(0)

    assert result == {"dice": [], "successes": 0, "botch": True}


def test_campaign_dice_roll_is_logged_and_paged():
    async def request():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            campaign = await client.post("/campaigns/", json={"title": "Dice test"})
            campaign_id = campaign.json()["id"]
            roll = await client.post(
                f"/campaigns/{campaign_id}/dice",
                json={"expression": "1d20", "reason": "test roll", "target": 10},
            )
            page = await client.get(f"/campaigns/{campaign_id}/dice")
            verify = await client.get(
                f"/campaigns/{campaign_id}/dice/{roll.json()['id']}/verify"
            )
            chat = await client.get(f"/campaigns/{campaign_id}/chat")
            return campaign, roll, page, verify, chat

    campaign, roll, page, verify, chat = _run(request())

    assert campaign.status_code == 200
    assert roll.status_code == 200
    assert page.status_code == 200
    assert page.json()["rolls"][0]["id"] == roll.json()["id"]
    assert page.json()["rolls"][0]["rng"]["counter_end"] > 0
    assert verify.status_code == 200
    assert verify.json()["valid"] is True
    assert chat.json()["messages"][-1]["dice_roll_ids"] == [roll.json()["id"]]