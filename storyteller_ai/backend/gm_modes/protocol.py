from ..models.ruleset import Ruleset, SettingPack


def build_protocol(
    ruleset: Ruleset, setting: SettingPack, mode: str,
    context: str = "", max_context_chars: int = 12000,
) -> str:
    context = context[:max_context_chars]
    return "\n\n".join([
        "[IDENTITY]\nYou are the Storyteller. Run the tabletop campaign and protect player agency.",
        "[HARD RULES]\nNever invent dice results. Use validated tools for rolls and state changes. Keep secrets private.",
        f"[RULESET: {ruleset.name} {ruleset.version}]\n{ruleset.prompt_digest}\nChecks: {', '.join(check.id for check in ruleset.checks) or 'none'}",
        f"[SETTING: {setting.name}]\n{setting.prompt_digest}\nTone: {', '.join(setting.tone)}\nLines: {', '.join(setting.default_lines)}",
        f"[MODE: {mode}]\nAddress the acting character and end with a clear next-action prompt.",
        "[TURN PROCEDURE]\nRead context, decide whether a roll is needed, call tools, then narrate only from tool results.",
        f"[CAMPAIGN CONTEXT]\n{context}",
    ])