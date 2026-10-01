import json

import yaml

from backend.rules.registry import RulesetRegistry, SettingRegistry


def _ruleset_manifest():
    return {
        "id": "test-rules", "version": "1.0.0", "name": "Test Rules",
        "license": "CC0", "dice": {"kind": "bands", "default_expression": "2d6"},
        "attributes": [], "checks": [],
        "turn_rules": {"combat_turn_mode": "freeform"}, "chargen": [],
        "npc_tiers": [], "prompt_digest": "test",
    }


def _write_ruleset(root, name="test-rules", manifest=None, schema=None):
    pack = root / name
    pack.mkdir()
    (pack / "ruleset.yaml").write_text(yaml.safe_dump(manifest or _ruleset_manifest()), encoding="utf-8")
    (pack / "sheet.schema.json").write_text(json.dumps(schema or {"type": "object"}), encoding="utf-8")


def test_ruleset_registry_validates_schema_and_discovers_packs(tmp_path):
    bundled = tmp_path / "bundled"
    local = tmp_path / "local"
    bundled.mkdir()
    local.mkdir()
    _write_ruleset(bundled)
    _write_ruleset(local, "local-rules", {**_ruleset_manifest(), "id": "local-rules"})

    registry = RulesetRegistry([("bundled", bundled), ("local", local)])

    assert [item.value.id for item in registry.list()] == ["test-rules", "local-rules"]
    assert registry.get("test-rules").sheet_schema == {"type": "object"}
    assert registry.issues() == []


def test_invalid_packs_are_reported_and_not_loaded(tmp_path):
    root = tmp_path / "settings"
    root.mkdir()
    invalid = root / "broken"
    invalid.mkdir()
    (invalid / "setting.yaml").write_text("id: broken\n", encoding="utf-8")

    registry = SettingRegistry([("local", root)])

    assert registry.list() == []
    assert len(registry.issues()) == 1
    assert "compatible_rulesets" in registry.issues()[0].error


def test_bundled_pack_wins_duplicate_id_and_version(tmp_path):
    bundled = tmp_path / "bundled"
    local = tmp_path / "local"
    bundled.mkdir()
    local.mkdir()
    _write_ruleset(bundled)
    _write_ruleset(local)

    registry = RulesetRegistry([("bundled", bundled), ("local", local)])

    assert len(registry.list()) == 1
    assert registry.list()[0].source == "bundled"


def test_bundled_rulesets_validate():
    registry = RulesetRegistry()

    assert [entry.value.id for entry in registry.list()] == ["freeform", "pbta-generic", "vtm-revised"]
    assert registry.issues() == []
    assert registry.get("pbta-generic").dice.kind == "bands"


def test_vtm_ruleset_and_city_setting_validate():
    rulesets = RulesetRegistry()
    settings = SettingRegistry()

    assert rulesets.get("vtm-revised").family == "storyteller-classic"
    city = settings.get("wod-city-nights")
    assert city.compatible_rulesets == ["vtm-revised"]
    assert {tracker.id for tracker in city.trackers} == {"masquerade", "camarilla", "anarchs"}
    assert rulesets.issues() == []
    assert settings.issues() == []