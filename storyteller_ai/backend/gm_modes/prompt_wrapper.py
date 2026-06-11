from typing import Any, Dict


def wrap_prompt(base_protocol: str, mode_instructions: str, state_snapshot: Dict[str, Any], retrieval_text: str) -> str:
    state_str = repr(state_snapshot)
    return f"""{base_protocol}

=== GM MODE INSTRUCTIONS ===
{mode_instructions}

=== CURRENT GAME STATE (SNAPSHOT) ===
{state_str}

=== RETRIEVED CONTEXT ===
{retrieval_text}

Follow the protocol exactly.
"""
