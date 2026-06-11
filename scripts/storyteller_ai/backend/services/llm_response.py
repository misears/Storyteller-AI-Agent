from typing import Optional, Dict, Any


class LLMResponse:
    def __init__(self, text: str, metadata: Optional[Dict[str, Any]] = None):
        self.text = text
        self.metadata = metadata or {}
