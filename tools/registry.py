from typing import List, Optional
from tools.base import BaseTool

_registry = {}

def register(tool: BaseTool):
    _registry[tool.name] = tool

def get_tool(name: str) -> Optional[BaseTool]:
    return _registry.get(name)

def list_tools() -> List[BaseTool]:
    return list(_registry.values())
