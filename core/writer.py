from typing import List, Any
from llm.router import get_llm
from core.protocol.request import LLMRequest, Message
from core.trace.event import TraceEvent, EventType

def write_answer(user_question: str, context: str, model: str = "llama3", trace_events: List[TraceEvent] = None) -> str:
    """
    Writer 负责生成最终回答，只负责输出，不负责决策。
    必须执行【证据一致性校验】。
    """
    llm = get_llm(model)
    
    # Evidence Consistency Check
    has_web_search = False
    has_web_fetch = False
    
    if trace_events:
        for event in trace_events:
            if event.type == EventType.TOOL_CALL:
                tool_name = event.data.get("tool", "")
                if tool_name == "web.search":
                    has_web_search = True
                elif tool_name == "web.fetch":
                    has_web_fetch = True
    
    evidence_warning = ""
    if not has_web_search and not has_web_fetch:
        evidence_warning = """
[重要警告 - 证据一致性校验]
本轮执行中【没有调用任何联网工具】(web.search/web.fetch)。
因此，你被【严格禁止】使用以下表述：
❌ "经过核查"、"查阅资料后"、"无权威记录"、"GitHub/官网未发现"、"搜索结果显示"
❌ 引用具体的 "搜索结果" 或 "网页内容"

你【必须】明确说明：
✅ "基于模型已有知识推测"、"我目前的知识库中暂时没有..."
✅ "由于未进行联网查询..."

如果 context 中包含了 "Downgrade" 或 "Fallback" 的标记，请务必遵守。
"""

    messages = [
        Message(role="system", content=f"""
你是一个 Agent 系统中的【结果生成模块 Writer】。

你将收到：
- 用户的原始问题
- 已经执行完成的任务列表及其结果 (Task List & Results)

你的职责：
1. 仔细阅读所有任务的执行结果。
2. 综合这些信息，回答用户的原始问题。
3. 生成清晰、结构化、可直接交付给用户的结果。
4. 必须基于事实说话，不要编造。

{evidence_warning}

你的输出将直接展示给用户。
        """),
        Message(role="user", content=f"""
用户问题：
{user_question}

任务执行结果汇总：
{context}

请给出清晰、简洁、结构化的总结回答。
""")
    ]

    if llm.stream_allowed:
        req = LLMRequest(messages=messages, stream=True)
        full_text = ""
        for event in llm.stream(req):
            if event.type == "output":
                print(event.text, end="", flush=True)
                full_text += event.text
            elif event.type == "error":
                print(f"\nError: {event.text}")
        print()
        return full_text
    else:
        req = LLMRequest(messages=messages, stream=False)
        resp = llm.call(req)
        print(resp.text)
        return resp.text
