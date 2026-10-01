import json
import re
from typing import Any, Dict, Optional, Tuple

JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
FENCE_RE = re.compile(r"```(?:storyteller-actions|json)[ \t]*\r?\n", re.IGNORECASE)


def extract_state_update(text: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    match = JSON_BLOCK_RE.search(text)
    if not match:
        return text, None

    json_str = match.group(0)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return text, None

    state_update = data.get("state_update")
    cleaned = text.replace(json_str, "").strip()
    return cleaned, state_update


def extract_actions(text: str) -> Tuple[str, Optional[list[dict[str, Any]]]]:
    matches = list(FENCE_RE.finditer(text))
    if not matches:
        return text, None
    match = matches[-1]
    closing = re.compile(r"\s*```\s*\Z")
    body = text[match.end():]
    try:
        data, end = json.JSONDecoder().raw_decode(body.lstrip())
    except json.JSONDecodeError:
        return text, None
    consumed = len(body) - len(body.lstrip()) + end
    if not closing.match(body, consumed):
        return text, None
    actions = data.get("actions") if isinstance(data, dict) else None
    if not isinstance(actions, list) or any(not isinstance(action, dict) for action in actions):
        return text, None
    return text[:match.start()].rstrip(), actions
