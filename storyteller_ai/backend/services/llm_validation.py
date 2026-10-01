import re


ROLL_PATTERN = re.compile(r"\b(?:rolled|roll|got|scored)\s+(\d+)\b|\b(\d+)\s+success(?:es)?\b", re.IGNORECASE)


def validate_narration(text: str, established_rolls: list[dict]) -> None:
    if not ROLL_PATTERN.search(text):
        return
    established_numbers = {
        str(value)
        for roll in established_rolls
        for value in (roll.get("total"), roll.get("successes"))
        if value is not None
    }
    mentioned = {value for match in ROLL_PATTERN.findall(text) for value in match if value}
    if not mentioned.intersection(established_numbers):
        raise ValueError("narration mentions an unestablished roll result")