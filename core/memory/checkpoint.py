import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from core.task import Task

@dataclass
class Checkpoint:
    agent_id: str
    state: str
    timestamp: float = field(default_factory=time.time)
    
    # Task Context
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    current_task_index: int = 0
    
    # Execution Context
    global_context: str = ""
    execution_history: List[str] = field(default_factory=list)
    
    # Trace info
    trace_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # Additional state
    current_action: Optional[Dict[str, Any]] = None
    current_observation: Optional[str] = None
    final_answer: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "state": self.state,
            "timestamp": self.timestamp,
            "tasks": self.tasks,
            "current_task_index": self.current_task_index,
            "global_context": self.global_context,
            "execution_history": self.execution_history,
            "trace_events": self.trace_events,
            "current_action": self.current_action,
            "current_observation": self.current_observation,
            "final_answer": self.final_answer
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        return cls(
            agent_id=data["agent_id"],
            state=data["state"],
            timestamp=data.get("timestamp", time.time()),
            tasks=data.get("tasks", []),
            current_task_index=data.get("current_task_index", 0),
            global_context=data.get("global_context", ""),
            execution_history=data.get("execution_history", []),
            trace_events=data.get("trace_events", []),
            current_action=data.get("current_action"),
            current_observation=data.get("current_observation"),
            final_answer=data.get("final_answer", "")
        )
