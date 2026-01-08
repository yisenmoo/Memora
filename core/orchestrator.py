import json
from core.planner import plan
from core.writer import write_answer
from tools.registry import get_tool, register
from tools.shell import ShellTool
from tools.file import FileTool
from core.parser import parse_action

# 注册默认工具
register(ShellTool())
register(FileTool())

def orchestrate(user_input: str, model: str = "llama3"):
    """
    Orchestrator: Agent 的唯一控制器。
    负责 Planner -> Tool -> Observation -> Planner 的循环。
    """
    context = "" # 纯文本上下文，记录交互历史
    max_turns = 10 # 防止死循环
    
    print(f"\n[Orchestrator] Start handling: {user_input}")

    for turn in range(max_turns):
        print(f"\n=== Turn {turn + 1} ===")
        
        # 1. 构造输入给 Planner
        # 如果是第一轮，context 为空
        # 如果是后续轮次，context 包含之前的 Action 和 Observation
        planner_input = f"用户目标: {user_input}\n\n当前上下文:\n{context}" if context else user_input
        
        print(f"[Orchestrator] Calling Planner...")
        # Planner 输出原始文本 (可能是 JSON)
        plan_text = plan(planner_input, model=model)
        
        # 2. 解析 Action
        action = parse_action(plan_text)
        
        if not action:
            print("[Orchestrator] Failed to parse action. Aborting.")
            break
            
        action_type = action.get("type")
        print(f"[Orchestrator] Action Type: {action_type}")

        # 3. 分发 Action (Dispatch)
        if action_type == "use_tool":
            tool_name = action.get("tool")
            args = action.get("args", {})
            reason = action.get("reason", "No reason provided")
            
            # 获取工具
            tool = get_tool(tool_name)
            if not tool:
                observation = f"Error: Tool '{tool_name}' not found."
            else:
                print(f"[Orchestrator] Running Tool '{tool_name}' with args: {args}")
                try:
                    # 执行工具
                    result = tool.run(**args)
                    observation = f"Tool Output:\n{result}"
                except Exception as e:
                    observation = f"Tool Execution Error: {str(e)}"
            
            # 4. 回灌 Observation (核心)
            # 记录这一轮的思考、行动和结果
            step_record = f"""
Step {turn + 1}:
Thought: {reason}
Action: use_tool({tool_name}, {json.dumps(args)})
Observation:
{observation}
"""
            context += "\n" + step_record
            print(f"[Orchestrator] Observation collected.")
            continue # 进入下一轮循环

        elif action_type == "final":
            # 5. 最终输出
            content = action.get("content", "")
            print("[Orchestrator] Final answer received.")
            
            # 这里的 content 已经是 Planner 总结好的回答了
            # 但为了严谨符合架构 (Planner -> Action -> Writer)，我们可以让 Writer 再润色一次
            # 如果 content 很短或者需要格式化，Writer 很有用。
            # 这里我们直接调用 Writer。
            
            return write_answer(user_input, context + "\n" + content, model=model)

        else:
            print(f"[Orchestrator] Unknown action type: {action_type}")
            break

    return "Task ended (max turns reached)."
