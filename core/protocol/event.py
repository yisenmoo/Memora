from dataclasses import dataclass, field
import time

@dataclass
class LLMEvent:
    """
    Canonical streaming event
    """
    type: str        # thinking | output | tool | error | done
    source: str      # e.g. llm:qwen3-8b / llm:goapi-gpt4
    text: str = ""
    ts: float = field(default_factory=time.time)
