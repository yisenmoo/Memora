from typing import Optional, List, Dict, Any

class Task:
    def __init__(self, id: str, goal: str):
        self.id = id
        self.goal = goal
        self.status = "pending"  # pending, running, completed, failed
        self.result = ""
        self.history: List[str] = [] # Execution history for this task

    def mark_running(self):
        self.status = "running"

    def mark_completed(self, result: str):
        self.status = "completed"
        self.result = result

    def mark_failed(self, error: str):
        self.status = "failed"
        self.result = error

    def add_history(self, record: str):
        self.history.append(record)
    
    def get_context(self) -> str:
        return "\n".join(self.history)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status,
            "result": self.result,
            "history": self.history
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        task = cls(id=data["id"], goal=data["goal"])
        task.status = data.get("status", "pending")
        task.result = data.get("result", "")
        task.history = data.get("history", [])
        return task
