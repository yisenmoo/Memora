from typing import Dict, Any

class BaseTool:
    name: str
    description: str
    args_schema: Dict[str, str]

    def run(self, **kwargs) -> str:
        raise NotImplementedError
