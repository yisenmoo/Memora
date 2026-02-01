import json
import time
import uuid
from typing import List, Optional, Dict, Any

from core.state import AgentState
from core.task import Task
from core.planner import plan
from core.writer import write_answer
from tools.registry import get_tool, register
from tools.shell import ShellTool
from tools.file import FileTool
from tools.web import WebSearchTool, WebFetchTool
from core.parser import parse_action
from core.trace.collector import TraceCollector
from core.trace.event import EventType
from core.memory.checkpoint import Checkpoint
from core.memory.store import FileMemoryStore, MemoryStore
from core.schema import PlannerMode

# Register default tools
register(ShellTool())
register(FileTool())
register(WebSearchTool())
register(WebFetchTool())

class Orchestrator:
    def __init__(self, user_input: str, model: str = "llama3", agent_id: Optional[str] = None):
        self.user_input = user_input
        self.model = model
        self.state = AgentState.IDLE
        
        # Agent Identity
        self.agent_id = agent_id or str(uuid.uuid4())
        
        # Memory Store
        self.memory_store = FileMemoryStore()
        
        self.tasks: List[Task] = []
        self.current_task_index = 0
        
        # Context
        self.global_context = "" # Results of completed tasks
        self.execution_history = [] # Full trace
        
        # Current Turn Data
        self.current_action: Optional[Dict[str, Any]] = None
        self.current_observation: Optional[str] = None
        self.final_answer: str = ""
        
        # Trace System
        self.trace = TraceCollector()
        
        # Tool usage tracking
        self.tool_usage_count: Dict[str, int] = {}
        self.tool_type_usage_count: Dict[str, int] = {} # Global limit per tool type
        
        # Entity Search Tracking (Entity -> Count)
        self.entity_search_count: Dict[str, int] = {}

    def _save_checkpoint(self):
        """Save current state to MemoryStore"""
        checkpoint = Checkpoint(
            agent_id=self.agent_id,
            state=self.state.value,
            tasks=[t.to_dict() for t in self.tasks],
            current_task_index=self.current_task_index,
            global_context=self.global_context,
            execution_history=self.execution_history,
            trace_events=[e.to_dict() for e in self.trace.get_events()],
            current_action=self.current_action,
            current_observation=self.current_observation,
            final_answer=self.final_answer
        )
        self.memory_store.save_checkpoint(checkpoint)
        # print(f"[System] Checkpoint saved for Agent {self.agent_id}")

    @classmethod
    def load_from_checkpoint(cls, agent_id: str, model: str = "llama3") -> Optional['Orchestrator']:
        """Factory method to restore an Orchestrator from a checkpoint"""
        store = FileMemoryStore()
        checkpoint = store.load_latest_checkpoint(agent_id)
        if not checkpoint:
            return None
            
        instance = cls(user_input="[RESUMED SESSION]", model=model, agent_id=agent_id)
        
        # Restore State
        try:
            instance.state = AgentState(checkpoint.state)
        except ValueError:
            instance.state = AgentState.IDLE # Fallback
            
        instance.tasks = [Task.from_dict(t) for t in checkpoint.tasks]
        instance.current_task_index = checkpoint.current_task_index
        instance.global_context = checkpoint.global_context
        instance.execution_history = checkpoint.execution_history
        instance.current_action = checkpoint.current_action
        instance.current_observation = checkpoint.current_observation
        instance.final_answer = checkpoint.final_answer
        
        # Restore Trace
        from core.trace.event import TraceEvent
        for evt_data in checkpoint.trace_events:
            evt = TraceEvent(
                type=evt_data["type"],
                data=evt_data["data"],
                id=evt_data["id"],
                timestamp=evt_data["timestamp"]
            )
            instance.trace.events.append(evt)
        
        return instance

    def _transition_to(self, new_state: AgentState):
        """Helper to manage state transitions and emit events"""
        old_state = self.state
        self.state = new_state
        self.trace.emit(EventType.STATE_CHANGE, {
            "from": old_state.value,
            "to": new_state.value
        })
        # Checkpoint on state change
        self._save_checkpoint()

    def start(self) -> str:
        """Main loop of the State Machine"""
        
        if self.state == AgentState.IDLE:
            self._transition_to(AgentState.PLANNING)
        else:
            print(f"[Orchestrator] Resuming from state: {self.state.value}")
        
        max_steps = 50 
        step_count = 0
        
        while self.state not in [AgentState.DONE, AgentState.ERROR]:
            step_count += 1
            if step_count > max_steps:
                self._transition_to(AgentState.ERROR)
                self.final_answer = "Max steps reached. Aborting."
                self.trace.emit(EventType.ERROR, {"error": "Max steps reached"})
                break

            try:
                if self.state == AgentState.PLANNING:
                    self._handle_planning()
                elif self.state == AgentState.TASK_READY:
                    self._handle_task_ready()
                elif self.state == AgentState.TASK_RUNNING:
                    self._handle_task_running()
                elif self.state == AgentState.TOOL_CALLING:
                    self._handle_tool_calling()
                elif self.state == AgentState.OBSERVING:
                    self._handle_observing()
                elif self.state == AgentState.WRITING:
                    self._handle_writing()
                    
            except KeyboardInterrupt:
                print("\n[System] Interrupted by user. Saving checkpoint...")
                self._save_checkpoint()
                return "Interrupted by user."
            except Exception as e:
                print(f"[Error] Exception in state {self.state}: {e}")
                import traceback
                traceback.print_exc()
                self.trace.emit(EventType.ERROR, {"error": str(e), "state": self.state.value})
                self._transition_to(AgentState.ERROR)
                self.final_answer = f"System Error: {str(e)}"

        if self.state == AgentState.ERROR:
            return f"Execution Failed: {self.final_answer}"
        
        if self.state == AgentState.DONE:
             self.memory_store.clear_checkpoint(self.agent_id)
            
        return self.final_answer

    def _get_current_task(self) -> Optional[Task]:
        if 0 <= self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None

    def _handle_planning(self):
        """Call Planner to decide next step."""
        current_task = self._get_current_task()
        
        if current_task:
            prompt = self._construct_task_prompt(current_task)
        else:
            prompt = self.user_input
            if self.global_context:
                prompt += f"\n\n[Context from previous actions]:\n{self.global_context}"

        self.trace.emit(EventType.PLANNER_CALL, {
            "state": self.state.value,
            "task_id": current_task.id if current_task else None,
            "prompt_preview": prompt[:100]
        })

        # Inject limits into prompt
        web_search_count = self.tool_type_usage_count.get("web.search", 0)
        if web_search_count >= 1:
            prompt += f"\n[System Limit] web.search usage: {web_search_count}/2. Warning: Quota is tight."
        if web_search_count >= 2:
            prompt += f"\n[System Limit] web.search usage: {web_search_count}/2. Quota EXHAUSTED. Do NOT call web.search again."
        
        # Inject Entity Search History
        if self.entity_search_count:
            history_str = ", ".join([f"{k}({v})" for k, v in self.entity_search_count.items()])
            prompt += f"\n[Search History] Entities already searched: {history_str}"

        plan_text = plan(prompt, model=self.model)
        action = parse_action(plan_text)
        
        self.trace.emit(EventType.PLANNER_OUTPUT, {
            "raw_text": plan_text,
            "action": action
        })
        
        if not action:
            self.trace.emit(EventType.ERROR, {"error": "Planner returned invalid format"})
            self._transition_to(AgentState.ERROR)
            self.final_answer = "Planner returned invalid format."
            return

        self.current_action = action
        
        # --- NEW: Execution Referee Logic ---
        planner_mode = action.get("mode", "REASON") # Default to REASON if missing (compatibility)
        target_entity = action.get("target_entity")
        action_payload = action.get("action", {})
        action_type = action_payload.get("type")
        
        # 1. SEARCH Mode Guard
        if planner_mode == PlannerMode.SEARCH:
            if not target_entity:
                self.current_observation = "System Error: SEARCH mode requires a 'target_entity'. Please fix your plan."
                self._transition_to(AgentState.OBSERVING)
                return
                
            entity_count = self.entity_search_count.get(target_entity, 0)
            if entity_count >= 1:
                self.current_observation = f"System Guard: Entity '{target_entity}' has already been searched. You MUST switch to REASON or SPECULATE mode."
                self._transition_to(AgentState.OBSERVING)
                return
            
            # Allow search, but verify it's a tool call
            if action_type != "use_tool":
                self.current_observation = "System Error: SEARCH mode expects 'use_tool' action."
                self._transition_to(AgentState.OBSERVING)
                return
                
            # Valid Search -> Increment Counter
            self.entity_search_count[target_entity] = entity_count + 1
            
            # Flatten action for legacy handler
            self.current_action = action_payload 
            self._transition_to(AgentState.TOOL_CALLING)

        # 2. REASON Mode Guard
        elif planner_mode == PlannerMode.REASON:
            if action_type == "use_tool" and action_payload.get("tool") == "web.search":
                 self.current_observation = "System Guard: REASON mode prohibits 'web.search'. Use SEARCH mode for external queries."
                 self._transition_to(AgentState.OBSERVING)
                 return
            
            # Proceed with action
            self.current_action = action_payload
            if action_type == "task_list":
                if current_task:
                    self.trace.emit(EventType.ERROR, {"error": "Nested task list not supported"})
                    self._transition_to(AgentState.ERROR)
                else:
                    self._transition_to(AgentState.TASK_READY)
            elif action_type == "final":
                 self._handle_final_action(current_task, action_payload)
            elif action_type == "use_tool":
                 # Internal tools (file, shell) are allowed in REASON? 
                 # User said "REASON: No new facts". File read introduces facts. 
                 # But let's assume REASON allows non-search tools for now, or strictly internal.
                 # User spec: "REASON... Only use memory / search results". 
                 # So File Read might be borderline. Let's allow it but maybe warn?
                 # For now, we treat REASON as "Non-Search".
                 self._transition_to(AgentState.TOOL_CALLING)
            else:
                 # Just thought? If no action, maybe observing?
                 # If only thought, we can loop back or finish?
                 # The schema requires 'action'.
                 pass

        # 3. SPECULATE Mode Guard
        elif planner_mode == PlannerMode.SPECULATE:
            if action_type == "use_tool":
                self.current_observation = "System Guard: SPECULATE mode prohibits tool usage. You must provide a final answer with uncertainty."
                self._transition_to(AgentState.OBSERVING)
                return
            
            if action_type == "final":
                # Ensure content contains uncertainty markers? (Hard to regex check reliably, trust prompt for now)
                self.current_action = action_payload
                self._handle_final_action(current_task, action_payload)
            else:
                 self.current_observation = "System Guard: SPECULATE mode expects 'final' action."
                 self._transition_to(AgentState.OBSERVING)

        else:
            # Legacy Fallback or Invalid Mode
            self.current_action = action_payload if "action" in action else action
            # Try to dispatch based on type
            act_type = self.current_action.get("type")
            if act_type == "use_tool":
                self._transition_to(AgentState.TOOL_CALLING)
            elif act_type == "task_list":
                 self._transition_to(AgentState.TASK_READY)
            elif act_type == "final":
                 self._handle_final_action(current_task, self.current_action)
            else:
                 self.trace.emit(EventType.ERROR, {"error": f"Unknown action type: {act_type}"})
                 self._transition_to(AgentState.ERROR)

    def _handle_final_action(self, current_task, action_payload):
        if current_task:
            result = action_payload.get("content", "")
            current_task.mark_completed(result)
            self.global_context += f"\n[Task {current_task.id} Result]: {result}\n"
            self.trace.emit(EventType.TASK_END, {"task_id": current_task.id, "result": result})
            self._save_checkpoint()
            self.current_task_index += 1
            self._transition_to(AgentState.TASK_RUNNING)
        else:
            self.final_answer = action_payload.get("content", "")
            self._transition_to(AgentState.WRITING)

    def _handle_task_ready(self):
        raw_tasks = self.current_action.get("tasks", [])
        for i, t in enumerate(raw_tasks):
            if isinstance(t, dict):
                goal = t.get("goal") or t.get("description") or str(t)
                tid = t.get("id", f"task_{i+1}")
            else:
                goal = str(t)
                tid = f"task_{i+1}"
            self.tasks.append(Task(tid, goal))
        self.current_task_index = 0
        self._transition_to(AgentState.TASK_RUNNING)

    def _handle_task_running(self):
        task = self._get_current_task()
        if task:
            task.mark_running()
            self.trace.emit(EventType.TASK_START, {"task_id": task.id, "goal": task.goal})
            self._save_checkpoint()
            self.current_observation = None 
            self._transition_to(AgentState.PLANNING)
        else:
            self._transition_to(AgentState.WRITING)

    def _handle_tool_calling(self):
        tool_name = self.current_action.get("tool")
        args = self.current_action.get("args", {})
        reason = self.current_action.get("reason", "")
        
        # Track tool usage
        sig = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        self.tool_usage_count[sig] = self.tool_usage_count.get(sig, 0) + 1
        self.tool_type_usage_count[tool_name] = self.tool_type_usage_count.get(tool_name, 0) + 1
        
        self.trace.emit(EventType.TOOL_CALL, {"tool": tool_name, "args": args, "reason": reason})
        
        tool = get_tool(tool_name)
        if not tool:
            self.current_observation = f"Error: Tool '{tool_name}' not found."
            self.trace.emit(EventType.ERROR, {"error": f"Tool {tool_name} not found"})
        else:
            try:
                result = tool.run(**args)
                self.current_observation = f"Tool Output:\n{result}"
                self.trace.emit(EventType.TOOL_RESULT, {"tool": tool_name, "result": str(result)})
                self._save_checkpoint()
            except Exception as e:
                self.current_observation = f"Error executing tool: {e}"
                self.trace.emit(EventType.ERROR, {"error": f"Tool execution failed: {e}"})
                
        self._transition_to(AgentState.OBSERVING)
        
        record = f"Thought: {reason}\nAction: {tool_name}({args})\nObservation: {self.current_observation}"
        current_task = self._get_current_task()
        if current_task:
            current_task.add_history(record)
        else:
            self.execution_history.append(record)

    def _handle_observing(self):
        self._transition_to(AgentState.PLANNING)

    def _handle_writing(self):
        self.trace.emit(EventType.WRITER_CALL, {})
        if self.tasks:
            task_summaries = []
            for t in self.tasks:
                task_summaries.append(f"Task: {t.goal}\nStatus: {t.status}\nResult: {t.result}")
            context = "\n\n".join(task_summaries)
        else:
            context = self.final_answer or "\n".join(self.execution_history)

        trace_events = self.trace.get_events()
        final_output = write_answer(self.user_input, context, model=self.model, trace_events=trace_events)
        self.trace.emit(EventType.WRITER_OUTPUT, {"content": final_output})
        self.final_answer = final_output
        self._transition_to(AgentState.DONE)

    def _construct_task_prompt(self, task: Task) -> str:
        prompt = f"Target Task: {task.goal}\n"
        if self.global_context:
            prompt += f"\n[Background - Completed Tasks Results]:\n{self.global_context}\n"
        history = task.get_context()
        if history:
            prompt += f"\n[Current Execution History]:\n{history}\n"
        if self.current_observation:
             prompt += f"\n[Latest Observation]:\n{self.current_observation}\n"
        return prompt

def orchestrate(user_input: str, model: str = "llama3", agent_id: str = None) -> str:
    store = FileMemoryStore()
    if agent_id and store.has_checkpoint(agent_id):
        print(f"[System] Found checkpoint for Agent {agent_id}. Resuming...")
        orchestrator = Orchestrator.load_from_checkpoint(agent_id, model=model)
    else:
        orchestrator = Orchestrator(user_input, model, agent_id)
    return orchestrator.start()
