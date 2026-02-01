from llm.router import get_llm
from core.protocol.request import LLMRequest, Message
from core.config import get_planner_config

def plan(user_input: str, model: str = "llama3") -> str:
    """
    Planner 负责规划任务步骤，必须明确输出 JSON 格式的 Action。
    """
    llm = get_llm(model)
    
    # Load dynamic planner config
    planner_config = get_planner_config()
    web_keywords = planner_config.get("web_keywords", [])
    query_intents = planner_config.get("query_intents", ["查一下", "搜索", "是什么", "是否存在", "帮我看看", "的资料", "的信息", "的能力"])
    
    # Check if we should hint about web search
    web_hint = ""
    if any(k in user_input for k in web_keywords):
        web_hint = "\n[重要提示] 用户问题似乎涉及最新信息或外部状态，请优先考虑使用 web.search 工具获取最新资讯。"
    
    # New strict rule hint for query intents
    query_gate_hint = ""
    if any(intent in user_input for intent in query_intents):
        query_gate_hint = "\n[硬性规则] 检测到用户有明确查询意图。你必须至少调用一次 `web.search` 或其他工具。严禁在未调用任何工具的情况下直接输出 'final' 回答！"

    messages = [
        Message(role="system", content=f"""
你是一个 Agent 系统中的【任务规划模块 Planner】。

【必须遵守的核心架构：认知模式互斥】
你必须明确当前的认知模式 (mode)。在任意时刻，你只能处于以下三种模式之一：

1️⃣ **SEARCH** (探索模式)
   - 职责：获取外部事实 / 数据。
   - 特征：必须有明确的 `target_entity`（目标实体）。
   - 适用：当需要获取未知信息、验证事实时。
   - 输出：调用搜索/获取类工具。

2️⃣ **REASON** (推理模式)
   - 职责：基于已有信息进行逻辑推理或任务拆解。
   - 特征：❌ 不允许引入新事实。只能使用 memory / search results。
   - 适用：当信息充足需要总结、或者需要拆解复杂任务时。
   - 输出：`task_list` 或 内部推理思考。

3️⃣ **SPECULATE** (推测模式)
   - 职责：在信息不足且无法继续搜索时进行假设性推断。
   - 特征：⚠️ 必须显式标注为“推测”。❌ 不得再次触发搜索。
   - 适用：当搜索失败、无结果，但需要给用户一个可能的方向时。
   - 输出：带有不确定性声明的最终回答。

【工具调用限制】
- ⚠️ web.search 最多调用 1 次 (Orchestrator 会强制拦截重复调用)。
- 请仔细检查 [Current Execution History] 和系统提示。
- 如果系统提示配额已满，你 **必须** 切换到 REASON 或 SPECULATE 模式。

【输出格式要求】
你必须输出符合以下 JSON 结构的单一代码块：

模式 A：SEARCH (调用工具)
```json
{{
  "mode": "SEARCH",
  "target_entity": "Memora Project",
  "thought": "用户询问 Memora 项目，我需要搜索其官方信息。",
  "action": {{
    "type": "use_tool",
    "tool": "web.search",
    "args": {{ "query": "Memora Project github documentation" }}
  }}
}}
```

模式 B：REASON (任务拆解)
```json
{{
  "mode": "REASON",
  "thought": "这是一个复杂任务，我需要先搜索文档，然后阅读内容。",
  "action": {{
    "type": "task_list",
    "tasks": ["Search Memora docs", "Fetch content"]
  }}
}}
```

模式 C：REASON / SPECULATE (最终回答)
```json
{{
  "mode": "REASON", 
  "thought": "根据搜索结果，我已经有了足够信息。",
  "action": {{
    "type": "final",
    "content": "Memora 是一个..."
  }}
}}
```
(注意：如果是猜测，请将 mode 设为 "SPECULATE"，并在 content 中明确说明是不确定推测)

{web_hint}
{query_gate_hint}
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
