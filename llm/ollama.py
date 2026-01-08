import requests
import json
import time
from typing import Generator, List, Dict, Any
from core.protocol.request import LLMRequest, Message
from core.protocol.response import LLMResponse
from core.protocol.event import LLMEvent
from llm.base import BaseLLM

class OllamaLLM(BaseLLM):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.url = f"{self.base_url}/api/chat"

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        converted = []
        for m in messages:
            msg = {"role": m.role, "content": m.content}
            if m.images:
                msg["images"] = m.images
            converted.append(msg)
        return converted

    def call(self, req: LLMRequest) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": self._convert_messages(req.messages),
            "stream": False,
            "options": {
                "temperature": req.temperature,
            }
        }
        
        if req.max_tokens:
            payload["options"]["num_predict"] = req.max_tokens

        resp = requests.post(self.url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        
        usage = {
            "prompt_eval_count": data.get("prompt_eval_count", 0),
            "eval_count": data.get("eval_count", 0)
        }

        return LLMResponse(
            text=data.get("message", {}).get("content", ""),
            usage=usage,
            raw=data
        )

    def stream(self, req: LLMRequest) -> Generator[LLMEvent, None, None]:
        payload = {
            "model": self.model,
            "messages": self._convert_messages(req.messages),
            "stream": True,
            "options": {
                "temperature": req.temperature,
            }
        }

        if req.max_tokens:
            payload["options"]["num_predict"] = req.max_tokens
        
        resp = requests.post(self.url, json=payload, stream=True, timeout=300)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line.decode("utf-8"))
                
                if "message" in data and "content" in data["message"]:
                    content = data["message"]["content"]
                    if content:
                        yield LLMEvent(
                            type="output",
                            source=f"llm:{self.name}", # Use self.name as ID
                            text=content,
                            ts=time.time()
                        )
                
                if data.get("done"):
                    yield LLMEvent(
                        type="done",
                        source=f"llm:{self.name}",
                        text="",
                        ts=time.time()
                    )
            except Exception as e:
                yield LLMEvent(
                    type="error",
                    source=f"llm:{self.name}",
                    text=str(e),
                    ts=time.time()
                )
