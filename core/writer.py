from llm.router import get_llm
from core.protocol.request import LLMRequest, Message

def write_answer(user_question: str, context: str, model: str = "llama3") -> str:
    """
    Writer 负责生成最终回答，只负责输出，不负责决策。
    """
    llm = get_llm(model)

    messages = [
        Message(role="system", content="""
你是一个 Agent 系统中的【结果生成模块 Writer】。

你将收到：
- 用户的原始问题
- 已经执行完成的任务列表及其结果 (Task List & Results)

你的职责：
1. 仔细阅读所有任务的执行结果。
2. 综合这些信息，回答用户的原始问题。
3. 生成清晰、结构化、可直接交付给用户的结果。
4. 必须基于事实说话，不要编造。

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
