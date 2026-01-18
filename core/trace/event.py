import time
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class TraceEvent:
    type: str
    data: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "type": self.type,
            "data": self.data
        }

# Event Types Constants
class EventType:
    STATE_CHANGE = "STATE_CHANGE"
    PLANNER_CALL = "PLANNER_CALL"
    PLANNER_OUTPUT = "PLANNER_OUTPUT"
    TASK_START = "TASK_START"
    TASK_END = "TASK_END"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    WRITER_CALL = "WRITER_CALL"
    WRITER_OUTPUT = "WRITER_OUTPUT"
    ERROR = "ERROR"
