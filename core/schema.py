from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

class PlannerMode(str, Enum):
    SEARCH = "SEARCH"
    REASON = "REASON"
    SPECULATE = "SPECULATE"

@dataclass
class PlannerDecision:
    mode: PlannerMode
    thought: str
    target_entity: Optional[str] = None # Required for SEARCH
    action: Optional[Dict[str, Any]] = None # The actual action (use_tool, task_list, final)

@dataclass
class ExecutionTraceItem:
    step_id: int
    planner_mode: PlannerMode
    target_entity: Optional[str]
    action_type: str
    result_status: str = "pending" # success, failure, denied
    timestamp: float = 0.0
