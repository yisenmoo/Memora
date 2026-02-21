import os
import json
import re
from typing import Dict, Any

_config_cache: Dict[str, Any] = {}

def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    global _config_cache
    if _config_cache:
        return _config_cache

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, config_path)

    if not os.path.exists(full_path):
        print(f"Warning: Config file {full_path} not found.")
        return {}

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Simple env var expansion ${VAR}
        def replace_env(match):
            var_name = match.group(1)
            return os.getenv(var_name, "")
            
        content = re.sub(r'\$\{(\w+)\}', replace_env, content)
        config = json.loads(content)
        _config_cache = config
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def get_web_config() -> Dict[str, Any]:
    config = load_config()
    return config.get("web", {})

def get_planner_config() -> Dict[str, Any]:
    config = load_config()
    return config.get("planner", {})

def get_llm_config() -> Dict[str, Any]:
    config = load_config()
    return config.get("llms", {})
