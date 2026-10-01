from backend.services.llm_utils import extract_actions


def test_extract_actions_only_accepts_final_fenced_json():
    text, actions = extract_actions("Narration\n```storyteller-actions\n{\"actions\": [{\"tool\": \"roll_dice\"}]}\n```")

    assert text == "Narration"
    assert actions == [{"tool": "roll_dice"}]


def test_extract_actions_keeps_invalid_or_nonfinal_blocks():
    invalid = "Narration\n```json\n{bad}\n```"
    trailing = "Narration\n```json\n{\"actions\": []}\n```\ntrailing"

    assert extract_actions(invalid) == (invalid, None)
    assert extract_actions(trailing) == (trailing, None)