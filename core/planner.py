from llm.router import get_llm
from core.protocol.request import LLMRequest, Message

def plan(user_input: str, model: str = "llama3") -> str:
    """
    Planner 负责规划任务步骤，必须明确输出 JSON 格式的 Action。
    """
    llm = get_llm(model)

    messages = [
        Message(role="system", content="""
你是一个 Agent 系统中的【任务规划模块 Planner】。

你的职责：
1. 理解用户的目标
2. 决定下一步该做什么（使用工具 或 结束任务）
3. 必须输出严格的 JSON 格式，不要包含多余的废话。

可用工具：
- shell: 执行本地命令行 (args: command)
- file: 读取或写入文件 (args: operation="read"|"write", path="...", content="...")
  - 支持格式: txt, md, json, csv, xlsx, docx, pptx, jpg/png(只读信息)
  - 示例: {"type": "use_tool", "tool": "file", "args": {"operation": "read", "path": "data.xlsx"}}

输出格式要求（请严格遵守）：

情况 1：需要使用工具
```json
{
  "type": "use_tool",
  "tool": "shell",
  "args": {
    "command": "ls -la"
  },
  "reason": "查看当前目录文件"
}
```

情况 2：任务完成，可以回答用户
```json
{
  "type": "final",
  "content": "这里写给用户的最终回答，总结你看到的信息。"
}
```

注意：
- 每次只输出一个 JSON 块。
- 不要一次性规划多步，只输出当前这一步。
- 观察结果会由系统在下一步提供给你。
        """),
        Message(role="user", content=user_input)
    ]

    # Check if stream is allowed by config
    if llm.stream_allowed:
        req = LLMRequest(messages=messages, stream=True)
        full_text = ""
        for event in llm.stream(req):
            if event.type == "output":
                print(event.text, end="", flush=True)
                full_text += event.text
            elif event.type == "error":
                print(f"\nError: {event.text}")
        print() # Newline after stream
        return full_text
    else:
        req = LLMRequest(messages=messages, stream=False)
        resp = llm.call(req)
        print(resp.text) # Print result at once to simulate output
        return resp.text
