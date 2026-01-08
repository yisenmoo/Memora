import dashscope
import time
from http import HTTPStatus
from typing import Generator, List, Dict
from core.protocol.request import LLMRequest, Message
from core.protocol.response import LLMResponse
from core.protocol.event import LLMEvent
from llm.base import BaseLLM

class DashScopeLLM(BaseLLM):
    def __init__(self, api_key: str, model: str):
        dashscope.api_key = api_key
        self.model = model

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def call(self, req: LLMRequest) -> LLMResponse:
        messages = self._convert_messages(req.messages)
        
        response = dashscope.Generation.call(
            model=self.model,
            messages=messages,
            temperature=req.temperature,
            result_format='message'
        )
        
        if response.status_code == HTTPStatus.OK:
            text = response.output.choices[0].message.content
            usage = response.usage
            return LLMResponse(
                text=text,
                raw=response,
                usage=usage
            )
        else:
            raise Exception(f"DashScope Error: {response.code} - {response.message}")

    def stream(self, req: LLMRequest) -> Generator[LLMEvent, None, None]:
        messages = self._convert_messages(req.messages)
        
        responses = dashscope.Generation.call(
            model=self.model,
            messages=messages,
            result_format='message',
            stream=True,
            output_in_full_message=False, # Incremental output
            temperature=req.temperature
        )
        
        for response in responses:
            if response.status_code == HTTPStatus.OK:
                delta = response.output.choices[0].message.content
                if delta:
                    yield LLMEvent(
                        type="output",
                        source=f"llm:{self.name}",
                        text=delta,
                        ts=time.time()
                    )
            else:
                yield LLMEvent(
                    type="error",
                    source=f"llm:{self.name}",
                    text=f"Error: {response.code} - {response.message}",
                    ts=time.time()
                )
        
        yield LLMEvent(type="done", source=f"llm:{self.name}", text="", ts=time.time())
