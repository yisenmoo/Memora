import os
import json
import re
from typing import Dict, Any, List

from llm.base import BaseLLM
from llm.ollama import OllamaLLM
from llm.goapi import GoAPILLM
from llm.openai_adapter import OpenAILLM
from llm.gemini_adapter import GeminiLLM
from llm.dashscope_adapter import DashScopeLLM

# ====== Global Singleton ======
_router = None

class LLMRouter:
    def __init__(self, config_path: str = "config.json"):
        self.models: Dict[str, BaseLLM] = {}
        self.config_path = config_path
        self._load_config()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            print(f"Warning: Config file {self.config_path} not found.")
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Simple env var expansion ${VAR}
        def replace_env(match):
            var_name = match.group(1)
            return os.getenv(var_name, "")
            
        content = re.sub(r'\$\{(\w+)\}', replace_env, content)
        
        try:
            config = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Error parsing config: {e}")
            return

        for llm_id, conf in config.get("llms", {}).items():
            provider = conf.get("provider")
            description = conf.get("description", llm_id)
            stream_allowed = conf.get("stream", True) # Default to True if not specified
            
            llm = None
            
            if provider == "ollama":
                llm = OllamaLLM(
                    base_url=conf.get("base_url", "http://localhost:11434"),
                    model=conf.get("model")
                )
            elif provider == "goapi":
                # GoAPI is essentially OpenAI compatible
                llm = GoAPILLM(
                    base_url=conf.get("base_url", "https://api.getgoapi.com"),
                    api_key=conf.get("api_key", ""),
                    model=conf.get("model")
                )
            elif provider == "openai":
                llm = OpenAILLM(
                    api_key=conf.get("api_key", ""),
                    model=conf.get("model"),
                    base_url=conf.get("base_url") # Optional
                )
            elif provider == "gemini":
                llm = GeminiLLM(
                    api_key=conf.get("api_key", ""),
                    model=conf.get("model")
                )
            elif provider == "dashscope":
                llm = DashScopeLLM(
                    api_key=conf.get("api_key", ""),
                    model=conf.get("model")
                )
            
            if llm:
                llm.name = llm_id
                llm.description = description
                llm.stream_allowed = stream_allowed
                self.models[llm_id] = llm

    def get_llm(self, name: str) -> BaseLLM:
        if name not in self.models:
            raise ValueError(f"Unknown LLM: {name}. Available: {list(self.models.keys())}")
        return self.models[name]

    def list_models(self) -> List[Dict[str, str]]:
        """Return a list of available models with metadata"""
        return [
            {"id": mid, "description": m.description, "model": getattr(m, "model", "")}
            for mid, m in self.models.items()
        ]

def _ensure_router():
    global _router
    if _router is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config.json")
        _router = LLMRouter(config_path)
    return _router

def get_llm(name: str = "llama3") -> BaseLLM:
    router = _ensure_router()
    return router.get_llm(name)

def list_models() -> List[Dict[str, str]]:
    router = _ensure_router()
    return router.list_models()
