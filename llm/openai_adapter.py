import openai
import time
from typing import Generator, List, Dict
from core.protocol.request import LLMRequest, Message
from core.protocol.response import LLMResponse
from core.protocol.event import LLMEvent
from llm.base import BaseLLM

class OpenAILLM(BaseLLM):
    def __init__(self, api_key: str, model: str, base_url: str = None):
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        # OpenAI style messages
        return [{"role": m.role, "content": m.content} for m in messages]

    def call(self, req: LLMRequest) -> LLMResponse:
        messages = self._convert_messages(req.messages)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            stream=False
        )
        
        text = response.choices[0].message.content
        usage = response.usage.model_dump() if response.usage else None
        
        return LLMResponse(
            text=text,
            raw=response.model_dump(),
            usage=usage
        )

    def stream(self, req: LLMRequest) -> Generator[LLMEvent, None, None]:
        messages = self._convert_messages(req.messages)
        
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            stream=True
        )
        
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield LLMEvent(
                    type="output",
                    source=f"llm:{self.name}",
                    text=delta,
                    ts=time.time()
                )
        
        yield LLMEvent(type="done", source=f"llm:{self.name}", text="", ts=time.time())
