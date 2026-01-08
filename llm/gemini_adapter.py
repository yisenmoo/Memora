import google.generativeai as genai
import time
from typing import Generator, List
from core.protocol.request import LLMRequest, Message
from core.protocol.response import LLMResponse
from core.protocol.event import LLMEvent
from llm.base import BaseLLM

class GeminiLLM(BaseLLM):
    def __init__(self, api_key: str, model: str):
        genai.configure(api_key=api_key)
        self.model_name = model
        self.model = genai.GenerativeModel(model)

    def _convert_history(self, messages: List[Message]):
        # Gemini format: [{'role': 'user', 'parts': [...]}, ...]
        # System instructions are set on model init or generate_content
        # Here we do a simple conversion. System prompt might need special handling.
        history = []
        system_instruction = None
        
        for m in messages:
            if m.role == "system":
                system_instruction = m.content
            elif m.role == "user":
                history.append({"role": "user", "parts": [m.content]})
            elif m.role == "assistant":
                history.append({"role": "model", "parts": [m.content]})
                
        return history, system_instruction

    def call(self, req: LLMRequest) -> LLMResponse:
        history, sys_inst = self._convert_history(req.messages)
        
        # Simple generation (no chat session for single request, but usually we use chat)
        # If there is history, we might need to use chat session. 
        # But for stateless call, we can just feed the whole history if supported, 
        # or use start_chat.
        
        # For simplicity in this adapter, we assume the last message is the prompt
        # and previous are history.
        
        if not history:
            return LLMResponse(text="Error: No messages provided")

        # Re-instantiate with system instruction if present
        model = genai.GenerativeModel(self.model_name, system_instruction=sys_inst)
        
        chat = model.start_chat(history=history[:-1])
        response = chat.send_message(history[-1]["parts"][0], 
                                     generation_config=genai.types.GenerationConfig(
                                         temperature=req.temperature,
                                         max_output_tokens=req.max_tokens
                                     ))
        
        return LLMResponse(
            text=response.text,
            raw=response.to_dict()
        )

    def stream(self, req: LLMRequest) -> Generator[LLMEvent, None, None]:
        history, sys_inst = self._convert_history(req.messages)
        model = genai.GenerativeModel(self.model_name, system_instruction=sys_inst)
        
        chat = model.start_chat(history=history[:-1])
        response = chat.send_message(history[-1]["parts"][0], 
                                     stream=True,
                                     generation_config=genai.types.GenerationConfig(
                                         temperature=req.temperature,
                                         max_output_tokens=req.max_tokens
                                     ))
        
        for chunk in response:
            if chunk.text:
                yield LLMEvent(
                    type="output",
                    source=f"llm:{self.name}",
                    text=chunk.text,
                    ts=time.time()
                )
        
        yield LLMEvent(type="done", source=f"llm:{self.name}", text="", ts=time.time())
