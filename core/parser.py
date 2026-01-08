import json
import re
from typing import Optional, Dict, Any

def parse_action(text: str) -> Optional[Dict[str, Any]]:
    """
    解析 Planner 的输出，提取 Action 结构。
    支持 JSON 块 或 Key-Value 文本格式。
    """
    text = text.strip()
    
    # 1. 尝试解析 JSON 块 ```json ... ```
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 2. 尝试解析纯 JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
        
    # 3. Fallback: 之前的 Key-Value 解析逻辑 (兼容旧格式)
    # Action: use_tool
    # Tool: shell
    # Args: command="ls"
    data = {}
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith("Action:"):
            val = line.split(":", 1)[1].strip().lower()
            # 兼容 finish
            if val == "finish":
                # 如果是 finish，尝试提取 content，或者如果没有 content 字段，就用剩余文本
                return {"type": "final", "content": text} 
            data["type"] = val
        elif line.startswith("Tool:"):
            data["tool"] = line.split(":", 1)[1].strip()
        elif line.startswith("Args:"):
            args_str = line.split(":", 1)[1].strip()
            # 简单提取 command="..."
            match = re.search(r'command=["\'](.*?)["\']', args_str)
            if match:
                data["args"] = {"command": match.group(1)}
            elif "command=" in args_str:
                cmd = args_str.split("command=", 1)[1].strip()
                data["args"] = {"command": cmd}
            # Add file tool support in fallback
            elif "operation=" in args_str:
                # very simple manual parse for file tool args in fallback mode
                # Args: operation="read", path="..."
                args = {}
                parts = args_str.split(",")
                for part in parts:
                    if "=" in part:
                        k, v = part.split("=", 1)
                        args[k.strip()] = v.strip().strip('"').strip("'")
                data["args"] = args

    if "type" in data:
        return data
        
    # 4. 如果以上都失败，但看起来像是自然语言回复，且没有明显的 Action 结构
    # 我们可以假设它是 final answer (容错处理)
    # 但这需要很小心，避免把中间思考当成结果。
    # 只有当它完全不像 JSON 也不像 Key-Value 时。
    if not "Action:" in text and not "```json" in text:
         # 稍微做个判断，防止是胡言乱语
         if len(text) > 0:
             return {"type": "final", "content": text}

    return None
