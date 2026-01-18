from enum import Enum

class AgentState(Enum):
    IDLE = "IDLE"            # Waiting for user input
    PLANNING = "PLANNING"    # Calling Planner for decision
    TASK_READY = "TASK_READY" # Task list acquired
    TASK_RUNNING = "TASK_RUNNING" # Executing a single task
    TOOL_CALLING = "TOOL_CALLING" # Executing a tool
    OBSERVING = "OBSERVING"  # Receiving tool execution result
    WRITING = "WRITING"      # Calling Writer for output
    DONE = "DONE"            # Task completed
    ERROR = "ERROR"          # Exception state
