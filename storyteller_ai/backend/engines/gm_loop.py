from typing import Optional

from ..gm_modes.orchestrator import GMOrchestrator
from ..services.llm_client import LLMClient
from ..services.llm_utils import extract_state_update

class GMLoop:
    def __init__(self, mode: str = "group", llm_client: Optional[LLMClient] = None):
        self.mode = mode
        self.orchestrator = GMOrchestrator(mode)
        self.llm = llm_client or LLMClient()

    async def step(self, user_message: str) -> dict:
        system_prompt = await self.orchestrator.build_prompt(user_message)
        response = await self.llm.generate(
            system_prompt=system_prompt,
            user_message=user_message,
        )

        cleaned_text, state_update = extract_state_update(response.text)
        if state_update:
            self.orchestrator.apply_state_update(state_update)

        return {"text": cleaned_text, "mode": self.mode}
