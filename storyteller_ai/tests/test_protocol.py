from backend.gm_modes.protocol import build_protocol
from backend.rules.registry import RulesetRegistry, SettingRegistry


def test_layered_protocol_is_ruleset_and_setting_aware():
    ruleset = RulesetRegistry().get("vtm-revised")
    setting = SettingRegistry().get("wod-city-nights")
    prompt = build_protocol(ruleset, setting, "group", "A" * 20000, max_context_chars=100)

    assert "[RULESET: Vampire Storyteller Revised Structure" in prompt
    assert "[SETTING: World of Darkness City Nights Structure]" in prompt
    assert "[MODE: group]" in prompt
    assert "A" * 101 not in prompt