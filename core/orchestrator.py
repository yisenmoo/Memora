import json
import time
import uuid
from typing import List, Optional, Dict, Any

from core.state import AgentState
from core.task import Task
from core.planner import plan
from core.writer import write_answer
from tools.registry import get_tool
from core.parser import parse_action
from core.trace.collector import TraceCollector
from core.trace.event import EventType
from core.memory.checkpoint import Checkpoint
from core.memory.store import FileMemoryStore, MemoryStore

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
            
        # Initialize basic instance
        # Note: We might need to guess user_input or store it in checkpoint. 
        # For now, let's assume user_input is implicitly part of the context or we add it to Checkpoint.
        # But wait, Checkpoint doesn't have user_input field in previous definition.
        # Let's assume we can proceed without it or we should add it.
        # Adding it to Checkpoint definition is better, but for now let's pass a placeholder
        # or try to recover it from the first event?
        # Actually, for resuming, we continue from where we left off.
        
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
        # We need to manually repopulate trace collector
        from core.trace.event import TraceEvent
        for evt_data in checkpoint.trace_events:
            # We construct TraceEvent objects. 
            # Note: evt_data has keys like 'type', 'data', 'timestamp', 'id'
            evt = TraceEvent(
                type=evt_data["type"],
                data=evt_data["data"],
                id=evt_data["id"],
                timestamp=evt_data["timestamp"]
            )
            instance.trace.events.append(evt)
            # We don't re-emit to listeners to avoid duplicate logs on console, 
            # unless we want to show history.
        
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
        
        # If we are just starting (IDLE), move to PLANNING
        if self.state == AgentState.IDLE:
            self._transition_to(AgentState.PLANNING)
        else:
            print(f"[Orchestrator] Resuming from state: {self.state.value}")
        
        max_steps = 50 # Safety break
        step_count = 0
        
        # print(f"\n[Orchestrator] Starting with input: {self.user_input}")

        while self.state not in [AgentState.DONE, AgentState.ERROR]:
            step_count += 1
            if step_count > max_steps:
                self._transition_to(AgentState.ERROR)
                self.final_answer = "Max steps reached. Aborting."
                self.trace.emit(EventType.ERROR, {"error": "Max steps reached"})
                break

            # print(f"\n[State] -> {self.state.value}")
            
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
        
        # Clear checkpoint on success
        if self.state == AgentState.DONE:
             self.memory_store.clear_checkpoint(self.agent_id)
            
        return self.final_answer

    def _get_current_task(self) -> Optional[Task]:
        if 0 <= self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None

    def _handle_planning(self):
        """
        Call Planner to decide next step.
        """
        current_task = self._get_current_task()
        
        if current_task:
            prompt = self._construct_task_prompt(current_task)
            # print(f"[Planner] Planning for Task {current_task.id}...")
        else:
            prompt = self.user_input
            if self.global_context:
                prompt += f"\n\n[Context from previous actions]:\n{self.global_context}"
            # print(f"[Planner] Global Planning...")

        # Trace Call
        self.trace.emit(EventType.PLANNER_CALL, {
            "state": self.state.value,
            "task_id": current_task.id if current_task else None,
            "prompt_preview": prompt[:100]
        })

        # Call Planner
        plan_text = plan(prompt, model=self.model)
        action = parse_action(plan_text)
        
        # Trace Output
        self.trace.emit(EventType.PLANNER_OUTPUT, {
            "raw_text": plan_text,
            "action": action
        })
        
        if not action:
            # print("[Planner] Failed to parse action.")
            self.trace.emit(EventType.ERROR, {"error": "Planner returned invalid format"})
            self._transition_to(AgentState.ERROR)
            self.final_answer = "Planner returned invalid format."
            return

        self.current_action = action
        action_type = action.get("type")
        # print(f"[Planner] Decision: {action_type}")

        # State Transition based on Action
        if action_type == "task_list":
            if current_task:
                # print("[Planner] Warning: Nested task list requested but not supported.")
                self.trace.emit(EventType.ERROR, {"error": "Nested task list not supported"})
                self._transition_to(AgentState.ERROR)
            else:
                self._transition_to(AgentState.TASK_READY)

        elif action_type == "use_tool":
            self._transition_to(AgentState.TOOL_CALLING)

        elif action_type == "final":
            if current_task:
                # Task Completed
                result = action.get("content", "")
                current_task.mark_completed(result)
                # print(f"[Task] {current_task.id} Completed.")
                self.global_context += f"\n[Task {current_task.id} Result]: {result}\n"
                
                # Trace Task End
                self.trace.emit(EventType.TASK_END, {
                    "task_id": current_task.id,
                    "result": result
                })
                
                # Checkpoint on task completion
                self._save_checkpoint()
                
                # Move to next task check
                self.current_task_index += 1
                self._transition_to(AgentState.TASK_RUNNING)
            else:
                # Global execution completed (Direct answer)
                self.final_answer = action.get("content", "")
                self._transition_to(AgentState.WRITING)

        else:
            # print(f"[Planner] Unknown action type: {action_type}")
            self.trace.emit(EventType.ERROR, {"error": f"Unknown action type: {action_type}"})
            self._transition_to(AgentState.ERROR)

    def _handle_task_ready(self):
        """
        Parse task list and initialize tasks.
        """
        raw_tasks = self.current_action.get("tasks", [])
        # print(f"[Task] Initializing {len(raw_tasks)} tasks...")
        
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
        """
        Scheduler state. Picks the next task or finishes.
        """
        task = self._get_current_task()
        if task:
            # print(f"\n>>> Running Task {task.id}: {task.goal}")
            task.mark_running()
            
            # Trace Task Start
            self.trace.emit(EventType.TASK_START, {
                "task_id": task.id,
                "goal": task.goal
            })
            
            # Checkpoint on task start
            self._save_checkpoint()
            
            self.current_observation = None 
            self._transition_to(AgentState.PLANNING)
        else:
            # No more tasks
            # print("[Task] All tasks completed.")
            self._transition_to(AgentState.WRITING)

    def _handle_tool_calling(self):
        """
        Execute the tool.
        """
        tool_name = self.current_action.get("tool")
        args = self.current_action.get("args", {})
        reason = self.current_action.get("reason", "")
        
        # Trace Tool Call
        self.trace.emit(EventType.TOOL_CALL, {
            "tool": tool_name,
            "args": args,
            "reason": reason
        })
        
        # print(f"[Tool] Calling {tool_name} with {args}")
        
        tool = get_tool(tool_name)
        if not tool:
            self.current_observation = f"Error: Tool '{tool_name}' not found."
            self.trace.emit(EventType.ERROR, {"error": f"Tool {tool_name} not found"})
        else:
            try:
                result = tool.run(**args)
                self.current_observation = f"Tool Output:\n{result}"
                
                # Trace Tool Result
                self.trace.emit(EventType.TOOL_RESULT, {
                    "tool": tool_name,
                    "result": str(result)
                })
                
                # Checkpoint on tool result (side effect confirmed)
                self._save_checkpoint()
                
            except Exception as e:
                self.current_observation = f"Error executing tool: {e}"
                self.trace.emit(EventType.ERROR, {"error": f"Tool execution failed: {e}"})
                
        self._transition_to(AgentState.OBSERVING)
        
        # Record history for current task (or global)
        record = f"Thought: {reason}\nAction: {tool_name}({args})\nObservation: {self.current_observation}"
        current_task = self._get_current_task()
        if current_task:
            current_task.add_history(record)
        else:
            self.execution_history.append(record)

    def _handle_observing(self):
        """
        Process observation. 
        """
        # The observation is already stored in self.current_observation
        self._transition_to(AgentState.PLANNING)

    def _handle_writing(self):
        """
        Generate final response using Writer.
        """
        # print("[Writer] Generating final response...")
        self.trace.emit(EventType.WRITER_CALL, {})
        
        # Prepare context for writer
        if self.tasks:
            # Summary of tasks
            task_summaries = []
            for t in self.tasks:
                task_summaries.append(f"Task: {t.goal}\nStatus: {t.status}\nResult: {t.result}")
            context = "\n\n".join(task_summaries)
        else:
            # Direct execution context
            context = self.final_answer or "\n".join(self.execution_history)

        final_output = write_answer(self.user_input, context, model=self.model)
        
        self.trace.emit(EventType.WRITER_OUTPUT, {"content": final_output})
        
        self.final_answer = final_output
        self._transition_to(AgentState.DONE)

    def _construct_task_prompt(self, task: Task) -> str:
        """
        Construct prompt for local task planning.
        """
        prompt = f"Target Task: {task.goal}\n"
        
        # Global context (completed tasks)
        if self.global_context:
            prompt += f"\n[Background - Completed Tasks Results]:\n{self.global_context}\n"
        
        # Current task history
        history = task.get_context()
        if history:
            prompt += f"\n[Current Execution History]:\n{history}\n"
            
        if self.current_observation:
             prompt += f"\n[Latest Observation]:\n{self.current_observation}\n"
             
        return prompt

# Compatibility wrapper
def orchestrate(user_input: str, model: str = "llama3", agent_id: str = None) -> str:
    # Check for existing checkpoint
    store = FileMemoryStore()
    if agent_id and store.has_checkpoint(agent_id):
        print(f"[System] Found checkpoint for Agent {agent_id}. Resuming...")
        orchestrator = Orchestrator.load_from_checkpoint(agent_id, model=model)
    else:
        orchestrator = Orchestrator(user_input, model, agent_id)
        
    return orchestrator.start()
