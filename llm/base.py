from typing import Generator, Optional
from core.protocol.request import LLMRequest
from core.protocol.response import LLMResponse
from core.protocol.event import LLMEvent

class BaseLLM:
    name: str
    description: Optional[str] = None
    stream_allowed: bool = True

    def call(self, req: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    def stream(self, req: LLMRequest) -> Generator[LLMEvent, None, None]:
        raise NotImplementedError
