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
    支持 Task List 模式。
    """
    context = "" # 纯文本上下文，记录交互历史
    max_turns = 10 # 防止单任务死循环
    
    print(f"\n[Orchestrator] Start handling: {user_input}")

    # --- Phase 1: Initial Planning ---
    print(f"[Orchestrator] Initial Planning...")
    # 第一次调用 Planner，可能会返回 task_list 或 use_tool
    plan_text = plan(user_input, model=model)
    action = parse_action(plan_text)
    
    if not action:
        return "Failed to parse initial plan."

    # --- Phase 2: Execution Mode Selection ---
    
    # 模式 A: 多任务模式 (Task List)
    if action.get("type") == "task_list":
        tasks = action.get("tasks", [])
        print(f"\n[Orchestrator] Detected Task List with {len(tasks)} tasks.")
        
        task_results = []
        
        for i, task_desc in enumerate(tasks):
            print(f"\n>>> Executing Task {i+1}/{len(tasks)}: {task_desc}")
            
            # 对每个子任务，启动一个迷你的 ReAct 循环 (run_single_task)
            # 我们复用单步执行的逻辑，但需要一个新的 Context 吗？
            # 最好是累积 Context，这样后面的任务知道前面的结果。
            
            task_result = run_single_task(task_desc, model, context)
            
            # 记录结果
            task_results.append(f"Task: {task_desc}\nResult: {task_result}")
            context += f"\n[Completed Task: {task_desc}]\n[Result: {task_result}]\n"
            
        # 所有任务完成，调用 Writer 汇总
        print("\n[Orchestrator] All tasks completed. Generating summary...")
        summary_context = "\n\n".join(task_results)
        return write_answer(user_input, summary_context, model=model)

    # 模式 B: 单任务模式 (ReAct Loop)
    else:
        # 如果第一次就是 use_tool 或 final，进入常规循环
        # 把第一次的结果作为初始状态
        return run_react_loop(user_input, model, context, initial_action=action)

def run_single_task(task_desc: str, model: str, global_context: str) -> str:
    """
    执行单个子任务。这其实就是一个 ReAct 循环，
    但它的目标是完成 task_desc，而不是回答 user_input。
    """
    # 构造针对子任务的输入
    # 我们把 global_context 作为背景信息传入
    task_input = f"当前子任务: {task_desc}\n\n背景信息(已完成的任务):\n{global_context}"
    return run_react_loop(task_input, model, context="", max_turns=5) # 子任务步数限制少一点

def run_react_loop(user_input: str, model: str, context: str, initial_action=None, max_turns=10):
    """
    标准的 ReAct 循环：Planner -> Action -> Tool -> Observation
    """
    current_action = initial_action
    
    for turn in range(max_turns):
        # 如果没有初始 Action (或后续轮次)，则调用 Planner
        if not current_action:
            planner_input = f"目标: {user_input}\n\n当前执行进度:\n{context}" if context else user_input
            print(f"[Loop] Thinking...")
            plan_text = plan(planner_input, model=model)
            current_action = parse_action(plan_text)
        
        if not current_action:
            return "Failed to parse action in loop."
            
        action_type = current_action.get("type")
        
        # Dispatch
        if action_type == "use_tool":
            tool_name = current_action.get("tool")
            args = current_action.get("args", {})
            reason = current_action.get("reason", "")
            
            tool = get_tool(tool_name)
            if tool:
                print(f"[Loop] Tool '{tool_name}' args: {args}")
                try:
                    result = tool.run(**args)
                    observation = f"Tool Output:\n{result}"
                except Exception as e:
                    observation = f"Tool Error: {e}"
            else:
                observation = f"Error: Tool '{tool_name}' not found."
            
            # Record & Continue
            step_record = f"Thought: {reason}\nAction: {tool_name}({json.dumps(args)})\nObservation: {observation}"
            context += "\n" + step_record
            current_action = None # Reset for next turn
            continue

        elif action_type == "final":
            return current_action.get("content", "")
            
        elif action_type == "task_list":
            # 嵌套 Task List？暂不支持递归拆解，直接报错或当作普通文本
            return "Error: Nested task lists are not supported yet."
            
        else:
            return f"Unknown action: {action_type}"

    return "Task loop limit reached."
