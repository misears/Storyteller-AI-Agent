import asyncio

from httpx2 import ASGITransport, AsyncClient

from backend.main import app


def test_pack_discovery_routes():
    async def request():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
            rulesets = await client.get("/rulesets")
            vtm = await client.get("/rulesets/vtm-revised")
            schema = await client.get("/rulesets/pbta-generic/sheet-schema")
            themes = await client.get("/themes", params={"ruleset": "vtm-revised"})
            return rulesets, vtm, schema, themes

    rulesets, vtm, schema, themes = asyncio.new_event_loop().run_until_complete(request())

    assert rulesets.status_code == 200
    assert {item["id"] for item in rulesets.json()} >= {"freeform", "pbta-generic", "vtm-revised"}
    assert vtm.status_code == 200
    assert "sheet_schema" not in vtm.json()
    assert schema.json()["type"] == "object"
    assert themes.status_code == 200
    assert [theme["id"] for theme in themes.json()] == ["wod-city-nights"]