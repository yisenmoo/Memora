from typing import List, Optional
from dataclasses import dataclass, field

@dataclass
class Message:
    role: str        # system | user | assistant | tool
    content: str
    images: Optional[List[str]] = None # Base64 encoded images

@dataclass
class LLMRequest:
    """
    Canonical LLM Request
    所有模型请求都必须先转换为该结构
    """
    messages: List[Message]

    # generation controls
    stream: bool = False
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    # extensibility
    metadata: Optional[dict] = None
