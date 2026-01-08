from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class LLMResponse:
    """
    Canonical LLM Response
    用于非 streaming 场景
    """
    text: str
    thinking: Optional[str] = None

    usage: Optional[dict] = None
    raw: Optional[Any] = None
