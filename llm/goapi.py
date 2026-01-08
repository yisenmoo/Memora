import requests
import json
import time
from typing import Generator, List, Dict
from core.protocol.request import LLMRequest, Message
from core.protocol.response import LLMResponse
from core.protocol.event import LLMEvent
from llm.base import BaseLLM

class GoAPILLM(BaseLLM):
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.url = f"{self.base_url}/v1/chat/completions"

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def call(self, req: LLMRequest) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": self._convert_messages(req.messages),
            "stream": False,
            "temperature": req.temperature,
        }
        if req.max_tokens:
            payload["max_tokens"] = req.max_tokens

        resp = requests.post(self.url, headers=self._get_headers(), json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        
        text = ""
        if "choices" in data and len(data["choices"]) > 0:
            text = data["choices"][0].get("message", {}).get("content", "")

        return LLMResponse(
            text=text,
            raw=data,
            usage=data.get("usage")
        )

    def stream(self, req: LLMRequest) -> Generator[LLMEvent, None, None]:
        payload = {
            "model": self.model,
            "messages": self._convert_messages(req.messages),
            "stream": True,
            "temperature": req.temperature,
        }
        if req.max_tokens:
            payload["max_tokens"] = req.max_tokens

        resp = requests.post(self.url, headers=self._get_headers(), json=payload, stream=True, timeout=300)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            
            decoded = line.decode("utf-8")
            if decoded.startswith("data:"):
                decoded = decoded[len("data:"):].strip()
            
            if decoded == "[DONE]":
                yield LLMEvent(
                    type="done", 
                    source=f"llm:{self.name}", 
                    text="", 
                    ts=time.time()
                )
                break
                
            try:
                chunk = json.loads(decoded)
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                
                if delta:
                    yield LLMEvent(
                        type="output",
                        source=f"llm:{self.name}",
                        text=delta,
                        ts=time.time()
                    )
            except Exception as e:
                # Some chunks might be keep-alive or errors
                pass
