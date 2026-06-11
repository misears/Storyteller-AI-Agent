import json
import re
from typing import Any, Dict, Optional, Tuple

JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


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
