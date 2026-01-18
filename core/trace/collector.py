import time
import json
from typing import List, Optional, Callable
from core.trace.event import TraceEvent, EventType

class TraceCollector:
    def __init__(self):
        self.events: List[TraceEvent] = []
        self.start_time = time.time()
        self._listeners: List[Callable[[TraceEvent], None]] = []

        # Add default console listener
        self.add_listener(self._default_console_logger)

    def emit(self, event_type: str, data: dict):
        event = TraceEvent(type=event_type, data=data)
        self.events.append(event)
        self._notify_listeners(event)

    def add_listener(self, listener: Callable[[TraceEvent], None]):
        self._listeners.append(listener)

    def _notify_listeners(self, event: TraceEvent):
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                print(f"[TraceCollector] Listener error: {e}")

    def get_events(self) -> List[TraceEvent]:
        return self.events

    def dump_json(self) -> str:
        return json.dumps([e.to_dict() for e in self.events], indent=2, ensure_ascii=False)

    def _default_console_logger(self, event: TraceEvent):
        """
        [T=0ms] STATE_CHANGE: IDLE → PLANNING
        """
        elapsed_ms = int((event.timestamp - self.start_time) * 1000)
        
        # Format the log message based on event type
        msg = ""
        if event.type == EventType.STATE_CHANGE:
            old_state = event.data.get("from", "?")
            new_state = event.data.get("to", "?")
            msg = f"{old_state} → {new_state}"
            
        elif event.type == EventType.PLANNER_OUTPUT:
            action = event.data.get("action", {})
            action_type = action.get("type", "unknown")
            if action_type == "use_tool":
                tool = action.get("tool")
                args = action.get("args")
                msg = f"use_tool({tool}, {args})"
            elif action_type == "final":
                msg = "final"
            elif action_type == "task_list":
                count = len(action.get("tasks", []))
                msg = f"task_list({count} tasks)"
            else:
                msg = str(action)
                
        elif event.type == EventType.TOOL_CALL:
            tool = event.data.get("tool")
            args = event.data.get("args")
            msg = f"{tool}({args})"
            
        elif event.type == EventType.TOOL_RESULT:
            result = str(event.data.get("result", ""))
            # Truncate long results for display
            display_res = (result[:50] + "...") if len(result) > 50 else result
            msg = f"{display_res}"
            
        elif event.type == EventType.TASK_START:
            msg = f"Task: {event.data.get('goal')}"
            
        elif event.type == EventType.TASK_END:
            msg = f"Result: {event.data.get('result', '')[:30]}..."

        elif event.type == EventType.ERROR:
            msg = f"{event.data.get('error')}"

        else:
            # Generic fallback
            msg = str(event.data) if event.data else ""

        print(f"[T={elapsed_ms}ms] {event.type}: {msg}")
