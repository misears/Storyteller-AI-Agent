class AssistantMode:
    name = "assistant"

    def build_mode_instructions(self) -> str:
        return (
            "You are a Storyteller's assistant. Offer suggestions, hooks, and consequences, "
            "but do not override the human GM."
        )
