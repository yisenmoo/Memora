import json
import os
from abc import ABC, abstractmethod
from typing import Optional
from core.memory.checkpoint import Checkpoint

class MemoryStore(ABC):
    @abstractmethod
    def save_checkpoint(self, checkpoint: Checkpoint):
        pass

    @abstractmethod
    def load_latest_checkpoint(self, agent_id: str) -> Optional[Checkpoint]:
        pass

    @abstractmethod
    def clear_checkpoint(self, agent_id: str):
        pass

    @abstractmethod
    def has_checkpoint(self, agent_id: str) -> bool:
        pass

class FileMemoryStore(MemoryStore):
    def __init__(self, storage_dir: str = ".memora/checkpoints"):
        self.storage_dir = storage_dir
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)

    def _get_file_path(self, agent_id: str) -> str:
        # Sanitize agent_id if needed, assuming simple string for now
        return os.path.join(self.storage_dir, f"{agent_id}.json")

    def save_checkpoint(self, checkpoint: Checkpoint):
        file_path = self._get_file_path(checkpoint.agent_id)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[MemoryStore] Failed to save checkpoint: {e}")

    def load_latest_checkpoint(self, agent_id: str) -> Optional[Checkpoint]:
        file_path = self._get_file_path(agent_id)
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Checkpoint.from_dict(data)
        except Exception as e:
            print(f"[MemoryStore] Failed to load checkpoint: {e}")
            return None

    def clear_checkpoint(self, agent_id: str):
        file_path = self._get_file_path(agent_id)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"[MemoryStore] Failed to delete checkpoint: {e}")

    def has_checkpoint(self, agent_id: str) -> bool:
        return os.path.exists(self._get_file_path(agent_id))
